#!/bin/bash
# Deployment script for Biotech M&A Predictor
# Usage: ./scripts/deploy.sh [environment]

set -e

ENVIRONMENT="${1:-dev}"
PROJECT_ID="${GCP_PROJECT_ID:-triple-course-480814-e4}"
REGION="${GCP_REGION:-us-central1}"
APP_NAME="biotech-ma-predictor"

echo "=== Biotech M&A Predictor Deployment ==="
echo "Environment: $ENVIRONMENT"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Ensure gcloud is configured
gcloud config set project "$PROJECT_ID"

# Navigate to terraform directory
cd "$(dirname "$0")/../terraform/environments/gcp"

# Initialize Terraform
echo "=== Initializing Terraform ==="
terraform init

# Create terraform.tfvars if it doesn't exist
if [ ! -f terraform.tfvars ]; then
    echo "Creating terraform.tfvars from example..."
    cp terraform.tfvars.example terraform.tfvars
    echo ""
    echo "IMPORTANT: Edit terraform.tfvars with your settings:"
    echo "  - notification_email (for budget alerts)"
    echo "  - Any other customizations"
    echo ""
    read -p "Press Enter after editing terraform.tfvars, or Ctrl+C to abort..."
fi

# Plan
echo "=== Terraform Plan ==="
terraform plan -out=tfplan

# Apply
read -p "Apply this plan? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "=== Applying Terraform ==="
    terraform apply tfplan
fi

# Output results
echo ""
echo "=== Deployment Complete ==="
terraform output

echo ""
echo "=== Next Steps ==="
echo "1. Build and push Docker image:"
echo "   ./scripts/build-push.sh"
echo ""
echo "2. Or connect GitHub for automatic deployments:"
echo "   gcloud builds connections create github \\"
echo "     --project=$PROJECT_ID \\"
echo "     --region=$REGION"
