variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "biotech-ma-predictor"
}

variable "notification_email" {
  description = "Email for budget alerts and notifications"
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget in USD"
  type        = number
  default     = 200
}

variable "db_tier" {
  description = "Cloud SQL tier (cost-conscious default)"
  type        = string
  default     = "db-f1-micro" # Free tier eligible, ~$7/month if always on
}

variable "enable_database" {
  description = "Enable Cloud SQL (set false to save costs during dev)"
  type        = bool
  default     = false
}

variable "container_cpu" {
  description = "CPU for Cloud Run"
  type        = string
  default     = "1"
}

variable "container_memory" {
  description = "Memory for Cloud Run"
  type        = string
  default     = "512Mi"
}

variable "enable_github_runner" {
  description = "Enable GitHub self-hosted runner (set false to save costs)"
  type        = bool
  default     = false
}
