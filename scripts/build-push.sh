#!/bin/bash
# Build and push Docker image to Artifact Registry
# Usage: ./scripts/build-push.sh [tag]

set -e

TAG="${1:-latest}"
PROJECT_ID="${GCP_PROJECT_ID:-triple-course-480814-e4}"
REGION="${GCP_REGION:-us-central1}"
APP_NAME="biotech-ma-predictor"
REPO_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}"

echo "=== Building Docker Image ==="
echo "Tag: $TAG"
echo "Repository: $REPO_URL"
echo ""

cd "$(dirname "$0")/.."

# Configure Docker for Artifact Registry
echo "=== Configuring Docker for Artifact Registry ==="
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Build image
echo "=== Building Image ==="
docker build -t "${REPO_URL}/${APP_NAME}:${TAG}" .
docker tag "${REPO_URL}/${APP_NAME}:${TAG}" "${REPO_URL}/${APP_NAME}:latest"

# Push to Artifact Registry
echo "=== Pushing to Artifact Registry ==="
docker push "${REPO_URL}/${APP_NAME}:${TAG}"
docker push "${REPO_URL}/${APP_NAME}:latest"

echo ""
echo "=== Image Pushed Successfully ==="
echo "Image: ${REPO_URL}/${APP_NAME}:${TAG}"
echo ""
echo "Deploy to Cloud Run:"
echo "  gcloud run deploy $APP_NAME \\"
echo "    --image ${REPO_URL}/${APP_NAME}:${TAG} \\"
echo "    --region $REGION \\"
echo "    --platform managed"
