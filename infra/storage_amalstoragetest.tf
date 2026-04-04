resource "azurerm_storage_account" "amalstoragetest" {
  name                     = "amalstoragetest"
  resource_group_name      = "AmalRG"
  location                 = "eastus"
  account_tier             = "Standard"
  account_replication_type = "LRS"
}