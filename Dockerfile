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
    git \
    && rm -rf /var/lib/apt/lists/*

# Ensure git is in PATH and set GIT_PYTHON_GIT_EXECUTABLE
RUN which git
ENV PATH="/usr/bin:/usr/local/bin:/bin:$PATH"
ENV GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git

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


# Add user with UID 1000 if not present and run as that user
RUN if ! id -u 1000 >/dev/null 2>&1; then \
    useradd -u 1000 -m appuser; \
fi
USER 1000

# Default command (adjust as needed)
CMD ["python", "main.py"]
