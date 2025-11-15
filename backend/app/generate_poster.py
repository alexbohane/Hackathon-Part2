"""Tool for generating event posters using fal.ai API."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import fal_client
from agents import RunContextWrapper, function_tool
from chatkit.agents import ClientToolCall
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
from uuid import uuid4

# Import FactAgentContext for type hints
from .chat import FactAgentContext  # noqa: F401

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# If you want to check what's going on under the hood, set this to DEBUG
logging.basicConfig(level=logging.INFO)

FAL_MODEL = "fal-ai/nano-banana"


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


async def generate_poster_image(
    event_name: str,
    tagline: str,
    location: str,
    date: str,
    focus: str,
    organizer_handle: str,
    sponsors: list[str] | None = None,
    skip_tts: bool = False,
) -> dict[str, str]:
    """Generate an event poster using fal.ai image generation API.

    This is a helper function that can be called without ChatKit context.

    Args:
        event_name: Name of the event (e.g., "Paris AI Hackathon")
        tagline: Event tagline (e.g., "Build the next one-person unicorn")
        location: Venue (e.g., "Station F, Paris")
        date: Event date (e.g., "15 November 2025")
        focus: Event focus areas (e.g., "AI, Agents & Automation")
        organizer_handle: Social media handle or organizer name (e.g., "@yourusername")
        sponsors: List of sponsor names (optional)
        skip_tts: If True, skip the TTS announcement (useful for API calls)

    Returns:
        Dictionary with event_name, image_url, and message

    Raises:
        ValueError: If API key is missing or generation fails
    """
    print("[PosterGenHelper] generating poster", {
        "event_name": event_name,
        "location": location,
        "date": date
    })

    try:
        # Get FAL API key from environment
        api_key = os.environ.get("FAL_API_KEY")
        if not api_key:
            logging.error("FAL_KEY not found in environment variables or .env file")
            raise ValueError("FAL API key is not configured. Please set FAL_KEY in your .env file.")

        # Set the FAL API key for the client
        os.environ["FAL_KEY"] = api_key

        # Generate the poster prompt
        poster_prompt = generate_poster_prompt(
            event_name=event_name,
            tagline=tagline,
            location=location,
            date=date,
            focus=focus,
            organizer_handle=organizer_handle,
            sponsors=sponsors
        )

        # Turn the JSON into a single text prompt (most image models expect plain text)
        prompt_text = (
            "Design a marketing poster based on this JSON description:\n\n"
            + json.dumps(json.loads(poster_prompt), indent=2)
        )

        print("[PosterGenHelper] calling fal.ai API", {
            "model": FAL_MODEL,
            "event_name": event_name
        })

        # Call fal.ai to generate the image
        result = fal_client.subscribe(
            FAL_MODEL,
            arguments={
                "prompt": prompt_text
            }
        )

        # Extract the image URL
        if result and "images" in result and len(result["images"]) > 0:
            image_url = result["images"][0]["url"]
            print("[PosterGenHelper] received image URL", {
                "url": image_url[:100] + "..." if len(image_url) > 100 else image_url
            })

            # Play ElevenLabs TTS announcement (unless skipped)
            if not skip_tts:
                try:
                    elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
                    if elevenlabs_api_key:
                        elevenlabs = ElevenLabs(api_key=elevenlabs_api_key)
                        audio = elevenlabs.text_to_speech.convert(
                            text=f"Successfully generated poster for '{event_name}'",
                            voice_id="JBFqnCBsd6RMkjVDRZzb",
                            model_id="eleven_multilingual_v2",
                            output_format="mp3_44100_128",
                        )
                        play(audio)
                    else:
                        logging.warning("ELEVENLABS_API_KEY not found, skipping TTS")
                except Exception as tts_exc:
                    logging.warning(f"Failed to play TTS: {str(tts_exc)}")

            return {
                "event_name": event_name,
                "image_url": image_url,
                "message": f"Successfully generated poster for '{event_name}'",
            }
        else:
            logging.warning("[PosterGenHelper] No images in fal.ai API response")
            raise ValueError("No image received from fal.ai API.")

    except Exception as exc:
        logging.exception("[PosterGenHelper] Failed to generate poster")
        raise ValueError(f"Unable to generate poster: {str(exc)}") from exc


def generate_poster_prompt(
    event_name: str|None,
    tagline: str|None,
    location: str|None,
    date: str|None,
    focus: str|None,
    organizer_handle: str|None,
    sponsors: list[str] = None
) -> str:
    """
    Generate a poster image generation prompt with custom event details.

    Args:
        event_name: Name of the event (e.g., "Paris AI Hackathon")
        tagline: Event tagline (e.g., "Build the next one-person unicorn")
        location: Venue (e.g., "Station F, Paris")
        date: Event date (e.g., "15 November 2025")
        focus: Event focus areas (e.g., "AI, Agents & Automation")
        organizer_handle: Social media handle or organizer name (e.g., "@yourusername")
        sponsors: List of sponsor names (optional, defaults to example sponsors)

    Returns:
        Formatted prompt string with all variables interpolated
    """

    return f"""{{
  "title": "{event_name}",
  "overall_style": {{
    "vibe": "futuristic, clean, high-contrast, tech event poster",
    "color_palette": [
      "#000000",
      "#0b1020",
      "#5b5bff",
      "#a855f7",
      "#ffffff"
    ],
    "mood_keywords": [
      "innovative",
      "energetic",
      "night-city",
      "AI-powered",
      "professional but playful"
    ],
    "design_references": [
      "modern startup conference",
      "AI lab branding",
      "gradient neon accents on dark background"
    ]
  }},
  "composition": {{
    "background": {{
      "description": "Dark night-sky gradient with subtle digital dots or matrix pattern, abstract city skyline silhouette in the lower third, faint outline of an iconic city landmark ({location}) in the center-right, soft glow behind it.",
      "elements": [
        "soft radial glow behind main text",
        "tiny scattered particles suggesting data or neural networks",
        "no busy details that distract from typography"
      ]
    }},
    "foreground": {{
      "main_heading": {{
        "text": "{event_name}",
        "layout": "Top-left or center-left, two lines, big bold sans-serif",
        "style": {{
          "font": "bold geometric sans-serif",
          "size": "very large",
          "color": "#ffffff",
          "emphasis_word": {{
            "word": "{event_name}",
            "color": "#a855f7",
            "effect": "slight glow or gradient"
          }}
        }}
      }},
      "tagline": {{
        "text": "{tagline}",
        "position": "below main heading",
        "style": {{
          "font": "monospace or light sans-serif",
          "size": "medium",
          "color": "#d1d5db"
        }}
      }},
      "event_details_block": {{
        "position": "left or center, below tagline",
        "items": [
          {{
            "label": "Location",
            "value": "{location}"
          }},
          {{
            "label": "Date",
            "value": "{date}"
          }},
          {{
            "label": "Focus",
            "value": "{focus}"
          }}
        ],
        "style": {{
          "label_color": "#9ca3af",
          "value_color": "#ffffff",
          "font": "clean sans-serif",
          "layout": "left-aligned stacked list"
        }}
      }},
      "partners_section": {{
        "heading_text": "our partners",
        "position": "bottom-left",
        "style": {{
          "font": "monospace or small caps",
          "color": "#9ca3af",
          "size": "small"
        }},
        "logos_style": {{
          "description": "Row of simple white or light-gray logotype placeholders, evenly spaced, all same height.",
          "example_partner_names": {json.dumps(sponsors if sponsors else [])},
          "note": "Do NOT use logos, just text labels."
        }}
      }},
      "organizer_handle": {{
        "text": "by {organizer_handle}",
        "position": "top-right or bottom-right",
        "style": {{
          "font": "small sans-serif",
          "color": "#9ca3af"
        }}
      }}
    }}
  }},
  "image_model_instructions": {{
    "aspect_ratio": "4:5 vertical poster",
    "render_quality": "high resolution, sharp typography",
    "avoid": [
      "crowded text",
      "cartoonish style",
      "clip-art",
      "overly bright background"
    ]
  }}
}}"""


@function_tool(
    description_override="Generate a professional event poster image. Once that all details about an event is defined like event name, tagline, location, date, focus areas, and sponsors. THEN and ONLY THEN use this tool to generate a poster for the event."
)
async def generate_poster(
    ctx: RunContextWrapper[FactAgentContext],  # type: ignore[name-defined]
    event_name: str,
    tagline: str,
    location: str,
    date: str,
    focus: str,
    organizer_handle: str,
    sponsors: list[str] | None = None,
) -> dict[str, str] | None:
    """Generate an event poster using fal.ai image generation API."""
    print("[PosterGenTool] tool invoked", {
        "event_name": event_name,
        "location": location,
        "date": date
    })

    # Use the helper function
    return await generate_poster_image(
        event_name=event_name,
        tagline=tagline,
        location=location,
        date=date,
        focus=focus,
        organizer_handle=organizer_handle,
        sponsors=sponsors,
        skip_tts=False,  # Keep TTS for ChatKit tool calls
    )