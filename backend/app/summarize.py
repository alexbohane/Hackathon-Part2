"""Simple summarization agent using Mistral API."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from mistralai import Mistral
from pydantic import BaseModel

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO)

MISTRAL_MODEL = "magistral-medium-2509"


class SummarizationRequest(BaseModel):
    """Request model for summarization."""

    markdown: str


class SummarizationResponse(BaseModel):
    """Response model for summarization."""

    summary: str
    poster_url: str | None = None
    event_name: str | None = None
    hackathon_rules: str | None = None


def _extract_text_from_chunks(response_content: str | list) -> str:
    """Extract text content from Mistral's chunk-based response format."""
    if isinstance(response_content, str):
        return response_content

    # Handle list of chunks
    text_parts = []
    for chunk in response_content:
        # Skip ThinkChunk objects (they contain thinking process, not the final response)
        if hasattr(chunk, 'type') and getattr(chunk, 'type', None) == 'thinking':
            continue
        # Handle TextChunk objects - extract the text
        if hasattr(chunk, 'text') and hasattr(chunk, 'type'):
            chunk_type = getattr(chunk, 'type', None)
            chunk_text = getattr(chunk, 'text', None)
            if chunk_type == 'text' and chunk_text:
                text_parts.append(str(chunk_text))
        # Handle chunks with just a text attribute
        elif hasattr(chunk, 'text'):
            chunk_text = getattr(chunk, 'text', None)
            if chunk_text:
                text_parts.append(str(chunk_text))
        # Handle string chunks (fallback)
        elif isinstance(chunk, str):
            text_parts.append(chunk)

    return "\n".join(text_parts).strip()


async def summarize_event_details(markdown: str) -> str:
    """Summarize event details markdown using Mistral API.

    Args:
        markdown: Markdown text containing event details

    Returns:
        Summarized text of the event details

    Raises:
        ValueError: If API key is missing or API call fails
    """
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logging.error("MISTRAL_API_KEY not found in environment variables or .env file")
        raise ValueError("Mistral API key is not configured. Please set MISTRAL_API_KEY in your .env file.")

    client = Mistral(api_key=api_key)

    prompt = (
        "You are an event planning assistant. Summarize the following event details "
        "in a clear, concise format. Focus on the key information: event type, location, "
        "size, budget, marketing plans, and any other important details. "
        "Make the summary professional and easy to read.\n\n"
        f"Event Details:\n{markdown}"
    )

    print("[SummarizeTool] calling Mistral API", {"model": MISTRAL_MODEL})

    try:
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
            combined_text = _extract_text_from_chunks(response_content)
            response_length = len(combined_text)

            if isinstance(response_content, list):
                print("[SummarizeTool] received response (from chunks)", {
                    "response_length": response_length,
                    "num_chunks": len(response_content),
                    "response_preview": combined_text[:100] if combined_text else None
                })
            else:
                print("[SummarizeTool] received response (string)", {
                    "response_length": response_length,
                    "response_preview": combined_text[:100] if combined_text else None
                })

            # Validate that we have meaningful content
            if not combined_text:
                logging.warning("[SummarizeTool] Empty response content from Mistral API")
                raise ValueError("Received empty response from Mistral API.")

            stripped_content = combined_text.strip()
            if not stripped_content or len(stripped_content) < 10:
                logging.warning(f"[SummarizeTool] Response too short or whitespace-only: {repr(stripped_content[:200])}")
                raise ValueError(f"Received invalid response from Mistral API (too short or empty): {repr(stripped_content[:200])}")

            return stripped_content
        else:
            logging.warning("[SummarizeTool] No choices in Mistral API response")
            raise ValueError("No response received from Mistral API.")

    except Exception as exc:
        logging.exception("[SummarizeTool] Failed to summarize event details")
        raise ValueError(f"Unable to summarize event details: {str(exc)}") from exc


