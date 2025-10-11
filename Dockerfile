FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create required temp directories with proper permissions
RUN mkdir -p /tmp/uploads /tmp/downloaded && \
    chmod -R 777 /tmp/uploads /tmp/downloaded

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install .

# Expose port 7860
EXPOSE 7860

# Default command (adjust as needed)
CMD ["python", "main.py"]
