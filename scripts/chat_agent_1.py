import asyncio
import httpx
import os

from openai import AsyncOpenAI
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, OpenAIChatPromptExecutionSettings
from semantic_kernel.contents.chat_history import ChatHistory


def build_kernel() -> Kernel:
    kernel = Kernel()

    openai_client = AsyncOpenAI(
        api_key=os.environ.get("LLM_API_KEY", ""),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        http_client=httpx.AsyncClient(verify=False),
    )

    kernel.add_service(
        OpenAIChatCompletion(
            service_id="chat",
            ai_model_id=os.environ.get("LLM_MODEL", "gpt-4o"),
            async_client=openai_client,
        )
    )

    return kernel


async def run():
    kernel = build_kernel()
    chat_history = ChatHistory()
    chat_history.add_system_message("You are a helpful assistant.")

    settings = OpenAIChatPromptExecutionSettings(
        service_id="chat",
        temperature=0.5,
    )

    chat_service = kernel.get_service("chat")
    print("Chat Agent ready. Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break

        chat_history.add_user_message(user_input)

        response = await chat_service.get_chat_message_content(
            chat_history=chat_history,
            settings=settings,
            kernel=kernel,
        )

        print(f"\nAgent: {response}\n")
        chat_history.add_assistant_message(str(response))


if __name__ == "__main__":
    asyncio.run(run())
