# Deployment

Runtime Observer is currently optimized for local and lightweight internal deployments.

## Local process

From a checkout:

```bash
just init
just run
```

Or install the collector directly from GitHub:

```bash
python -m pip install \
  'runtime-observer-server @ git+https://github.com/germanilia/runtime-observer.git#subdirectory=collector'

cp secrets.example.yml secrets.yml
# edit secrets.yml and set database.url
RUNTIME_OBSERVER_SECRETS=./secrets.yml runtime-observer-server --host 127.0.0.1 --port 4319
```

Keep only minimal process settings in environment variables. Put the SQLite connection string in `secrets.yml`. SDK API keys are generated in the dashboard per project and stored hashed in the database. On first dashboard login, create the admin user; later logins require that username/password.

## Docker Compose with LocalStack SQS

```bash
cp .env.example .env
cp secrets.example.yml secrets.yml
# edit .env for host/port and secrets.yml for database.url
docker compose up localstack collector
```

The compose file starts LocalStack on `localhost:4566`, creates `runtime-observer-ingest` and `runtime-observer-ingest-dlq`, and configures the collector with `RUNTIME_OBSERVER_INGEST_QUEUE_BACKEND=sqs`. The collector accepts ingest requests quickly, puts them on SQS, and a background worker drains messages into the database in batches.

For a no-SQS local smoke test, set:

```bash
RUNTIME_OBSERVER_INGEST_QUEUE_BACKEND=direct just run
```

The compose service stores SQLite data in a named Docker volume and exposes the collector on port `4319`.

## AWS SQS queue

Create the production ingest queue and DLQ with Terraform/OpenTofu:

```bash
cd deployments/aws-sqs
terraform init
terraform apply -var='name_prefix=runtime-observer' -var='aws_region=us-east-1'
```

Configure the collector with the output queue URL:

```bash
export RUNTIME_OBSERVER_INGEST_QUEUE_BACKEND=sqs
export RUNTIME_OBSERVER_SQS_QUEUE_URL='<terraform output ingest_queue_url>'
export AWS_REGION=us-east-1
```

Give the collector IAM permissions for `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`, and `sqs:GetQueueAttributes` on the ingest queue. Messages are only deleted after successful database processing; repeated failures are moved to the DLQ.

## EC2 deployment

The reproducible EC2 deployment is driven by:

```bash
RUNTIME_OBSERVER_DB_PASSWORD='<database-password>' just deploy-ec2 sela
```

This uses the `sela` AWS profile by default, deploys in `us-east-1` so the existing `*.bobthebot.io` ACM certificate can be attached to the ALB, creates/updates `metrics.bobthebot.io` in Route 53, and writes connection details to `deployments/sela/info.txt`. Provide the database password through `RUNTIME_OBSERVER_DB_PASSWORD` or an ignored local `deployments/sela/db-password.txt` file. The generated SSH private key is stored in `deployments/sela/runtime-observer-sela.pem` and ignored by git.

The EC2 deploy script also creates an SQS ingest queue, DLQ, EC2 instance role/profile with least-privilege SQS access, and writes `RUNTIME_OBSERVER_INGEST_QUEUE_BACKEND=sqs` plus the queue URL into the remote `.env`. The EC2 host runs Docker Compose with `pgvector/pgvector:pg17` as Postgres and the collector service. Database schema migrations run automatically when the collector starts.

## Security checklist

- Generate SDK API keys in the dashboard per project; do not keep SDK ingest keys in `.env` files.
- Record the first admin credentials securely.
- Keep `RUNTIME_OBSERVER_INSECURE_DEV=false` outside local development.
- Do not expose the collector publicly without a trusted network boundary or reverse proxy authentication.
- Back up the SQLite volume if runtime telemetry must be retained.
