# Dockerfile for the backend service
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system deps (minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

EXPOSE 5000

# Run with gunicorn; the Flask app is defined in app.py as `app`
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app", "--workers", "2"]
