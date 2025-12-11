#!/bin/bash
# One-time GCP setup script
# Run this once to configure your GCP project

set -e

PROJECT_ID="${GCP_PROJECT_ID:-triple-course-480814-e4}"
REGION="${GCP_REGION:-us-central1}"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-aivestorlab@gmail.com}"

echo "=== GCP Setup for Biotech M&A Predictor ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Notification Email: $NOTIFICATION_EMAIL"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "=== Enabling Required APIs ==="
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    sqladmin.googleapis.com \
    billingbudgets.googleapis.com \
    monitoring.googleapis.com \
    iam.googleapis.com

echo "APIs enabled successfully"

# Create Artifact Registry repository
echo ""
echo "=== Creating Artifact Registry Repository ==="
gcloud artifacts repositories create biotech-ma-predictor \
    --repository-format=docker \
    --location="$REGION" \
    --description="Docker images for Biotech M&A Predictor" \
    2>/dev/null || echo "Repository already exists"

# Configure Docker for Artifact Registry
echo ""
echo "=== Configuring Docker ==="
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Create secrets (placeholder values)
echo ""
echo "=== Creating Secret Manager Secrets ==="
gcloud secrets create biotech-ma-predictor-database-url \
    --replication-policy="automatic" \
    2>/dev/null || echo "Secret 'database-url' already exists"

gcloud secrets create biotech-ma-predictor-api-keys \
    --replication-policy="automatic" \
    2>/dev/null || echo "Secret 'api-keys' already exists"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Add secret values:"
echo "   echo 'postgresql://...' | gcloud secrets versions add biotech-ma-predictor-database-url --data-file=-"
echo ""
echo "2. Deploy infrastructure with Terraform:"
echo "   ./scripts/deploy.sh"
echo ""
echo "3. Or build and deploy manually:"
echo "   ./scripts/build-push.sh"
echo "   gcloud run deploy biotech-ma-predictor --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/biotech-ma-predictor/biotech-ma-predictor:latest --region $REGION"
