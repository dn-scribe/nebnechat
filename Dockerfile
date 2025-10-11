FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create required temp directories with proper permissions
RUN mkdir -p /tmp/uploads /tmp/downloaded /tmp/flask_session && \
    chmod -R 777 /tmp/uploads /tmp/downloaded /tmp/flask_session

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install flask-session \
    && pip install .

# Expose port 7860
EXPOSE 7860

# Set a fixed session secret for stability across restarts
ENV SESSION_SECRET="stable-secret-key-for-docker-container"

# Default command (adjust as needed)
CMD ["python", "main.py"]
