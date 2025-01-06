#!/bin/bash

curr_dir=$(dirname "$(realpath "$0")")

ARGS=(
    "--api.dashboard=true"
    "--api.insecure=true"
    "--entrypoints.web.address=:80"
    "--entrypoints.traefik.address=:8080"
    "--providers.nomad=true"
    "--providers.nomad.endpoint.address=http://localhost:4646"
    "--providers.consulcatalog.endpoint.address=127.0.0.1:8500"
    "--providers.consulcatalog=true"
    "--providers.consulcatalog.endpoint.scheme=http"
    "--providers.consulcatalog.exposedByDefault=false"
    "--providers.file.filename=$curr_dir/traefik_config/dynamic-conf.yml"
    "--providers.file.watch=true"
    "--log.level=DEBUG"
    "--providers.http.pollInterval=5s"
)

traefik ${ARGS[@]}
