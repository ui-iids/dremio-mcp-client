#!/bin/sh
# Create a sealed secret from `.env.dev` using whatever is available.

if [[ ! -f .env.dev ]]; then
    echo ".env.dev file not found. Please create it and try again."
    exit 1
fi

if [[ -x "$(command -v kubeseal)" && -x "$(command -v kubectl)" ]]; then
    echo "Kubeseal and Kubectl are installed. Sealing secrets locally."
    ./scripts/cli_seal_secrets.sh
elif [[ -x "$(command -v docker)" ]]; then
    echo "Docker is installed. Using Docker to create sealed secrets."
    ./scripts/docker_seal_secrets.sh
else
    echo "Neither Kubeseal and Kubectl, or Docker are installed. Please install one of them."
    exit 1
fi