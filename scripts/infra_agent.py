import subprocess, json, requests, os, sys

LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://localhost:1234/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "mistral-7b-instruct-v0.1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

SYSTEM_PROMPT = """You are an Azure infrastructure assistant using Terraform. You MUST respond with ONLY a valid JSON object. No explanation, no markdown, no extra text.

Always use this exact format:
{"action": "run", "command": "<full terraform command>"}

Rules:
- action must always be "run"
- command must be a complete, valid Terraform CLI command
- Always use -chdir=infra to point to the infra directory
- For deploying/creating resources use: terraform -chdir=infra apply -auto-approve
- For destroying resources use: terraform -chdir=infra destroy -auto-approve
- For planning changes use: terraform -chdir=infra plan
- For listing/showing state use: terraform -chdir=infra show
- For initialising use: terraform -chdir=infra init
- Always close the JSON properly with double quotes and curly brace

Examples:
User: deploy resources -> {"action": "run", "command": "terraform -chdir=infra apply -auto-approve"}
User: destroy resources -> {"action": "run", "command": "terraform -chdir=infra destroy -auto-approve"}
User: plan changes -> {"action": "run", "command": "terraform -chdir=infra plan"}
User: show state -> {"action": "run", "command": "terraform -chdir=infra show"}
User: init terraform -> {"action": "run", "command": "terraform -chdir=infra init"}"""

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


def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout or result.stderr


def process_prompt(user_prompt, auto_execute=False):
    reply = ask_llm(user_prompt)
    try:
        action = json.loads(reply)
        if action.get("action") in ("run", "delete", "create", "list"):
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