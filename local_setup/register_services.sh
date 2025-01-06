#!/bin/bash

# Directory containing service definition files
SERVICE_DIR="./services"

# Iterate over each .hcl file and register the service
for service_file in "$SERVICE_DIR"/*.hcl; do
  if [ -f "$service_file" ]; then
    echo "Registering service from $service_file..."
    consul services register "$service_file"
    if [ $? -eq 0 ]; then
      echo "Successfully registered $(basename "$service_file")"
    else
      echo "Failed to register $(basename "$service_file")"
    fi
  else
    echo "No .hcl files found in $SERVICE_DIR"
  fi
done

