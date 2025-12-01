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
