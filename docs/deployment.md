# Deployment

Runtime Observer is currently optimized for local and lightweight internal deployments.

## Local process

```bash
just init
just run-collector
```

Set secrets through environment variables or a local `.env` file based on `.env.example`.

## Docker Compose

```bash
cp .env.example .env
# edit .env
RUNTIME_OBSERVER_API_KEY=replace-me docker compose up collector
```

The compose service stores SQLite data in a named Docker volume and exposes the collector on port `4319`.

## Security checklist

- Replace all placeholder API keys and dashboard passwords.
- Keep `RUNTIME_OBSERVER_INSECURE_DEV=false` outside local development.
- Do not expose the collector publicly without a trusted network boundary or reverse proxy authentication.
- Back up the SQLite volume if runtime telemetry must be retained.
