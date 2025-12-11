# Self-hosted GitHub Actions Runner on GCP Spot Instance
# Cost: ~$3-5/month for e2-medium spot (vs $0.008/min on GitHub = $16 for 2000 min)

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "github_repo" {
  description = "GitHub repo in format owner/repo"
  type        = string
}

variable "github_runner_token" {
  description = "GitHub runner registration token (from repo settings)"
  type        = string
  sensitive   = true
}

variable "machine_type" {
  description = "VM machine type"
  type        = string
  default     = "e2-medium" # 2 vCPU, 4GB RAM - good for builds
}

variable "spot_instance" {
  description = "Use spot/preemptible instance (70-90% cheaper)"
  type        = bool
  default     = true
}

variable "runner_labels" {
  description = "Labels for the runner"
  type        = list(string)
  default     = ["self-hosted", "gcp", "linux"]
}

# Service account for the runner
resource "google_service_account" "runner" {
  account_id   = "github-runner"
  display_name = "GitHub Actions Runner"
  project      = var.project_id
}

# Permissions for the runner
resource "google_project_iam_member" "runner_permissions" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/storage.admin",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.runner.email}"
}

# Firewall rule for runner (outbound only)
resource "google_compute_firewall" "runner_egress" {
  name    = "github-runner-egress"
  network = "default"
  project = var.project_id

  direction = "EGRESS"

  allow {
    protocol = "tcp"
    ports    = ["443", "80"]
  }

  target_service_accounts = [google_service_account.runner.email]
}

# Startup script stored in Secret Manager
resource "google_secret_manager_secret" "runner_token" {
  secret_id = "github-runner-token"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "runner_token" {
  secret      = google_secret_manager_secret.runner_token.id
  secret_data = var.github_runner_token
}

resource "google_secret_manager_secret_iam_member" "runner_token_access" {
  secret_id = google_secret_manager_secret.runner_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runner.email}"
  project   = var.project_id
}

# Instance template for the runner
resource "google_compute_instance_template" "runner" {
  name_prefix  = "github-runner-"
  machine_type = var.machine_type
  project      = var.project_id
  region       = var.region

  # Spot instance for cost savings
  scheduling {
    preemptible                 = var.spot_instance
    automatic_restart           = !var.spot_instance
    on_host_maintenance         = var.spot_instance ? "TERMINATE" : "MIGRATE"
    provisioning_model          = var.spot_instance ? "SPOT" : "STANDARD"
    instance_termination_action = var.spot_instance ? "STOP" : null
  }

  disk {
    source_image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
    auto_delete  = true
    boot         = true
    disk_size_gb = 50            # Enough for Docker images
    disk_type    = "pd-standard" # Cheaper than SSD
  }

  network_interface {
    network = "default"
    access_config {} # Ephemeral public IP
  }

  service_account {
    email  = google_service_account.runner.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -e

    # Install dependencies
    apt-get update
    apt-get install -y curl jq docker.io

    # Start Docker
    systemctl enable docker
    systemctl start docker

    # Create runner user
    useradd -m -s /bin/bash runner
    usermod -aG docker runner

    # Install GitHub Actions runner
    RUNNER_VERSION="2.311.0"
    cd /home/runner
    curl -o actions-runner.tar.gz -L "https://github.com/actions/runner/releases/download/v$${RUNNER_VERSION}/actions-runner-linux-x64-$${RUNNER_VERSION}.tar.gz"
    tar xzf actions-runner.tar.gz
    chown -R runner:runner /home/runner

    # Get runner token from Secret Manager
    RUNNER_TOKEN=$(gcloud secrets versions access latest --secret=github-runner-token)

    # Configure runner
    su - runner -c "./config.sh --url https://github.com/${var.github_repo} --token $RUNNER_TOKEN --labels ${join(",", var.runner_labels)} --unattended --replace"

    # Install and start as service
    ./svc.sh install runner
    ./svc.sh start

    echo "GitHub Actions runner started successfully"
  EOF

  labels = {
    purpose = "github-runner"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Managed instance group (auto-restart on preemption)
resource "google_compute_instance_group_manager" "runner" {
  name               = "github-runner-mig"
  base_instance_name = "github-runner"
  zone               = var.zone
  project            = var.project_id

  version {
    instance_template = google_compute_instance_template.runner.id
  }

  target_size = 1 # Run 1 runner by default

  named_port {
    name = "http"
    port = 80
  }

  # Auto-heal if runner dies
  auto_healing_policies {
    health_check      = google_compute_health_check.runner.id
    initial_delay_sec = 300
  }
}

# Health check for auto-healing
resource "google_compute_health_check" "runner" {
  name    = "github-runner-health"
  project = var.project_id

  check_interval_sec  = 30
  timeout_sec         = 10
  healthy_threshold   = 2
  unhealthy_threshold = 3

  tcp_health_check {
    port = 22
  }
}

# Outputs
output "runner_instance_group" {
  value = google_compute_instance_group_manager.runner.name
}

output "runner_service_account" {
  value = google_service_account.runner.email
}

output "estimated_monthly_cost" {
  value = <<-EOT
    Estimated cost for e2-medium spot instance:
    - Compute: ~$3-5/month (spot pricing, 70% off)
    - Disk (50GB): ~$2/month
    - Total: ~$5-7/month for UNLIMITED build minutes

    Compare to GitHub Actions:
    - 2000 free minutes, then $0.008/min
    - 4000 minutes = $16/month

    To scale up temporarily for heavy builds:
      gcloud compute instance-groups managed resize github-runner-mig --size=3 --zone=${var.zone}

    To scale down:
      gcloud compute instance-groups managed resize github-runner-mig --size=1 --zone=${var.zone}
  EOT
}
