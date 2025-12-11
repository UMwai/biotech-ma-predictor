# Cloud-agnostic database module interface
# Implementations provided per cloud provider

variable "name" {
  description = "Database instance name"
  type        = string
}

variable "engine" {
  description = "Database engine (postgres, mysql)"
  type        = string
  default     = "postgres"
}

variable "engine_version" {
  description = "Database engine version"
  type        = string
  default     = "15"
}

variable "tier" {
  description = "Instance tier/size"
  type        = string
  default     = "small"  # small, medium, large - mapped per provider
}

variable "storage_gb" {
  description = "Storage size in GB"
  type        = number
  default     = 10
}

variable "database_name" {
  description = "Name of the database to create"
  type        = string
}

variable "high_availability" {
  description = "Enable high availability"
  type        = bool
  default     = false
}

variable "backup_enabled" {
  description = "Enable automated backups"
  type        = bool
  default     = true
}

variable "public_access" {
  description = "Allow public IP access"
  type        = bool
  default     = false
}

variable "labels" {
  description = "Resource labels/tags"
  type        = map(string)
  default     = {}
}

# Outputs defined by provider-specific implementations
output "connection_string" {
  description = "Database connection string"
  value       = ""
  sensitive   = true
}

output "host" {
  description = "Database host"
  value       = ""
}

output "port" {
  description = "Database port"
  value       = 5432
}
