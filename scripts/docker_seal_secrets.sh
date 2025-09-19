#!/bin/sh
# Create a sealed secret from `.env.dev` using client Kubectl and Kubeseal libraries from Docker

docker run -v $(realpath .env.dev):/mnt/.env bitnami/kubectl:latest create secret generic \
    --dry-run=client --from-env-file /mnt/.env -o yaml env > dev-env.yaml
docker run -v $(realpath dev-env.yaml):/mnt/unsealed-secrets/dev-env.yaml \
           -v $(realpath manifest):/mnt/sealed-secrets \
           bitnami/sealed-secrets-kubeseal:latest \
           -f /mnt/unsealed-secrets/dev-env.yaml \
           --cert http://k8s-master-poc.hpc.uidaho.edu/v1/cert.pem \
           -w /mnt/sealed-secrets/dev-env.yaml \
           --scope cluster-wide