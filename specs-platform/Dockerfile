FROM python:3.11-slim

WORKDIR /app

COPY index.html .
COPY specs ./specs

EXPOSE 8080

CMD exec python3 -m http.server $PORT 2>&1
