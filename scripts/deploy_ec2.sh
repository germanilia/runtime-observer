#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-sela}"
AWS_PROFILE="${AWS_PROFILE:-sela}"
AWS_REGION="${AWS_REGION:-us-east-1}"
DOMAIN_NAME="${DOMAIN_NAME:-metrics.bobthebot.io}"
HOSTED_ZONE_ID="${HOSTED_ZONE_ID:-Z04861982PVM83JJV8MH}"
CERTIFICATE_ARN="${CERTIFICATE_ARN:-arn:aws:acm:us-east-1:138182066483:certificate/6e9eb02f-3688-4be0-b4fe-15a34eac1860}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.medium}"
APP_PORT="${APP_PORT:-4319}"
DEPLOY_DIR="deployments/${ENVIRONMENT}"
KEY_NAME="runtime-observer-${ENVIRONMENT}"
KEY_PATH="${DEPLOY_DIR}/${KEY_NAME}.pem"
INFO_PATH="${DEPLOY_DIR}/info.txt"
NAME_PREFIX="runtime-observer-${ENVIRONMENT}"
REMOTE_DIR="/opt/runtime-observer"
INGEST_QUEUE_NAME="${NAME_PREFIX}-ingest"
INGEST_DLQ_NAME="${NAME_PREFIX}-ingest-dlq"
INSTANCE_ROLE_NAME="${NAME_PREFIX}-collector-role"
INSTANCE_PROFILE_NAME="${NAME_PREFIX}-collector-profile"

mkdir -p "${DEPLOY_DIR}"

DB_PASSWORD_FILE="${DEPLOY_DIR}/db-password.txt"
DB_PASSWORD="${RUNTIME_OBSERVER_DB_PASSWORD:-${POSTGRES_PASSWORD:-}}"
if [[ -z "${DB_PASSWORD}" && -f "${DB_PASSWORD_FILE}" ]]; then
  DB_PASSWORD=$(<"${DB_PASSWORD_FILE}")
fi
if [[ -z "${DB_PASSWORD}" ]]; then
  echo "Database password is required. Set RUNTIME_OBSERVER_DB_PASSWORD or create ${DB_PASSWORD_FILE}." >&2
  exit 1
fi
DB_PASSWORD_ENCODED=$(DB_PASSWORD="${DB_PASSWORD}" python3 - <<'PY'
import os
from urllib.parse import quote
print(quote(os.environ["DB_PASSWORD"], safe=""))
PY
)

aws_cmd() {
  aws --profile "${AWS_PROFILE}" --region "${AWS_REGION}" "$@"
}

echo "Checking ACM certificate ${CERTIFICATE_ARN}"
CERT_STATUS=$(aws_cmd acm describe-certificate --certificate-arn "${CERTIFICATE_ARN}" --query 'Certificate.Status' --output text)
CERT_NAMES=$(aws_cmd acm describe-certificate --certificate-arn "${CERTIFICATE_ARN}" --query 'Certificate.SubjectAlternativeNames' --output text)
if [[ "${CERT_STATUS}" != "ISSUED" || " ${CERT_NAMES} " != *" *.bobthebot.io "* ]]; then
  echo "Certificate is not issued or does not cover *.bobthebot.io" >&2
  exit 1
fi

if [[ ! -f "${KEY_PATH}" ]]; then
  echo "Creating local SSH key ${KEY_PATH}"
  ssh-keygen -t rsa -b 4096 -m PEM -N "" -f "${KEY_PATH}" -C "${KEY_NAME}"
  chmod 600 "${KEY_PATH}"
fi
if ! aws_cmd ec2 describe-key-pairs --key-names "${KEY_NAME}" >/dev/null 2>&1; then
  echo "Importing EC2 key pair ${KEY_NAME}"
  aws_cmd ec2 import-key-pair --key-name "${KEY_NAME}" --public-key-material "fileb://${KEY_PATH}.pub" >/dev/null
fi

