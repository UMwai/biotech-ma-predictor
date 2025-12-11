#!/bin/bash
# Set up self-hosted GitHub Actions runner on GCP spot instance
# Cost: ~$5-7/month for UNLIMITED minutes

set -e

PROJECT_ID="${GCP_PROJECT_ID:-triple-course-480814-e4}"
ZONE="${GCP_ZONE:-us-central1-a}"
GITHUB_REPO="UMwai/biotech-ma-predictor"

echo "=== GitHub Self-Hosted Runner Setup ==="
echo ""
echo "COST COMPARISON:"
echo "================"
echo ""
echo "GitHub Actions (paid):"
echo "  - 2000 min FREE/month"
echo "  - Then \$0.008/minute"
echo "  - 4000 min = \$16/month"
echo "  - 6000 min = \$32/month"
echo ""
echo "GCP Self-Hosted (spot instance):"
echo "  - e2-medium spot: ~\$5/month 24/7"
echo "  - UNLIMITED build minutes"
echo "  - Auto-restarts if preempted"
echo ""
echo "VERDICT: Self-hosted is cheaper if you use >2600 min/month"
echo ""

read -p "Continue with self-hosted runner setup? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

# Step 1: Get runner token from GitHub
echo ""
echo "=== Step 1: Get Runner Token from GitHub ==="
echo ""
echo "Go to: https://github.com/${GITHUB_REPO}/settings/actions/runners/new"
echo ""
echo "1. Click 'New self-hosted runner'"
echo "2. Select 'Linux' and 'x64'"
echo "3. Copy the token from the config command (looks like: AXXXX...)"
echo ""
read -p "Paste the runner token: " RUNNER_TOKEN

if [ -z "$RUNNER_TOKEN" ]; then
    echo "Error: Runner token is required"
    exit 1
fi

# Step 2: Store token in Secret Manager
echo ""
echo "=== Step 2: Storing token in Secret Manager ==="
gcloud secrets create github-runner-token \
    --project="$PROJECT_ID" \
    --replication-policy="automatic" \
    2>/dev/null || echo "Secret already exists"

echo -n "$RUNNER_TOKEN" | gcloud secrets versions add github-runner-token \
    --project="$PROJECT_ID" \
    --data-file=-

echo "Token stored securely"

# Step 3: Deploy runner via Terraform
echo ""
echo "=== Step 3: Deploy Runner ==="
cd "$(dirname "$0")/../terraform/environments/gcp"

# Add runner module to main.tf if not present
if ! grep -q "module \"github_runner\"" main.tf; then
    cat >> main.tf << 'TERRAFORM'

# =============================================================================
# GITHUB ACTIONS SELF-HOSTED RUNNER (Spot Instance)
# =============================================================================

module "github_runner" {
  source = "../../modules/github-runner"

  project_id          = var.project_id
  region              = var.region
  zone                = "${var.region}-a"
  github_repo         = "UMwai/biotech-ma-predictor"
  github_runner_token = data.google_secret_manager_secret_version.runner_token.secret_data
  machine_type        = "e2-medium"
  spot_instance       = true  # 70% cheaper
  runner_labels       = ["self-hosted", "gcp", "linux", "biotech"]
}

data "google_secret_manager_secret_version" "runner_token" {
  secret  = "github-runner-token"
  project = var.project_id
}

output "runner_info" {
  value = module.github_runner.estimated_monthly_cost
}
TERRAFORM
    echo "Added runner module to main.tf"
fi

terraform init
terraform apply -target=module.github_runner

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Your self-hosted runner is now running on GCP!"
echo ""
echo "To use it, update your workflow to use:"
echo "  runs-on: [self-hosted, gcp, linux]"
echo ""
echo "To scale runners up/down:"
echo "  gcloud compute instance-groups managed resize github-runner-mig --size=3 --zone=$ZONE"
echo ""
echo "To stop runner (save costs when not needed):"
echo "  gcloud compute instance-groups managed resize github-runner-mig --size=0 --zone=$ZONE"
