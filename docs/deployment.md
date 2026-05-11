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

## Docker Compose

```bash
cp .env.example .env
cp secrets.example.yml secrets.yml
# edit .env for host/port and secrets.yml for database.url
docker compose up collector
```

The compose service stores SQLite data in a named Docker volume and exposes the collector on port `4319`.

## EC2 deployment

The reproducible EC2 deployment is driven by:

```bash
RUNTIME_OBSERVER_DB_PASSWORD='<database-password>' just deploy-ec2 sela
```

This uses the `sela` AWS profile by default, deploys in `us-east-1` so the existing `*.bobthebot.io` ACM certificate can be attached to the ALB, creates/updates `metrics.bobthebot.io` in Route 53, and writes connection details to `deployments/sela/info.txt`. Provide the database password through `RUNTIME_OBSERVER_DB_PASSWORD` or an ignored local `deployments/sela/db-password.txt` file. The generated SSH private key is stored in `deployments/sela/runtime-observer-sela.pem` and ignored by git.

The EC2 host runs Docker Compose with `pgvector/pgvector:pg17` as Postgres and the collector service. Database schema migrations run automatically when the collector starts.

## Security checklist

- Generate SDK API keys in the dashboard per project; do not keep SDK ingest keys in `.env` files.
- Record the first admin credentials securely.
- Keep `RUNTIME_OBSERVER_INSECURE_DEV=false` outside local development.
- Do not expose the collector publicly without a trusted network boundary or reverse proxy authentication.
- Back up the SQLite volume if runtime telemetry must be retained.
