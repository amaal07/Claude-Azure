#!/usr/bin/env bash
# deploy.sh — Build, push Docker image to ACR, and restart the Azure Web App.
# Run from the repo root: bash scripts/deploy.sh
set -euo pipefail

echo "==> Reading Terraform outputs..."
cd infra
ACR_SERVER=$(terraform output -raw acr_login_server)
WEBAPP_NAME=$(terraform output -raw webapp_name)
cd ..

ACR_NAME="${ACR_SERVER%%.*}"   # strip .azurecr.io
APP_NAME="stock-predictor"
IMAGE="${ACR_SERVER}/${APP_NAME}:latest"
RESOURCE_GROUP="AmalRG"

echo "==> Logging in to ACR: ${ACR_SERVER}"
az acr login --name "${ACR_NAME}"

echo "==> Building Docker image: ${IMAGE}"
docker build -t "${IMAGE}" ./app

echo "==> Pushing image to ACR..."
docker push "${IMAGE}"

echo "==> Restarting Web App: ${WEBAPP_NAME}"
az webapp restart \
  --name "${WEBAPP_NAME}" \
  --resource-group "${RESOURCE_GROUP}"

echo ""
echo "Deployment complete!"
echo "App URL: https://${WEBAPP_NAME}.azurewebsites.net"