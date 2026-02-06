# Mobius Developer Setup Guide

This guide covers everything needed to set up your local development environment for Mobius services.

> **Important**: All development now uses shared **GCP Dev Cloud** resources. There is no local PostgreSQL, Redis, or BigQuery setup required.

---

## Prerequisites

- **Python 3.11+** (required for all Python services)
- **Node.js 20+** (for frontend services)
- **Google Cloud SDK** (`gcloud` CLI)
- **Git**

---

## 1. GCP Authentication Setup

All Mobius services connect to GCP resources. You need to authenticate with Google Cloud:

```bash
# Install gcloud CLI (macOS)
brew install google-cloud-sdk

# Authenticate with your Google account
gcloud auth login

# Set up Application Default Credentials (ADC)
gcloud auth application-default login

# Verify you have access to the dev project
gcloud config set project mobius-os-dev
gcloud projects describe mobius-os-dev
```

### Request Project Access

Ask a project admin to grant you access to:
- `mobius-os-dev` (Dev environment)
- Optionally: `mobius-staging-mobius` (Staging), `mobiusos-new` (Production)

Required IAM roles for development:
- `roles/viewer` (basic read access)
- `roles/cloudsql.client` (database connections)
- `roles/storage.objectViewer` (GCS access)
- `roles/aiplatform.user` (Vertex AI)
- `roles/bigquery.user` (BigQuery)

---

## 2. Dev Cloud Resources

All developers share these GCP Dev resources:

| Resource | Connection Details |
|----------|-------------------|
| **PostgreSQL** | `34.135.72.145:5432` (Cloud SQL) |
| **Redis** | `10.40.102.67:6379` (private IP, requires VPN/proxy) |
| **BigQuery** | Project: `mobius-os-dev`, Datasets: `landing_rag`, `mobius_rag` |
| **GCS Bucket** | `mobius-rag-uploads-dev` |
| **Vertex AI** | Project: `mobius-os-dev`, Region: `us-central1` |

### Databases (Cloud SQL)

| Database | Purpose |
|----------|---------|
| `mobius_rag` | RAG document processing and embeddings |
| `mobius_chat` | Chat service persistence |
| `mobius_os` | OS backend (Flask) |
| `mobius_user` | User authentication |

**Connection string format:**
```
postgresql://postgres:MobiusDev123$@34.135.72.145:5432/{database_name}
```

### Connecting to Redis (Private IP)

Redis is on a private IP and requires one of:

1. **Cloud SQL Proxy + SSH Tunnel** (recommended for local dev)
2. **VPN to GCP VPC** (if your org has VPN setup)
3. **Compute Engine jump host** (SSH tunnel through a GCE instance)

For most local development, services that need Redis (chat-worker, scraper-worker) can be tested against the cloud deployment.

---

## 3. Repository Structure

```
Mobius/
├── mobius-chat/        # Chat API and worker (FastAPI)
├── mobius-rag/         # RAG document processing (FastAPI)
├── mobius-os/          # OS backend (Flask)
├── Mobius-user/        # Shared auth module (library)
├── mobius-dbt/         # BigQuery transformations (dbt)
├── mobius-skills/      # Skills (web-scraper, etc.)
├── mobius-config/      # Shared configuration
├── mobius-auth/        # Auth service (TypeScript)
├── mobius-design/      # Brand assets and CSS tokens
└── docs/               # Documentation
```

---

## 4. Python Environment Setup

All Mobius Python services share a single virtual environment at the workspace root.

```bash
cd ~/Mobius

# Create shared venv (if not already created)
python3.11 -m venv .venv

# Activate
source .venv/bin/activate

# Install all dependencies from consolidated requirements.txt
pip install --upgrade pip
pip install -r requirements.txt

# Install mobius-user as editable package
pip install -e ./Mobius-user
```

### Verify Installation

```bash
source .venv/bin/activate
python -c "import fastapi, flask, sqlalchemy, redis, google.cloud.aiplatform, mobius_user; print('All packages installed')"
```

---

## 5. Environment Configuration

Each service has a `.env.example` file. Copy it to `.env`:

