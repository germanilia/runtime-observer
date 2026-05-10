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

## Security checklist

- Generate SDK API keys in the dashboard per project; do not keep SDK ingest keys in `.env` files.
- Record the first admin credentials securely.
- Keep `RUNTIME_OBSERVER_INSECURE_DEV=false` outside local development.
- Do not expose the collector publicly without a trusted network boundary or reverse proxy authentication.
- Back up the SQLite volume if runtime telemetry must be retained.
