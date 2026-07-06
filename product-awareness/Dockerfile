# product-awareness retrieval service (Cloud Run).
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY product_awareness ./product_awareness
# Ship the pre-chunked manuals (chunking is done offline + committed). The corpus
# is embedded into pgvector by the `ingest-from-chunks` Cloud Run Job, which reads
# these. The service itself only reads pgvector.
COPY corpus/chunks ./corpus/chunks

ENV PRODUCT_DOCS_STORE=pgvector \
    PRODUCT_DOCS_EMBEDDER=vertex
EXPOSE 8080

# Cloud Run injects $PORT (8080); bind to it.
CMD ["sh", "-c", "uvicorn product_awareness.service:app --host 0.0.0.0 --port ${PORT:-8080}"]
