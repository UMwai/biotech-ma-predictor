output "cloud_run_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.app.uri
}

output "artifact_registry_url" {
  description = "Artifact Registry URL for Docker images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "storage_bucket" {
  description = "Cloud Storage bucket name"
  value       = google_storage_bucket.data.name
}

output "database_instance" {
  description = "Cloud SQL instance name (if enabled)"
  value       = var.enable_database ? google_sql_database_instance.postgres[0].name : "disabled"
}

output "database_connection_name" {
  description = "Cloud SQL connection name for Cloud Run"
  value       = var.enable_database ? google_sql_database_instance.postgres[0].connection_name : "disabled"
}

output "service_account_email" {
  description = "Cloud Run service account"
  value       = google_service_account.cloud_run.email
}

output "budget_name" {
  description = "Budget display name"
  value       = google_billing_budget.monthly_budget.display_name
}

output "github_runner_instance_group" {
  description = "GitHub runner instance group name (if enabled)"
  value       = var.enable_github_runner ? module.github_runner[0].runner_instance_group : "disabled"
}

output "github_runner_service_account" {
  description = "GitHub runner service account email (if enabled)"
  value       = var.enable_github_runner ? module.github_runner[0].runner_service_account : "disabled"
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost breakdown"
  value       = <<-EOT

    Estimated Monthly Costs (USD):
    ==============================
    Cloud Run (scale to zero):     ~$0-15 (pay per request)
    Artifact Registry:             ~$0.10/GB stored
    Cloud Storage:                 ~$0.02/GB/month
    Secret Manager:                ~$0.06/secret/month
    Cloud SQL (if enabled):        ~$7-25/month (db-f1-micro)
    GitHub Runner (if enabled):    ~$5-7/month (e2-medium spot)

    Budget Alert Set:              $${var.budget_amount}/month
    Free Tier Credits:             $300 (90 days)

    Tips to minimize costs:
    - Keep min_instance_count = 0 (scale to zero)
    - Disable Cloud SQL during dev (use local DB)
    - Disable GitHub Runner until needed
    - Delete unused container images
    - Review spending daily via email alerts
  EOT
}
