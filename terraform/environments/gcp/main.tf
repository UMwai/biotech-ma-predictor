terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Uncomment to use remote state
  # backend "gcs" {
  #   bucket = "your-terraform-state-bucket"
  #   prefix = "biotech-ma-predictor"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

locals {
  labels = {
    app         = var.app_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "billingbudgets.googleapis.com",
    "monitoring.googleapis.com",
    "compute.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# =============================================================================
# BUDGET ALERTS - $200/month with daily notifications
# =============================================================================

data "google_project" "project" {
  project_id = var.project_id
}

resource "google_billing_budget" "monthly_budget" {
  billing_account = data.google_project.project.billing_account
  display_name    = "${var.app_name}-${var.environment}-monthly-budget"

  budget_filter {
    projects = ["projects/${data.google_project.project.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount)
    }
  }

  # Alert at 25%, 50%, 75%, 90%, 100%
  dynamic "threshold_rules" {
    for_each = [0.25, 0.5, 0.75, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  # Also alert on forecasted spend
  dynamic "threshold_rules" {
    for_each = [0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "FORECASTED_SPEND"
    }
  }

  all_updates_rule {
    monitoring_notification_channels = [
      google_monitoring_notification_channel.email.id
    ]
    disable_default_iam_recipients = false
  }

  depends_on = [google_project_service.apis]
}

# Email notification channel for budget alerts
resource "google_monitoring_notification_channel" "email" {
  display_name = "${var.app_name}-budget-alerts"
  type         = "email"

  labels = {
    email_address = var.notification_email
  }

  depends_on = [google_project_service.apis]
}

# =============================================================================
# ARTIFACT REGISTRY - Store Docker images
# =============================================================================

resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.app_name
  description   = "Docker repository for ${var.app_name}"
  format        = "DOCKER"

  labels = local.labels

  # Cleanup policy to save storage costs
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"

    most_recent_versions {
      keep_count = 5
    }
  }

  cleanup_policies {
    id     = "delete-old-untagged"
    action = "DELETE"

    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s" # 7 days
    }
  }

  depends_on = [google_project_service.apis]
}

# =============================================================================
# CLOUD STORAGE - Reports and data
# =============================================================================

resource "google_storage_bucket" "data" {
  name          = "${var.project_id}-${var.app_name}-data"
  location      = var.region
  storage_class = "STANDARD"

  uniform_bucket_level_access = true

  labels = local.labels

  # Cost saving: Auto-delete old files
  lifecycle_rule {
    condition {
      age = 90 # Delete after 90 days
    }
    action {
      type = "Delete"
    }
  }

  # Move to cheaper storage after 30 days
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  versioning {
    enabled = false # Save costs
  }
}

# =============================================================================
# SECRET MANAGER - API keys and credentials
# =============================================================================

resource "google_secret_manager_secret" "database_url" {
  secret_id = "${var.app_name}-database-url"

  labels = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "api_keys" {
  secret_id = "${var.app_name}-api-keys"

  labels = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# =============================================================================
# CLOUD RUN - Serverless container (scale to zero = cost effective)
# =============================================================================

resource "google_cloud_run_v2_service" "app" {
  name     = var.app_name
  location = var.region

  labels = local.labels

  template {
    labels = local.labels

    scaling {
      min_instance_count = 0 # Scale to zero when idle
      max_instance_count = 2 # Limit max instances for cost
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.app_name}/${var.app_name}:latest"

      resources {
        limits = {
          cpu    = var.container_cpu
          memory = var.container_memory
        }
        cpu_idle = true # CPU throttled when not processing requests (cost saving)
      }

      ports {
        container_port = 8000
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.data.name
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      # Startup probe
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }
    }

    # Service account for Cloud Run
    service_account = google_service_account.cloud_run.email

    # Request timeout
    timeout = "300s"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.repo
  ]
}

# Allow unauthenticated access (public API)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Service account for Cloud Run
resource "google_service_account" "cloud_run" {
  account_id   = "${var.app_name}-run"
  display_name = "Cloud Run service account for ${var.app_name}"
}

# Grant Cloud Run access to secrets
resource "google_secret_manager_secret_iam_member" "cloud_run_database" {
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_secret_manager_secret_iam_member" "cloud_run_api_keys" {
  secret_id = google_secret_manager_secret.api_keys.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Grant Cloud Run access to storage bucket
resource "google_storage_bucket_iam_member" "cloud_run_storage" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

# =============================================================================
# CLOUD SQL (OPTIONAL - disabled by default to save costs)
# =============================================================================

resource "google_sql_database_instance" "postgres" {
  count = var.enable_database ? 1 : 0

  name             = "${var.app_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = var.db_tier

    # Cost savings
    availability_type = "ZONAL" # No HA

    disk_size       = 10
    disk_autoresize = false # Prevent unexpected costs

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = false # Cost saving
    }

    ip_configuration {
      ipv4_enabled = true
      # In production, use private IP with VPC
    }

    user_labels = local.labels
  }

  deletion_protection = false # Set true for production
}

resource "google_sql_database" "database" {
  count = var.enable_database ? 1 : 0

  name     = var.app_name
  instance = google_sql_database_instance.postgres[0].name
}

resource "google_sql_user" "user" {
  count = var.enable_database ? 1 : 0

  name     = var.app_name
  instance = google_sql_database_instance.postgres[0].name
  password = random_password.db_password[0].result
}

resource "random_password" "db_password" {
  count   = var.enable_database ? 1 : 0
  length  = 32
  special = false
}

# Store database URL in Secret Manager
resource "google_secret_manager_secret_version" "database_url" {
  count = var.enable_database ? 1 : 0

  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql://${google_sql_user.user[0].name}:${random_password.db_password[0].result}@/${google_sql_database.database[0].name}?host=/cloudsql/${google_sql_database_instance.postgres[0].connection_name}"
}

# =============================================================================
# CLOUD BUILD - DISABLED (using GitHub Actions instead for free minutes)
# =============================================================================

# Cloud Build trigger commented out - we use GitHub Actions + GCP self-hosted runner
# for the hybrid approach that uses free GitHub minutes first, then GCP spot instances
#
# resource "google_cloudbuild_trigger" "deploy" {
#   name        = "${var.app_name}-deploy"
#   description = "Deploy ${var.app_name} on push to main"
#
#   github {
#     owner = "UMwai"
#     name  = "biotech-ma-predictor"
#
#     push {
#       branch = "^main$"
#     }
#   }
#
#   filename = "cloudbuild.yaml"
#   included_files = ["src/**", "Dockerfile", "requirements.txt"]
#   depends_on = [google_project_service.apis]
# }

# =============================================================================
# GITHUB SELF-HOSTED RUNNER (OPTIONAL - disabled by default to save costs)
# =============================================================================

module "github_runner" {
  count  = var.enable_github_runner ? 1 : 0
  source = "../../modules/github-runner"

  project_id = var.project_id
  region     = var.region
  zone       = "${var.region}-a"

  github_repo         = "UMwai/biotech-ma-predictor"
  github_runner_token = "" # Placeholder - set via secret manager or TF_VAR_github_runner_token
  machine_type        = "e2-medium"
  spot_instance       = true
  runner_labels       = ["self-hosted", "gcp", "linux"]

  depends_on = [google_project_service.apis]
}
