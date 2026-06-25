FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e . && \
    playwright install chromium

EXPOSE 8080

VOLUME ["/app/data"]

ENTRYPOINT ["job-bot"]
CMD ["dashboard", "--host", "0.0.0.0"]
