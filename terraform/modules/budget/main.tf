# Cloud-agnostic budget module interface
# Implementations provided per cloud provider

variable "name" {
  description = "Budget name"
  type        = string
}

variable "amount" {
  description = "Budget amount in USD"
  type        = number
}

variable "currency" {
  description = "Currency code"
  type        = string
  default     = "USD"
}

variable "alert_thresholds" {
  description = "Percentage thresholds for alerts (0.0 to 1.0)"
  type        = list(number)
  default     = [0.25, 0.5, 0.75, 0.9, 1.0]
}

variable "notification_emails" {
  description = "Email addresses for budget alerts"
  type        = list(string)
}

variable "time_period" {
  description = "Budget time period (monthly, quarterly, yearly)"
  type        = string
  default     = "monthly"
}

variable "services_filter" {
  description = "Specific services to track (empty = all)"
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Resource labels/tags to filter"
  type        = map(string)
  default     = {}
}

# Outputs defined by provider-specific implementations
output "budget_id" {
  description = "Budget identifier"
  value       = ""
}