```bash
# For each service you're working on:
cd mobius-chat && cp .env.example .env
cd ../mobius-rag && cp .env.example .env
cd ../mobius-os/backend && cp .env.example .env
cd ../Mobius-user && cp .env.example .env
cd ../mobius-dbt && cp .env.example .env
cd ../mobius-skills/web-scraper && cp .env.example .env
```

The `.env.example` files are pre-configured for the dev cloud environment. You typically don't need to change anything unless you need to:
- Point to a different environment (staging/prod)
- Override specific values for testing

### Key Environment Variables

| Variable | Default (Dev) | Description |
|----------|---------------|-------------|
| `GCP_PROJECT_ID` | `mobius-os-dev` | GCP project for Vertex AI, GCS |
| `DATABASE_URL` | `postgresql+asyncpg://...@34.135.72.145:5432/...` | Service database |
| `REDIS_URL` | `redis://10.40.102.67:6379/0` | Redis for queuing |
| `GCS_BUCKET` | `mobius-rag-uploads-dev` | Cloud Storage bucket |
| `VERTEX_PROJECT_ID` | `mobius-os-dev` | Vertex AI project |
| `VERTEX_LOCATION` | `us-central1` | Vertex AI region |
| `LLM_PROVIDER` | `vertex` | LLM provider (vertex/openai) |
| `VERTEX_MODEL` | `gemini-2.5-flash` | Model for chat |

---

## 6. Running Services Locally

Always activate the shared venv first:

```bash
cd ~/Mobius
source .venv/bin/activate
```

### mobius-chat (FastAPI)

```bash
cd mobius-chat

# API server (port 8001)
uvicorn app.main:app --reload --port 8001

# Worker (separate terminal, activate venv first)
python -m app.worker
```

### mobius-rag (FastAPI)

```bash
cd mobius-rag

# Backend (port 8002)
uvicorn app.main:app --reload --port 8002

# Chunking worker (separate terminal)
python -m app.workers.chunking_worker

# Embedding worker (separate terminal)
python -m app.workers.embedding_worker
```

### mobius-os (Flask)

```bash
cd mobius-os/backend
flask run --port 5000
```

### mobius-dbt

```bash
cd mobius-dbt

# Test connection
dbt debug

# Run transformations
dbt run --target dev

# Run specific model
dbt run --select published_rag_embeddings
```

### All Services (using mstart/mstop)

```bash
# From workspace root (venv activated)
./mstart   # Starts all services
./mstop    # Stops all services
```

---

## 7. Database Migrations

### mobius-rag (SQLAlchemy models)

Tables are auto-created by SQLAlchemy. For schema changes, update `app/models.py`.

### mobius-chat (SQL migrations)

```bash
cd mobius-chat/db/schema
# Apply migrations in order
psql "postgresql://postgres:MobiusDev123$@34.135.72.145:5432/mobius_chat" -f 001_rag_schema.sql
# ... etc
```

### mobius-os (Alembic)

```bash
cd mobius-os/backend
alembic upgrade head
```

### Mobius-user (Alembic)

```bash
cd Mobius-user
alembic upgrade head
```

---

## 8. Testing

```bash
# From service directory with activated venv
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test
pytest tests/test_specific.py -v
```

---

## 9. Common Issues

### "Connection refused" to PostgreSQL

- Verify your IP is authorized in Cloud SQL
- Check if GCP ADC is set up: `gcloud auth application-default print-access-token`

### "Redis connection failed"

- Redis is on private IP `10.40.102.67`
- You need VPN or SSH tunnel to access from local machine
- For testing, mock Redis or skip Redis-dependent tests

### "Vertex AI quota exceeded"

- Dev environment has limited quotas
- Use `gemini-2.0-flash-lite` for high-volume testing
- Contact admin to increase quotas if needed

### "ModuleNotFoundError: mobius_user"

```bash
pip install -e ./Mobius-user  # From workspace root
```

---

## 10. Additional Resources

- [Environment Variables Matrix](../mobius-config/env-matrix.md) - Complete env var reference
- [mobius-design/STYLE_GUIDELINES.md](../mobius-design/STYLE_GUIDELINES.md) - UI/branding guidelines
- [mobius-chat/docs/](../mobius-chat/docs/) - Chat service architecture
- [mobius-dbt/docs/](../mobius-dbt/docs/) - DBT pipeline documentation

---

*Last updated: 2026-02-06*
