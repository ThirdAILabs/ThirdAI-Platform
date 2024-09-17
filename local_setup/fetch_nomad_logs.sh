#!/bin/bash

# Ensure Nomad is in your PATH
NOMAD_PATH=$(which nomad)
if [ -z "$NOMAD_PATH" ]; then
  echo "Nomad is not installed or not in your PATH. Please install it first."
  exit 1
fi

# Check if skipping is enabled
if [ "$ENABLE_SKIP_JOBS" = "true" ]; then
  # Convert SKIP_JOBS to an array
  IFS=',' read -r -a SKIP_JOBS_ARRAY <<< "$SKIP_JOBS"
else
  SKIP_JOBS_ARRAY=()
fi

# Fetch all job names
echo "Fetching all Nomad jobs..."
NOMAD_JOBS=$($NOMAD_PATH job status | awk 'NR>1 {print $1}')

# Check if any jobs were found
if [ -z "$NOMAD_JOBS" ]; then
  echo "No Nomad jobs found."
  exit 0
fi

# Loop through all jobs to fetch their logs
for job in $NOMAD_JOBS; do
  # Check if the job should be skipped
  SKIP=false
  for skip_job in "${SKIP_JOBS_ARRAY[@]}"; do
    if [ "$job" == "$skip_job" ]; then
      SKIP=true
      echo "Skipping logs for job $job as per configuration."
      break
    fi
  done

  if [ "$SKIP" = true ]; then
    continue
  fi

  # Fetch stdout logs
  $NOMAD_PATH alloc logs -job "$job"  > "${job}_stdout.log"
  echo "STDOUT Logs for allocation $job:"
  cat "${job}_stdout.log"

  # Fetch stderr logs
  $NOMAD_PATH alloc logs -job --stderr "$job"> "${job}_stderr.log"
  echo "STDERR Logs for allocation $job:"
  cat "${job}_stderr.log"
done
