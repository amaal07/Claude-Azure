terraform {
  required_version = ">= 1.3.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "AmalRG"
    storage_account_name = "tfstateamal"
    container_name       = "tfstate"
    key                  = "claude-azure.tfstate"
  }
}

provider "azurerm" {
  features {}
}