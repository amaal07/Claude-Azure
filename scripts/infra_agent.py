import subprocess, json, requests, os, sys

LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://localhost:1234/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "mistral-7b-instruct-v0.1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

SYSTEM_PROMPT = """You are an Azure infrastructure assistant using Terraform.

For CREATE requests (new resources like VMs, storage, etc.), respond with JSON:
{
  "action": "terraform",
  "filename": "infra/<resource_name>.tf",
  "code": "<full valid Terraform HCL code>"
}

For other operations respond with JSON:
{"action": "run", "command": "<terraform command>"}

Terraform operation examples:
- destroy: {"action": "run", "command": "terraform -chdir=infra destroy -auto-approve"}
- plan:    {"action": "run", "command": "terraform -chdir=infra plan"}
- show:    {"action": "run", "command": "terraform -chdir=infra show"}
- init:    {"action": "run", "command": "terraform -chdir=infra init"}

Rules:
- action must be "terraform" for new resource creation, "run" for everything else
- For VM creation always use azurerm_linux_virtual_machine with Ubuntu 22.04
- Always include required dependencies (vnet, subnet, nic) in the same file
- Use tls_private_key for SSH key generation
- Use Standard_B1s size for test VMs
- Use resource_group_name = "AmalRG" and location = "eastus"
- NEVER include terraform{} block or provider{} block in generated code — they already exist in providers.tf
- Only include resource blocks in the generated code
- Only respond with JSON, no explanation

Example for create test VM:
{
  "action": "terraform",
  "filename": "infra/vm.tf",
  "code": "terraform {\\n  required_providers {\\n    tls = { source = \\"hashicorp/tls\\" }\\n  }\\n}\\n\\nresource \\"azurerm_virtual_network\\" \\"vm_vnet\\" {\\n  name = \\"vm-vnet\\"\\n  address_space = [\\"10.0.0.0/16\\"]\\n  location = \\"eastus\\"\\n  resource_group_name = \\"AmalRG\\"\\n}\\n\\nresource \\"azurerm_subnet\\" \\"vm_subnet\\" {\\n  name = \\"vm-subnet\\"\\n  resource_group_name = \\"AmalRG\\"\\n  virtual_network_name = azurerm_virtual_network.vm_vnet.name\\n  address_prefixes = [\\"10.0.1.0/24\\"]\\n}\\n\\nresource \\"azurerm_network_interface\\" \\"vm_nic\\" {\\n  name = \\"vm-nic\\"\\n  location = \\"eastus\\"\\n  resource_group_name = \\"AmalRG\\"\\n  ip_configuration {\\n    name = \\"internal\\"\\n    subnet_id = azurerm_subnet.vm_subnet.id\\n    private_ip_address_allocation = \\"Dynamic\\"\\n  }\\n}\\n\\nresource \\"tls_private_key\\" \\"vm_key\\" {\\n  algorithm = \\"RSA\\"\\n  rsa_bits = 4096\\n}\\n\\nresource \\"azurerm_linux_virtual_machine\\" \\"test_vm\\" {\\n  name = \\"test-vm\\"\\n  resource_group_name = \\"AmalRG\\"\\n  location = \\"eastus\\"\\n  size = \\"Standard_B1s\\"\\n  admin_username = \\"azureuser\\"\\n  network_interface_ids = [azurerm_network_interface.vm_nic.id]\\n  admin_ssh_key {\\n    username = \\"azureuser\\"\\n    public_key = tls_private_key.vm_key.public_key_openssh\\n  }\\n  os_disk {\\n    caching = \\"ReadWrite\\"\\n    storage_account_type = \\"Standard_LRS\\"\\n  }\\n  source_image_reference {\\n    publisher = \\"Canonical\\"\\n    offer = \\"0001-com-ubuntu-server-jammy\\"\\n    sku = \\"22_04-lts\\"\\n    version = \\"latest\\"\\n  }\\n}"
}"""

