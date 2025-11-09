# Multi-stage build for ArchiMind
FROM python:3.11-slim as builder

# Set build arguments
ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN groupadd -r archimind && useradd -r -g archimind archimind

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /root/.local /home/archimind/.local

# Copy application code
COPY . .

# Ensure data directory exists for persistent artifacts
RUN mkdir -p /app/data

# Set ownership
RUN chown -R archimind:archimind /app

# Switch to non-root user
USER archimind

# Add local bin to PATH
ENV PATH=/home/archimind/.local/bin:$PATH
ENV HOME=/home/archimind

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Run the application with Gunicorn (factory pattern in app.py)
CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "300"]
