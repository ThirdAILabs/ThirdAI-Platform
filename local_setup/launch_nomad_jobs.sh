#!/bin/bash

# Check if a Nomad path is provided as an argument, otherwise use the default "nomad"
NOMAD_PATH=${1:-nomad}

# Verify that the nomad command is available
if ! command -v $NOMAD_PATH &> /dev/null
then
    echo "Nomad command could not be found at the specified path: $NOMAD_PATH"
    exit 1
fi

# Run Nomad jobs
$NOMAD_PATH job run -var="nomad_endpoint=$($NOMAD_PATH agent-info | grep 'known_servers' | awk '{print $3}' | sed 's/:4647//')" autoscaler.nomad
$NOMAD_PATH job run redis.nomad