VPC_ID=$(aws_cmd ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
if [[ -z "${VPC_ID}" || "${VPC_ID}" == "None" ]]; then
  echo "No default VPC found in ${AWS_REGION}" >&2
  exit 1
fi
readarray -t SUBNET_IDS < <(aws_cmd ec2 describe-subnets --filters Name=vpc-id,Values="${VPC_ID}" --query 'Subnets[?MapPublicIpOnLaunch==`true`].SubnetId' --output text | tr '\t' '\n')
if (( ${#SUBNET_IDS[@]} < 2 )); then
  echo "Need at least two public subnets for the ALB" >&2
  exit 1
fi

ensure_sg() {
  local name="$1" desc="$2"
  local sg_id
  sg_id=$(aws_cmd ec2 describe-security-groups --filters Name=vpc-id,Values="${VPC_ID}" Name=group-name,Values="${name}" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
  if [[ -z "${sg_id}" || "${sg_id}" == "None" ]]; then
    sg_id=$(aws_cmd ec2 create-security-group --group-name "${name}" --description "${desc}" --vpc-id "${VPC_ID}" --query 'GroupId' --output text)
  fi
  echo "${sg_id}"
}

ALB_SG_ID=$(ensure_sg "${NAME_PREFIX}-alb" "Runtime Observer ALB")
INSTANCE_SG_ID=$(ensure_sg "${NAME_PREFIX}-instance" "Runtime Observer EC2 instance")
aws_cmd ec2 authorize-security-group-ingress --group-id "${ALB_SG_ID}" --ip-permissions IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges='[{CidrIp=0.0.0.0/0,Description="HTTP redirect"}]' >/dev/null 2>&1 || true
aws_cmd ec2 authorize-security-group-ingress --group-id "${ALB_SG_ID}" --ip-permissions IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges='[{CidrIp=0.0.0.0/0,Description="HTTPS"}]' >/dev/null 2>&1 || true
aws_cmd ec2 authorize-security-group-ingress --group-id "${INSTANCE_SG_ID}" --ip-permissions IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges='[{CidrIp=0.0.0.0/0,Description="SSH"}]' >/dev/null 2>&1 || true
aws_cmd ec2 authorize-security-group-ingress --group-id "${INSTANCE_SG_ID}" --ip-permissions IpProtocol=tcp,FromPort="${APP_PORT}",ToPort="${APP_PORT}",UserIdGroupPairs="[{GroupId=${ALB_SG_ID},Description=\"Collector from ALB\"}]" >/dev/null 2>&1 || true

ACCOUNT_ID=$(aws --profile "${AWS_PROFILE}" sts get-caller-identity --query Account --output text)
DLQ_URL=$(aws_cmd sqs get-queue-url --queue-name "${INGEST_DLQ_NAME}" --query QueueUrl --output text 2>/dev/null || aws_cmd sqs create-queue --queue-name "${INGEST_DLQ_NAME}" --attributes MessageRetentionPeriod=1209600 --query QueueUrl --output text)
DLQ_ARN=$(aws_cmd sqs get-queue-attributes --queue-url "${DLQ_URL}" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)
QUEUE_ATTRIBUTES_FILE=$(mktemp)
python3 - <<PY > "${QUEUE_ATTRIBUTES_FILE}"
import json
redrive_policy = json.dumps({"deadLetterTargetArn": "${DLQ_ARN}", "maxReceiveCount": "5"})
print(json.dumps({
    "VisibilityTimeout": "30",
    "MessageRetentionPeriod": "1209600",
    "ReceiveMessageWaitTimeSeconds": "10",
    "RedrivePolicy": redrive_policy,
}))
PY
INGEST_QUEUE_URL=$(aws_cmd sqs get-queue-url --queue-name "${INGEST_QUEUE_NAME}" --query QueueUrl --output text 2>/dev/null || aws_cmd sqs create-queue --queue-name "${INGEST_QUEUE_NAME}" --attributes "file://${QUEUE_ATTRIBUTES_FILE}" --query QueueUrl --output text)
rm -f "${QUEUE_ATTRIBUTES_FILE}"
INGEST_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:${INGEST_QUEUE_NAME}"

if ! aws --profile "${AWS_PROFILE}" iam get-role --role-name "${INSTANCE_ROLE_NAME}" >/dev/null 2>&1; then
  aws --profile "${AWS_PROFILE}" iam create-role --role-name "${INSTANCE_ROLE_NAME}" --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
fi
POLICY_DOC=$(mktemp)
cat > "${POLICY_DOC}" <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["sqs:SendMessage","sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueAttributes"],"Resource":"${INGEST_QUEUE_ARN}"}]}
JSON
aws --profile "${AWS_PROFILE}" iam put-role-policy --role-name "${INSTANCE_ROLE_NAME}" --policy-name runtime-observer-sqs --policy-document "file://${POLICY_DOC}" >/dev/null
rm -f "${POLICY_DOC}"
if ! aws --profile "${AWS_PROFILE}" iam get-instance-profile --instance-profile-name "${INSTANCE_PROFILE_NAME}" >/dev/null 2>&1; then
  aws --profile "${AWS_PROFILE}" iam create-instance-profile --instance-profile-name "${INSTANCE_PROFILE_NAME}" >/dev/null
  aws --profile "${AWS_PROFILE}" iam add-role-to-instance-profile --instance-profile-name "${INSTANCE_PROFILE_NAME}" --role-name "${INSTANCE_ROLE_NAME}" >/dev/null
  sleep 10
fi

TG_ARN=$(aws_cmd elbv2 describe-target-groups --names "${NAME_PREFIX}-tg" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)
if [[ -z "${TG_ARN}" || "${TG_ARN}" == "None" ]]; then
  TG_ARN=$(aws_cmd elbv2 create-target-group --name "${NAME_PREFIX}-tg" --protocol HTTP --port "${APP_PORT}" --vpc-id "${VPC_ID}" --target-type instance --health-check-protocol HTTP --health-check-path / --matcher HttpCode=200-399 --query 'TargetGroups[0].TargetGroupArn' --output text)
fi

ALB_ARN=$(aws_cmd elbv2 describe-load-balancers --names "${NAME_PREFIX}-alb" --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || true)
if [[ -z "${ALB_ARN}" || "${ALB_ARN}" == "None" ]]; then
  ALB_ARN=$(aws_cmd elbv2 create-load-balancer --name "${NAME_PREFIX}-alb" --type application --scheme internet-facing --security-groups "${ALB_SG_ID}" --subnets "${SUBNET_IDS[@]}" --query 'LoadBalancers[0].LoadBalancerArn' --output text)
fi
ALB_DNS=$(aws_cmd elbv2 describe-load-balancers --load-balancer-arns "${ALB_ARN}" --query 'LoadBalancers[0].DNSName' --output text)
ALB_ZONE_ID=$(aws_cmd elbv2 describe-load-balancers --load-balancer-arns "${ALB_ARN}" --query 'LoadBalancers[0].CanonicalHostedZoneId' --output text)

LISTENERS=$(aws_cmd elbv2 describe-listeners --load-balancer-arn "${ALB_ARN}" --query 'Listeners[].Port' --output text 2>/dev/null || true)
if [[ " ${LISTENERS} " != *" 80 "* ]]; then
  aws_cmd elbv2 create-listener --load-balancer-arn "${ALB_ARN}" --protocol HTTP --port 80 --default-actions Type=redirect,RedirectConfig='{Protocol=HTTPS,Port=443,StatusCode=HTTP_301}' >/dev/null
fi
if [[ " ${LISTENERS} " != *" 443 "* ]]; then
  aws_cmd elbv2 create-listener --load-balancer-arn "${ALB_ARN}" --protocol HTTPS --port 443 --certificates CertificateArn="${CERTIFICATE_ARN}" --default-actions Type=forward,TargetGroupArn="${TG_ARN}" >/dev/null
fi

INSTANCE_ID=$(aws_cmd ec2 describe-instances --filters Name=tag:Name,Values="${NAME_PREFIX}" Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[0].InstanceId' --output text)
if [[ -z "${INSTANCE_ID}" || "${INSTANCE_ID}" == "None" ]]; then
  AMI_ID=$(aws_cmd ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query 'Parameter.Value' --output text)
  USER_DATA=$(mktemp)
  cat > "${USER_DATA}" <<'USERDATA'
#!/bin/bash
set -eux
systemctl enable --now docker || (dnf install -y docker && systemctl enable --now docker)
dnf install -y docker git rsync curl
mkdir -p /opt/runtime-observer
chown ec2-user:ec2-user /opt/runtime-observer
usermod -aG docker ec2-user || true
USERDATA
  INSTANCE_ID=$(aws_cmd ec2 run-instances --image-id "${AMI_ID}" --instance-type "${INSTANCE_TYPE}" --key-name "${KEY_NAME}" --security-group-ids "${INSTANCE_SG_ID}" --subnet-id "${SUBNET_IDS[0]}" --iam-instance-profile Name="${INSTANCE_PROFILE_NAME}" --associate-public-ip-address --user-data "file://${USER_DATA}" --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${NAME_PREFIX}},{Key=App,Value=runtime-observer},{Key=Environment,Value=${ENVIRONMENT}}]" --query 'Instances[0].InstanceId' --output text)
  rm -f "${USER_DATA}"
else
  STATE=$(aws_cmd ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query 'Reservations[0].Instances[0].State.Name' --output text)
  if [[ "${STATE}" == "stopped" ]]; then
    aws_cmd ec2 start-instances --instance-ids "${INSTANCE_ID}" >/dev/null
  fi
fi

PROFILE_ASSOCIATION=$(aws_cmd ec2 describe-iam-instance-profile-associations --filters Name=instance-id,Values="${INSTANCE_ID}" Name=state,Values=associated,associating --query 'IamInstanceProfileAssociations[0].AssociationId' --output text 2>/dev/null || true)
if [[ -z "${PROFILE_ASSOCIATION}" || "${PROFILE_ASSOCIATION}" == "None" ]]; then
  aws_cmd ec2 associate-iam-instance-profile --instance-id "${INSTANCE_ID}" --iam-instance-profile Name="${INSTANCE_PROFILE_NAME}" >/dev/null || true
fi

aws_cmd ec2 wait instance-running --instance-ids "${INSTANCE_ID}"
aws_cmd ec2 wait instance-status-ok --instance-ids "${INSTANCE_ID}"
PUBLIC_IP=$(aws_cmd ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
aws_cmd elbv2 register-targets --target-group-arn "${TG_ARN}" --targets Id="${INSTANCE_ID}",Port="${APP_PORT}"

cat > /tmp/runtime-observer-route53.json <<JSON
{
  "Comment": "Runtime Observer ${ENVIRONMENT}",
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "${DOMAIN_NAME}",
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "${ALB_ZONE_ID}",
        "DNSName": "${ALB_DNS}",
        "EvaluateTargetHealth": false
      }
    }
  }]
}
JSON
aws --profile "${AWS_PROFILE}" route53 change-resource-record-sets --hosted-zone-id "${HOSTED_ZONE_ID}" --change-batch file:///tmp/runtime-observer-route53.json >/dev/null
rm -f /tmp/runtime-observer-route53.json

