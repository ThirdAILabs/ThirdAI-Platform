#!/bin/bash

$EXPORT_IMAGE_NAMES_COMMAND

# Finally, run the Uvicorn server
uvicorn main:app --reload --host 0.0.0.0 --port 80