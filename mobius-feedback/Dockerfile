# syntax=docker/dockerfile:1.7
# mobius-feedback — small stateless FastAPI service that classifies a piece of
# user product-feedback into a structured envelope for chat to persist. Same
# multi-stage pattern as mobius-skills/vibe.

FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

WORKDIR /build
COPY requirements.txt /build/requirements.txt
RUN pip install --no-cache-dir -r /build/requirements.txt
COPY app /build/app


FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --no-create-home --uid 10001 --shell /sbin/nologin feedback

COPY --from=builder /venv /venv
ENV VIRTUAL_ENV=/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY --from=builder --chown=feedback:feedback /build /app
WORKDIR /app
USER feedback

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8080
EXPOSE 8080

CMD exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port ${PORT} \
        --proxy-headers \
        --forwarded-allow-ips='*'
