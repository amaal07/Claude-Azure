import subprocess, json, requests, os, sys

LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

SYSTEM_PROMPT = """You are an Azure infrastructure assistant using Terraform. You can create, manage and destroy ANY Azure resource.

For CREATE/UPDATE requests respond with JSON:
{
  "action": "terraform",
  "filename": "infra/<descriptive_resource_name>.tf",
  "code": "<full valid Terraform HCL resource blocks only>"
}

For DESTROY/PLAN/SHOW/OTHER operations respond with JSON:
{
  "action": "run",
  "command": "<full terraform command>"
}

STRICT RULES — follow exactly:
1. NEVER include terraform{} or provider{} blocks in code — they already exist in providers.tf
2. NEVER include required_providers{} blocks — already declared
3. Only include resource{} and data{} blocks in the code field
4. Always use resource_group_name = "AmalRG" and location = "eastus" unless user specifies otherwise
5. Always include ALL required dependent resources in the same file (e.g. vnet+subnet+nic for a VM)
6. For destroy, always use -target for each resource address — never destroy all resources at once
7. For destroy, derive resource addresses from the resource type and name used in the create code
8. action must be "terraform" for create/update, "run" for everything else
9. Only respond with valid JSON — no explanation, no markdown, no extra text

RESOURCE-SPECIFIC RULES:
- VM: use azurerm_linux_virtual_machine, Ubuntu 22_04-lts, Standard_B1s, include vnet+subnet+nic+tls_private_key
- Storage Account: use azurerm_storage_account, Standard tier, LRS replication
- AKS: use azurerm_kubernetes_cluster, include azurerm_resource_group if needed, system node pool
- SQL: use azurerm_mssql_server + azurerm_mssql_database, include random_password for admin
- Key Vault: use azurerm_key_vault, include data.azurerm_client_config for tenant_id
- App Service: use azurerm_service_plan + azurerm_linux_web_app
- Container Instance: use azurerm_container_group
- Any other resource: use the correct azurerm_* resource type with all required fields

Examples:
- create storage account: {"action": "terraform", "filename": "infra/storage.tf", "code": "resource \\"azurerm_storage_account\\" \\"storage\\" {\\n  name = \\"amalstorageacct\\"\\n  resource_group_name = \\"AmalRG\\"\\n  location = \\"eastus\\"\\n  account_tier = \\"Standard\\"\\n  account_replication_type = \\"LRS\\"\\n}"}
- destroy storage account: {"action": "run", "command": "terraform -chdir=infra destroy -target=azurerm_storage_account.storage -auto-approve"}
- plan: {"action": "run", "command": "terraform -chdir=infra plan"}
- show state: {"action": "run", "command": "terraform -chdir=infra show"}"""

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


def extract_targets(code):
    """Extract resource addresses from Terraform HCL code for use with -target flag."""
    import re
    targets = []
    for match in re.finditer(r'resource\s+"([^"]+)"\s+"([^"]+)"', code):
        targets.append(f"{match.group(1)}.{match.group(2)}")
    return targets


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

                # Step 2: Run terraform init + apply (target only resources in generated file)
                targets = extract_targets(code)
                target_flags = " ".join(f"-target={t}" for t in targets)
                print(f"\n[2/3] Running terraform init...")
                run_command("terraform -chdir=infra init")
                print(f"\n[2/3] Running terraform apply targeting: {targets}")
                run_command(f"terraform -chdir=infra apply {target_flags} -auto-approve")
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
            command = action["command"]
            print(f"\n Running: {command}")
            if auto_execute:
                run_command("terraform -chdir=infra init")
                run_command(command)
            else:
                confirm = input("Execute? (y/n): ")
                if confirm == "y":
                    run_command("terraform -chdir=infra init")
                    run_command(command)

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