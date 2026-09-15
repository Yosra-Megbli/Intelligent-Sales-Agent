# Production Dockerfile for Ecofix Sophie FastAPI backend
# Optimized for free-tier deployments (Render / containers)
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Create a non-root system user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Install base dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Set correct ownership for the non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose standard port (Render will override via $PORT)
EXPOSE 8000

# Start Uvicorn bound to 0.0.0.0 and dynamic $PORT
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