history = [{"role": "system", "content": SYSTEM_PROMPT}]


def ask_llm(user_input):
    history.append({"role": "user", "content": user_input})
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"} if LLM_API_KEY else {}
    res = requests.post(LLM_ENDPOINT, headers=headers, json={
        "model": MODEL,
        "messages": history,
        "stream": False,
        "temperature": 0.2
    })
    reply = res.json()["choices"][0]["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    return reply


def clean_tf_code(code):
    """Remove terraform{} and provider{} blocks — they already exist in providers.tf."""
    result = []
    skip = False
    depth = 0

    for line in code.splitlines():
        stripped = line.strip()
        if not skip and depth == 0 and (
            stripped.startswith('terraform {') or
            stripped.startswith('terraform{') or
            stripped.startswith('provider "') or
            stripped.startswith("provider '")
        ):
            skip = True

        if skip:
            depth += stripped.count('{') - stripped.count('}')
            if depth <= 0:
                skip = False
                depth = 0
            continue

        result.append(line)

    cleaned = '\n'.join(result).strip()
    print(f"\n[DEBUG] Cleaned TF code:\n{cleaned}\n")
    return cleaned


def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        raise Exception(f"Command failed (exit {result.returncode}): {cmd}")
    return result.stdout


def git_commit_push(filename):
    run_command("git config user.email 'infra-agent@github-actions'")
    run_command("git config user.name 'Infra Agent'")
    run_command(f"git add {filename}")
    run_command(f"git commit -m 'infra: add {filename} generated by LLM'")
    output = run_command("git push")
    print(output)


def process_prompt(user_prompt, auto_execute=False):
    reply = ask_llm(user_prompt)
    try:
        action = json.loads(reply)

        if action.get("action") == "terraform":
            filename = action.get("filename")
            code = clean_tf_code(action.get("code"))

            print(f"\n Generated file: {filename}")
            print(f"\n Terraform code:\n{code}")

            if auto_execute:
                # Step 1: Write generated TF code to infra/ folder
                with open(filename, "w") as f:
                    f.write(code)
                print(f"\n[1/3] Written to {filename}")

                # Step 2: Run terraform init + apply
                print(f"\n[2/3] Running terraform init...")
                run_command("terraform -chdir=infra init")
                print(f"\n[2/3] Running terraform apply...")
                run_command("terraform -chdir=infra apply -auto-approve")
                print(f"\n[2/3] Resource created in Azure.")

                # Step 3: Commit and push to repo only after successful apply
                print(f"\n[3/3] Committing {filename} to repo...")
                git_commit_push(filename)
                print(f"\n[3/3] Done.")
            else:
                confirm = input("Write file, commit to repo and apply? (y/n): ")
                if confirm == "y":
                    with open(filename, "w") as f:
                        f.write(code)
                    print(f"\n[1/3] Written to {filename}")
                    git_commit_push(filename)
                    print(f"\n[2/3] Committed to repo")
                    print(f"\n[3/3] Running terraform init...")
                    run_command("terraform -chdir=infra init")
                    print(f"\n[3/3] Running terraform apply...")
                    run_command("terraform -chdir=infra apply -auto-approve")

        elif action.get("action") in ("run", "delete", "create", "list"):
            print(f"\n Running: {action['command']}")
            if auto_execute:
                output = run_command(action["command"])
                print(output)
                return output
            else:
                confirm = input("Execute? (y/n): ")
                if confirm == "y":
                    output = run_command(action["command"])
                    print(output)
                    return output

    except json.JSONDecodeError:
        print(f"\nAssistant: {reply}")
    return reply


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Non-interactive mode: prompt passed as CLI argument (used by GitHub Actions)
        prompt = " ".join(sys.argv[1:])
        process_prompt(prompt, auto_execute=True)
    else:
        # Interactive mode
        while True:
            user = input("\nYou: ")
            if user.lower() in ("exit", "quit"):
                break
            process_prompt(user, auto_execute=False)