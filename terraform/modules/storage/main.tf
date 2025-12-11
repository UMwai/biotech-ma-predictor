# Cloud-agnostic storage module interface
# Implementations provided per cloud provider

variable "name" {
  description = "Bucket/container name"
  type        = string
}

variable "location" {
  description = "Storage location/region"
  type        = string
}

variable "storage_class" {
  description = "Storage class (standard, nearline, coldline, archive)"
  type        = string
  default     = "standard"
}

variable "versioning_enabled" {
  description = "Enable object versioning"
  type        = bool
  default     = false
}

variable "lifecycle_rules" {
  description = "Lifecycle rules for automatic deletion/transition"
  type = list(object({
    age_days      = number
    action        = string  # delete, transition
    storage_class = optional(string)
  }))
  default = []
}

variable "public_access" {
  description = "Allow public access"
  type        = bool
  default     = false
}

variable "cors_origins" {
  description = "CORS allowed origins"
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Resource labels/tags"
  type        = map(string)
  default     = {}
}

# Outputs defined by provider-specific implementations
output "bucket_name" {
  description = "Bucket name"
  value       = ""
}

output "bucket_url" {
  description = "Bucket URL"
  value       = ""
}
