FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        pkg-config \
        libmariadb-dev \
        libsctp-dev \
        lksctp-tools \
        build-essential \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy test script and requirements
# Use local copies since tools/ is excluded by .dockerignore
COPY swx_test_provision.py .
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set Python path to include mounted modules
ENV PYTHONPATH=/app:/app/lib:/app/services

# Run the test
CMD ["python3", "swx_test_provision.py"]