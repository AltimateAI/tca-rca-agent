# TCA RCA Agent - API Server Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY tca_core/ ./tca_core/
COPY tca_api/ ./tca_api/
COPY .env .env

# Expose API port
EXPOSE 8000

# Run API server
CMD ["uvicorn", "tca_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
