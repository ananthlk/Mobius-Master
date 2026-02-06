# Mobius

Mobius platform monorepo with shared Python environment and GCP Dev cloud resources.

## Quick Start

```bash
# 1. Clone and enter workspace
cd ~/Mobius

# 2. Set up Python environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ./Mobius-user

# 3. Authenticate with GCP
gcloud auth application-default login

# 4. Copy environment files
for dir in mobius-chat mobius-rag mobius-os/backend Mobius-user mobius-dbt mobius-skills/web-scraper; do
  cp $dir/.env.example $dir/.env 2>/dev/null || true
done

# 5. Start all services
./mstart
```

See [docs/DEVELOPER_SETUP.md](docs/DEVELOPER_SETUP.md) for complete setup instructions.

## Services

| Folder | Purpose |
|--------|---------|
| `mobius-os` | Extension + Flask backend |
| `mobius-rag` | RAG document processing (FastAPI) |
| `mobius-chat` | Chat app, consumes RAG/DBT output (FastAPI) |
| `mobius-dbt` | BigQuery transformations (dbt) |
| `Mobius-user` | Shared user/auth module |
| `mobius-skills` | Skills (web-scraper, etc.) |

## Running Services

- **`./mstart`** - Start all services (landing page at http://localhost:3999)
- **`./mstop`** - Stop all services
- **`./mstart --no-landing`** - Start without landing page

To run from anywhere: `export PATH="$HOME/Mobius:$PATH"`

## Resources

- **[docs/DEVELOPER_SETUP.md](docs/DEVELOPER_SETUP.md)** - Complete developer setup
- **[mobius-config/env-matrix.md](mobius-config/env-matrix.md)** - Environment variables reference
- **[mobius-design/STYLE_GUIDELINES.md](mobius-design/STYLE_GUIDELINES.md)** - Branding and CSS tokens

## Dev Cloud Resources

All development uses shared GCP resources in `mobius-os-dev`:

| Resource | Connection |
|----------|------------|
| PostgreSQL | `34.135.72.145:5432` |
| Redis | `10.40.102.67:6379` |
| BigQuery | `mobius-os-dev.landing_rag`, `mobius-os-dev.mobius_rag` |
| GCS | `mobius-rag-uploads-dev` |
| Vertex AI | `us-central1` |
