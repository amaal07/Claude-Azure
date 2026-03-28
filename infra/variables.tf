variable "resource_group_name" {
  description = "Name of the existing Azure Resource Group"
  type        = string
  default     = "AmalRG"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "app_name" {
  description = "Base name for the application resources"
  type        = string
  default     = "stock-predictor"
}

variable "acr_name" {
  description = "Azure Container Registry name (globally unique, 5-50 chars, lowercase alphanumeric only)"
  type        = string
  default     = "stockpredictorregistry"
}