# Local development

## One-command stack

```bash
docker compose up
```

- Redis: `localhost:6379`
- Backend: `http://localhost:8000`
- Frontend dev: `http://localhost:3000`

## Webhook tunnel (PR merge events on localhost)

```bash
python scripts/tunnel_webhook.py
```

Set `ORQIS_PUBLIC_URL` to the printed URL and configure your GitHub App webhook to
`{PUBLIC_URL}/integrations/github/webhook`.

## Tests

```bash
make unit
make integration   # requires Redis
make ci
```
