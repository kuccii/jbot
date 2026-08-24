FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY pyproject.toml README.md ./
COPY job_hunter/ job_hunter/
COPY config.example.yaml config.yaml

# Install
RUN pip install --no-cache-dir -e .

# Create data dir
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "job_hunter.dashboard.server:app", "--host", "0.0.0.0", "--port", "8000"]
