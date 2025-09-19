#!/bin/sh
# Create a sealed secret from `.env.dev` using client Kubectl and Kubeseal libraries locally

kubectl create secret generic --dry-run=client --from-env-file .env.dev -o yaml env > dev-env.yaml
kubeseal -f dev-env.yaml --cert http://k8s-master-poc.hpc.uidaho.edu/v1/cert.pem -w manifest/dev-env.yaml --scope cluster-wide