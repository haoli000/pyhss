#!/bin/bash
set -a
source ../docker/.env
set +a
echo "Debug: EIR_NO_MATCH_RESPONSE = $EIR_NO_MATCH_RESPONSE"
envsubst < ../docker/config.yaml > config-processed.yaml
echo "Config processing completed"