SSH_OPTS=(-i "${KEY_PATH}" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10)
echo "Waiting for SSH on ${PUBLIC_IP}"
for _ in {1..30}; do
  if ssh "${SSH_OPTS[@]}" ec2-user@"${PUBLIC_IP}" 'echo ok' >/dev/null 2>&1; then
    break
  fi
  sleep 10
done

ARCHIVE=$(mktemp -t runtime-observer.XXXXXX.tar.gz)
ENV_FILE=$(mktemp -t runtime-observer-env.XXXXXX)
cat > "${ENV_FILE}" <<ENV
POSTGRES_PASSWORD=${DB_PASSWORD}
RUNTIME_OBSERVER_DATABASE_URL=postgresql://runtime_observer:${DB_PASSWORD_ENCODED}@db:5432/runtime_observer
RUNTIME_OBSERVER_INGEST_QUEUE_BACKEND=sqs
RUNTIME_OBSERVER_SQS_QUEUE_URL=${INGEST_QUEUE_URL}
AWS_DEFAULT_REGION=${AWS_REGION}
ENV
tar --exclude='.git' --exclude='.venv' --exclude='*/.venv' --exclude='node_modules' --exclude='*/node_modules' --exclude='**/__pycache__' --exclude='deployments/*/*.pem' --exclude='deployments/*/*.pub' --exclude='deployments/*/db-password.txt' -czf "${ARCHIVE}" .
ssh "${SSH_OPTS[@]}" ec2-user@"${PUBLIC_IP}" "sudo mkdir -p ${REMOTE_DIR} && sudo chown ec2-user:ec2-user ${REMOTE_DIR}"
scp "${SSH_OPTS[@]}" "${ARCHIVE}" ec2-user@"${PUBLIC_IP}":/tmp/runtime-observer.tar.gz
scp "${SSH_OPTS[@]}" "${ENV_FILE}" ec2-user@"${PUBLIC_IP}":/tmp/runtime-observer.env
ssh "${SSH_OPTS[@]}" ec2-user@"${PUBLIC_IP}" "set -euo pipefail; DOCKER=docker; if ! docker ps >/dev/null 2>&1; then DOCKER='sudo docker'; fi; if ! \$DOCKER compose version >/dev/null 2>&1; then sudo mkdir -p /usr/local/lib/docker/cli-plugins; sudo curl -SL https://github.com/docker/compose/releases/download/v2.40.3/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose; sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose; fi; if [ -f ${REMOTE_DIR}/docker-compose.yml ]; then cd ${REMOTE_DIR} && \$DOCKER compose down --remove-orphans; fi; sudo rm -rf ${REMOTE_DIR:?}/*; sudo chown ec2-user:ec2-user ${REMOTE_DIR}; tar -xzf /tmp/runtime-observer.tar.gz -C ${REMOTE_DIR}; mv /tmp/runtime-observer.env ${REMOTE_DIR}/.env; chmod 600 ${REMOTE_DIR}/.env; cd ${REMOTE_DIR}; cp deployments/docker-compose.ec2.yml docker-compose.yml; \$DOCKER compose up -d --remove-orphans --force-recreate collector"
rm -f "${ARCHIVE}" "${ENV_FILE}"

cat > "${INFO_PATH}" <<INFO
profile=${AWS_PROFILE}
region=${AWS_REGION}
domain=https://${DOMAIN_NAME}
alb_dns=${ALB_DNS}
instance_id=${INSTANCE_ID}
public_ip=${PUBLIC_IP}
ssh=ssh -i ${KEY_PATH} ec2-user@${PUBLIC_IP}
app_port=${APP_PORT}
target_group_arn=${TG_ARN}
certificate_arn=${CERTIFICATE_ARN}
ingest_queue_url=${INGEST_QUEUE_URL}
ingest_dlq_url=${DLQ_URL}
INFO

echo "Deployment complete: https://${DOMAIN_NAME}"
echo "Info written to ${INFO_PATH}"
