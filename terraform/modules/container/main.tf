# Cloud-agnostic container module interface
# Implementations provided per cloud provider

variable "name" {
  description = "Service name"
  type        = string
}

variable "image" {
  description = "Container image URL"
  type        = string
}

variable "port" {
  description = "Container port"
  type        = number
  default     = 8000
}

variable "cpu" {
  description = "CPU allocation (e.g., '1' or '1000m')"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory allocation (e.g., '512Mi', '1Gi')"
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Minimum number of instances (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 2
}

variable "env_vars" {
  description = "Environment variables"
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Secret references (name -> secret_id)"
  type        = map(string)
  default     = {}
}

variable "labels" {
  description = "Resource labels/tags"
  type        = map(string)
  default     = {}
}

# Outputs defined by provider-specific implementations
output "url" {
  description = "Service URL"
  value       = ""
}

output "service_id" {
  description = "Service identifier"
  value       = ""
}
