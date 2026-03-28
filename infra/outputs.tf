output "app_url" {
  description = "Public URL of the deployed container app"
  value       = "http://${azurerm_container_group.app.fqdn}:8000"
}

output "app_ip" {
  description = "Public IP of the container instance"
  value       = azurerm_container_group.app.ip_address
}

output "app_fqdn" {
  description = "Fully qualified domain name of the container"
  value       = azurerm_container_group.app.fqdn
}

output "acr_login_server" {
  description = "ACR login server hostname"
  value       = azurerm_container_registry.acr.login_server
}

output "acr_admin_username" {
  description = "ACR admin username (used in CI/CD)"
  value       = azurerm_container_registry.acr.admin_username
  sensitive   = true
}

output "acr_admin_password" {
  description = "ACR admin password (used in CI/CD)"
  value       = azurerm_container_registry.acr.admin_password
  sensitive   = true
}

output "container_group_name" {
  description = "Azure Container Instance group name"
  value       = azurerm_container_group.app.name
}