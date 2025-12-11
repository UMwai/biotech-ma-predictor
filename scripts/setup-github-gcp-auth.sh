#!/bin/bash
# Set up Workload Identity Federation for GitHub Actions -> GCP
# This allows GitHub Actions to authenticate to GCP WITHOUT service account keys

set -e

PROJECT_ID="${GCP_PROJECT_ID:-triple-course-480814-e4}"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
GITHUB_REPO="UMwai/biotech-ma-predictor"
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-actions-provider"
SERVICE_ACCOUNT_NAME="github-actions-deploy"

echo "=== Setting up Workload Identity Federation ==="
echo "Project: $PROJECT_ID"
echo "Project Number: $PROJECT_NUMBER"
echo "GitHub Repo: $GITHUB_REPO"
echo ""

# Enable required APIs
echo "=== Enabling APIs ==="
gcloud services enable iamcredentials.googleapis.com --project="$PROJECT_ID"
gcloud services enable sts.googleapis.com --project="$PROJECT_ID"

# Create Workload Identity Pool
echo "=== Creating Workload Identity Pool ==="
gcloud iam workload-identity-pools create "$POOL_NAME" \
    --project="$PROJECT_ID" \
    --location="global" \
    --display-name="GitHub Actions Pool" \
    2>/dev/null || echo "Pool already exists"

# Create Workload Identity Provider
echo "=== Creating Workload Identity Provider ==="
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_NAME" \
    --display-name="GitHub Actions Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    2>/dev/null || echo "Provider already exists"

# Create service account for GitHub Actions
echo "=== Creating Service Account ==="
gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --project="$PROJECT_ID" \
    --display-name="GitHub Actions Deploy SA" \
    2>/dev/null || echo "Service account already exists"

SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant required roles to service account
echo "=== Granting Roles to Service Account ==="
for role in \
    "roles/run.admin" \
    "roles/artifactregistry.writer" \
    "roles/iam.serviceAccountUser" \
    "roles/storage.admin" \
    "roles/secretmanager.secretAccessor"
do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$role" \
        --quiet
done

# Allow GitHub Actions to impersonate the service account
echo "=== Setting up Workload Identity Binding ==="
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --project="$PROJECT_ID" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"

# Output values for GitHub Secrets
echo ""
echo "=== SETUP COMPLETE ==="
echo ""
echo "Add these secrets to your GitHub repository:"
echo "  Settings -> Secrets and variables -> Actions -> New repository secret"
echo ""
echo "WIF_PROVIDER:"
echo "  projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"
echo ""
echo "WIF_SERVICE_ACCOUNT:"
echo "  ${SA_EMAIL}"
echo ""
echo "Or run this to copy to clipboard (macOS):"
echo "  echo 'projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}' | pbcopy"