async def extract_event_details(markdown: str) -> dict[str, str | None]:
    """Extract structured event details from markdown using Mistral API.

    Args:
        markdown: Markdown text containing event details

    Returns:
        Dictionary with event details: event_name, tagline, location, date, focus, organizer_handle, sponsors
    """
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("Mistral API key is not configured.")

    client = Mistral(api_key=api_key)

    prompt = f"""You are an event planning assistant. Extract structured event details from the following event information.
Return ONLY a valid JSON object with the following structure:
{{
    "event_name": "The name of the event (or null if not specified)",
    "tagline": "A catchy tagline or slogan for the event (or null if not specified)",
    "location": "The venue or location (e.g., 'Station F, Paris' or just 'Paris') (or null if not specified)",
    "date": "The event date in a readable format (e.g., '15 November 2025') (or null if not specified)",
    "focus": "The focus areas or topics (e.g., 'AI, Agents & Automation') (or null if not specified)",
    "organizer_handle": "Organizer name or social media handle (e.g., '@yourusername' or 'Event Organizers') (or null if not specified). Default to '@EventOrganizers' if not found.",
    "sponsors": ["List of sponsor names if any", "or empty list if none"]
}}

Important rules:
- If a field is not specified in the input, use null (for strings) or empty list (for sponsors)
- For event_name, extract the main event name or create a descriptive one based on the event type
- For tagline, create a catchy one if not provided, based on the event type and location
- For date, format it in a readable way like "15 November 2025"
- For organizer_handle, default to "@EventOrganizers" if not found
- Return ONLY the JSON object, no other text

Event Details:
{markdown}
"""

    try:
        chat_response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        if chat_response.choices and len(chat_response.choices) > 0:
            response_content = chat_response.choices[0].message.content
            response_text = _extract_text_from_chunks(response_content)

            # Extract JSON from response (might have markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                event_details = json.loads(json_str)

                # Ensure all required fields exist with defaults
                return {
                    "event_name": event_details.get("event_name"),
                    "tagline": event_details.get("tagline"),
                    "location": event_details.get("location"),
                    "date": event_details.get("date"),
                    "focus": event_details.get("focus"),
                    "organizer_handle": event_details.get("organizer_handle") or "@EventOrganizers",
                    "sponsors": event_details.get("sponsors", []),
                }
            else:
                logging.warning("[ExtractEventDetails] No JSON found in response")
                return {
                    "event_name": None,
                    "tagline": None,
                    "location": None,
                    "date": None,
                    "focus": None,
                    "organizer_handle": "@EventOrganizers",
                    "sponsors": [],
                }
        else:
            logging.warning("[ExtractEventDetails] No choices in Mistral API response")
            return {
                "event_name": None,
                "tagline": None,
                "location": None,
                "date": None,
                "focus": None,
                "organizer_handle": "@EventOrganizers",
                "sponsors": [],
            }

    except Exception as exc:
        logging.exception("[ExtractEventDetails] Failed to extract event details")
        # Return defaults on error
        return {
            "event_name": None,
            "tagline": None,
            "location": None,
            "date": None,
            "focus": None,
            "organizer_handle": "@EventOrganizers",
            "sponsors": [],
        }


async def generate_hackathon_rules(markdown: str) -> str:
    """Generate hackathon rules in Notion-style markdown using Mistral API.

    Args:
        markdown: Markdown text containing event details

    Returns:
        Notion-style markdown with hackathon rules

    Raises:
        ValueError: If API key is missing or API call fails
    """
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logging.error("MISTRAL_API_KEY not found in environment variables or .env file")
        raise ValueError("Mistral API key is not configured. Please set MISTRAL_API_KEY in your .env file.")

    client = Mistral(api_key=api_key)

    prompt = f"""You are an event planning assistant. Create comprehensive hackathon rules in Notion-style markdown format based on the following event details.

The output should be well-structured Notion-style markdown with:
- Headings using #, ##, ###
- Bullet points and numbered lists
- Bold text for important terms
- Clear sections for different rule categories

Include sections for:
1. Event Overview
2. Eligibility & Participation Rules
3. Submission Guidelines
4. Judging Criteria
5. Code of Conduct
6. Prizes & Rewards (if applicable)
7. Timeline & Important Dates
8. Team Formation Rules (if applicable)
9. Intellectual Property & Ownership
10. Contact & Support

Make the rules professional, clear, and comprehensive. Base them on the event details provided, but make them general enough for a hackathon if specific details are missing.

Event Details:
{markdown}

Return ONLY the Notion-style markdown content, no additional explanation or wrapper text.
"""

    print("[HackathonRulesTool] calling Mistral API", {"model": MISTRAL_MODEL})

    try:
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
            rules_text = _extract_text_from_chunks(response_content)

            if isinstance(response_content, list):
                print("[HackathonRulesTool] received response (from chunks)", {
                    "response_length": len(rules_text),
                    "num_chunks": len(response_content),
                })
            else:
                print("[HackathonRulesTool] received response (string)", {
                    "response_length": len(rules_text),
                })

            # Validate that we have meaningful content
            if not rules_text:
                logging.warning("[HackathonRulesTool] Empty response content from Mistral API")
                raise ValueError("Received empty response from Mistral API.")

            stripped_text = rules_text.strip()
            if not stripped_text or len(stripped_text) < 50:
                logging.warning(f"[HackathonRulesTool] Response too short: {repr(stripped_text[:200])}")
                raise ValueError(f"Received invalid response from Mistral API (too short): {repr(stripped_text[:200])}")

            return stripped_text
        else:
            logging.warning("[HackathonRulesTool] No choices in Mistral API response")
            raise ValueError("No response received from Mistral API.")

    except Exception as exc:
        logging.exception("[HackathonRulesTool] Failed to generate hackathon rules")
        raise ValueError(f"Unable to generate hackathon rules: {str(exc)}") from exc

