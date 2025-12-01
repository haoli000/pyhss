#!/bin/bash

# PyHSS SWX Test Runner - Simple Docker Version
# This script builds and runs the SWX test using plain Docker commands

set -e

echo "=== PyHSS SWX Test Runner (Simple Docker) ==="

# Check if main PyHSS services are running
if ! curl -s http://localhost:8080/oam/ping > /dev/null; then
    echo "❌ PyHSS API service not accessible on localhost:8080"
    echo "Please start the main PyHSS services first:"
    echo "  docker-compose -f docker/docker-compose.yaml up -d"
    exit 1
fi

if ! nc -z localhost 3868 2>/dev/null; then
    echo "❌ PyHSS Diameter service not accessible on localhost:3868"
    echo "Please start the main PyHSS services first:"
    echo "  docker-compose -f docker/docker-compose.yaml up -d"
    exit 1
fi

echo "✅ PyHSS services are accessible"

# Build and run the test
echo "🏗️  Building test container..."
docker build -t pyhss-swx-test swx-test-client/

# Process config template with environment variables
echo "📝 Processing configuration template..."
# Use Python to process the config with environment variable substitution
cat > swx-test-client/process-config.py << 'EOF'
import os
import re

# Load environment variables
with open('../docker/.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

# Override database to use SQLite for testing (no MySQL needed)
os.environ['DATABASE_SERVER'] = 'localhost'
os.environ['DATABASE_TYPE'] = 'sqlite'
os.environ['DATABASE_NAME'] = '/tmp/test_hss.db'

# Set up logging configuration for testing
os.environ['LOGGING_LEVEL'] = 'INFO'
os.environ['LOGGING_HSS_FILE'] = '/tmp/pyhss_hss.log'
os.environ['LOGGING_DIAMETER_FILE'] = '/tmp/pyhss_diameter.log'

# Read and process the config
with open('../docker/config.yaml', 'r') as f:
    content = f.read()

# Replace ${VAR:-default} patterns with actual values or defaults
def replace_env_var(match):
    var_expr = match.group(1)
    if ':-' in var_expr:
        var, default = var_expr.split(':-', 1)
        return os.environ.get(var, default)
    else:
        return os.environ.get(var_expr, '')

content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)

# Write processed config
with open('config-processed.yaml', 'w') as f:
    f.write(content)

print(f"Config processing completed")
EOF
cd test && python3 process-config.py && cd ..

echo "🧪 Running SWX test..."
docker run --rm --network host \
  -v "$(pwd)/lib:/app/lib" \
  -v "$(pwd)/services:/app/services" \
  -v "$(pwd)/swx-test-client/config-processed.yaml:/app/config.yaml" \
  -v "$(pwd)/swx-test-client/config-processed.yaml:/etc/pyhss/config.yaml" \
  -v "$(pwd)/swx-test-client/config-processed.yaml:/usr/share/pyhss/config.yaml" \
  -v "$(pwd)/logs:/app/logs" \
  -v "/tmp:/tmp" \
  --env-file "$(pwd)/docker/.env" \
  -e PYHSS_CONFIG=/app/config.yaml \
  pyhss-swx-test

# Debug: Show what's in the processed config
echo "🔍 Debug: Checking processed config content..."
echo "First 5 lines of processed config:"
head -5 swx-test-client/config-processed.yaml
echo "EIR section:"
grep -A 3 "eir:" swx-test-client/config-processed.yaml

# Clean up processed config
rm -f swx-test-client/config-processed.yaml

echo "✅ Test completed"