# webhook-relay

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

FastAPI webhook ingestion microservice with HMAC-SHA256 verification and SQLite WAL queue.

## Features

- **FastAPI** - Modern async web framework
- **HMAC-SHA256** - Signature verification for webhooks
- **SQLite WAL** - Durable webhook queue with WAL mode
- **Health & Stats** - Built-in monitoring endpoints
- **Docker Ready** - Production Dockerfile included

## Installation

```bash
pip install webhook-relay
```

## Usage

### Start Server

```bash
uvicorn webhook_relay:app --host 0.0.0.0 --port 8000
```

### Send Webhook

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Event-Type: user.created" \
  -d '{"user_id": 123, "email": "test@example.com"}'
```

### Check Health

```bash
curl http://localhost:8000/health
```

### View Stats

```bash
curl http://localhost:8000/stats
```

## Docker

```bash
make docker-build
make docker-run
```

## Development

```bash
make install
make test
```

## License

MIT License - see [LICENSE](LICENSE) for details.
