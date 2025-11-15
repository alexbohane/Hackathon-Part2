"""FastAPI entrypoint wiring the ChatKit server and REST endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from chatkit.server import StreamingResult
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from starlette.responses import JSONResponse

from .chat import (
    FactAssistantServer,
    create_chatkit_server,
)
from .facts import fact_store
from .generate_poster import generate_poster_image
from .summarize import (
    SummarizationRequest,
    SummarizationResponse,
    extract_event_details,
    generate_hackathon_rules,
    summarize_event_details,
)

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

app = FastAPI(title="ChatKit API")

_chatkit_server: FactAssistantServer | None = create_chatkit_server()


def get_chatkit_server() -> FactAssistantServer:
    if _chatkit_server is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ChatKit dependencies are missing. Install the ChatKit Python "
                "package to enable the conversational endpoint."
            ),
        )
    return _chatkit_server


@app.post("/chatkit")
async def chatkit_endpoint(
    request: Request, server: FactAssistantServer = Depends(get_chatkit_server)
) -> Response:
    payload = await request.body()
    result = await server.process(payload, {"request": request})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return JSONResponse(result)


@app.get("/facts")
async def list_facts() -> dict[str, Any]:
    facts = await fact_store.list_saved()
    return {"facts": [fact.as_dict() for fact in facts]}


@app.post("/facts/{fact_id}/save")
async def save_fact(fact_id: str) -> dict[str, Any]:
    fact = await fact_store.mark_saved(fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"fact": fact.as_dict()}


@app.post("/facts/{fact_id}/discard")
async def discard_fact(fact_id: str) -> dict[str, Any]:
    fact = await fact_store.discard(fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"fact": fact.as_dict()}


@app.post("/summarize", response_model=SummarizationResponse)
async def summarize_endpoint(request: SummarizationRequest) -> SummarizationResponse:
    """Summarize event details markdown using Mistral and generate a poster if possible."""
    try:
        # First, generate the summary
        summary = await summarize_event_details(request.markdown)

        # Extract structured event details for poster generation
        event_details = await extract_event_details(request.markdown)

        poster_url: str | None = None
        event_name: str | None = None
        hackathon_rules: str | None = None

        # Generate hackathon rules
        try:
            hackathon_rules = await generate_hackathon_rules(request.markdown)
            logging.info("[SummarizeEndpoint] Successfully generated hackathon rules")
        except Exception as rules_exc:
            # Log but don't fail the entire request if rules generation fails
            logging.warning(f"[SummarizeEndpoint] Failed to generate hackathon rules: {str(rules_exc)}")
            # Continue without rules

        # Always try to generate poster with fallbacks for missing fields
        try:
            # Provide fallbacks for all required fields
            event_name = event_details.get("event_name") or "Upcoming Event"
            location = event_details.get("location") or "TBA"
            date = event_details.get("date") or "Coming Soon"
            tagline = event_details.get("tagline") or f"Join us for {event_name}"
            focus = event_details.get("focus") or "Innovation & Technology"
            organizer_handle = event_details.get("organizer_handle") or "@EventOrganizers"
            sponsors = event_details.get("sponsors") or []

            print("[SummarizeEndpoint] Generating poster with details (using fallbacks if needed)", {
                "event_name": event_name,
                "location": location,
                "date": date,
                "tagline": tagline,
                "focus": focus
            })

            poster_result = await generate_poster_image(
                event_name=event_name,
                tagline=tagline,
                location=location,
                date=date,
                focus=focus,
                organizer_handle=organizer_handle,
                sponsors=sponsors if sponsors else None,
                skip_tts=True,  # Skip TTS for API calls
            )

            poster_url = poster_result.get("image_url")
            event_name = poster_result.get("event_name") or event_name
            logging.info(f"[SummarizeEndpoint] Successfully generated poster: {poster_url}")
        except Exception as poster_exc:
            # Log but don't fail the entire request if poster generation fails
            logging.warning(f"[SummarizeEndpoint] Failed to generate poster: {str(poster_exc)}")
            # Continue without poster

        return SummarizationResponse(
            summary=summary,
            poster_url=poster_url,
            event_name=event_name,
            hackathon_rules=hackathon_rules,
        )
    except ValueError as exc:
        error_msg = str(exc)
        logging.error(f"[SummarizeEndpoint] ValueError: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as exc:
        logging.exception("Failed to summarize event details")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(exc)}") from exc


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
