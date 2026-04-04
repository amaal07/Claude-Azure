# Install the SDK: pip install azure-ai-projects azure-identity
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Replace with your actual values from Azure portal
client = AIProjectClient(
    endpoint="https://amalaifoundry.services.ai.azure.com/api/projects/proj-default",
    credential=DefaultAzureCredential()
)

# Verify connection by listing available connections
connections = list(client.connections.list())
print(f"Successfully connected to Azure AI Foundry. Found {len(connections)} connection(s).")