"""Tool for answering questions about Paris using Mistral API."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from agents import RunContextWrapper, function_tool
from dotenv import load_dotenv
from mistralai import Mistral

# Import FactAgentContext for type hints
# This creates a circular import, but Python handles it gracefully
# since we only use it in type annotations
from .chat import FactAgentContext  # noqa: F401

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# If you want to check what's going on under the hood, set this to DEBUG
logging.basicConfig(level=logging.INFO)

MISTRAL_MODEL = "magistral-medium-2509"


@function_tool(
    description_override="Get information about Paris, France. Use this tool when the user asks questions about Paris, including its history, culture, landmarks, food, or any other topics related to the city."
)
async def paris_fact(
    ctx: RunContextWrapper[FactAgentContext],  # type: ignore[name-defined]
    question: str,
) -> dict[str, str] | None:
    """Retrieve information about Paris using the Mistral API."""
    print("[ParisTool] tool invoked", {"question": question})

    try:
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            logging.error("MISTRAL_API_KEY not found in environment variables or .env file")
            raise ValueError("Mistral API key is not configured. Please set MISTRAL_API_KEY in your .env file.")

        client = Mistral(api_key=api_key)

        # Construct a prompt that focuses on Paris
        prompt = f"Answer the following question about Paris, France: {question}"

        print("[ParisTool] calling Mistral API", {"model": MISTRAL_MODEL, "question": question})

        chat_response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        # Extract the response content
        if chat_response.choices and len(chat_response.choices) > 0:
            response_content = chat_response.choices[0].message.content
            print("[ParisTool] received response", {"response_length": len(response_content) if response_content else 0})

            return {
                "question": question,
                "answer": response_content or "No response received from Mistral API.",
            }
        else:
            logging.warning("[ParisTool] No choices in Mistral API response")
            raise ValueError("No response received from Mistral API.")

    except Exception as exc:
        logging.exception("[ParisTool] Failed to get Paris information")
        raise ValueError(f"Unable to retrieve information about Paris: {str(exc)}") from exc

