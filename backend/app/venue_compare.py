"""Venue comparison tool for event planning."""

from __future__ import annotations

import httpx
import os
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from chatkit.widgets import (
    Badge,
    Caption,
    Card,
    Col,
    Icon,
    Image,
    Row,
    Spacer,
    Text,
    Title,
    WidgetComponent,
    WidgetRoot,
)

USER_AGENT = "ChatKitVenueTool/1.0 (+https://openai.com/)"
DEBUG_PREFIX = "[VenueDebug]"
DEFAULT_TIMEOUT = 20.0

# You can use Google Places API, Eventbrite API, or similar venue services
# For now, this uses a fallback to generated examples
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")
GOOGLE_PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"


class VenueLookupError(RuntimeError):
    """Raised when venue data could not be retrieved."""


@dataclass(frozen=True)
class Venue:
    """Represents a venue for comparison."""

    id: str
    name: str
    image: str
    alt: str
    location: str
    cost: Literal["$", "$$", "$$$"]


@dataclass(frozen=True)
class VenueComparisonData:
    """Data structure for venue comparison widget."""

    venues: tuple[Venue, Venue]


def _compact(items: list[WidgetComponent | None]) -> list[WidgetComponent]:
    """Filter out None values from a list of widget components."""
    return [item for item in items if item is not None]


def _debug(message: str, *, extra: dict[str, Any] | None = None) -> None:
    """Print debug information."""
    payload = f"{DEBUG_PREFIX} {message}"
    if extra:
        payload = f"{payload} | {extra}"
    print(payload)


async def _fetch_venues_from_api(location: str | None = None) -> list[Venue] | None:
    """Fetch venues from an external API (e.g., Google Places API).

    Returns None if API is not configured or request fails.
    """
    # Example: Google Places API integration
    # Uncomment and configure when you have an API key

    if not GOOGLE_PLACES_API_KEY:
        _debug("Google Places API key not configured")
        return None

    query = f"event venues in {location}" if location else "event venues"

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
            },
        ) as client:
            response = await client.post(
                GOOGLE_PLACES_API_URL,
                json={"textQuery": query, "maxResultCount": 2},
            )
            response.raise_for_status()
            data = response.json()

            venues = []
            for place in data.get("places", [])[:2]:
                venue = Venue(
                    id=place.get("id", str(uuid4())),
                    name=place.get("displayName", {}).get("text", "Unknown Venue"),
                    image=place.get("photos", [{}])[0].get("uri", "") if place.get("photos") else "",
                    alt=place.get("displayName", {}).get("text", "Venue image"),
                    location=place.get("formattedAddress", "Unknown Location"),
                    cost=_estimate_cost(place.get("priceLevel", "FREE")),
                )
                venues.append(venue)

            if len(venues) >= 2:
                return venues
    except Exception as exc:
        _debug("API fetch failed", extra={"error": str(exc)})
        return None

    return None


def _estimate_cost(price_level: str) -> Literal["$", "$$", "$$$"]:
    """Convert API price level to our cost format."""
    price_mapping = {
        "FREE": "$",
        "INEXPENSIVE": "$",
        "MODERATE": "$$",
        "EXPENSIVE": "$$$",
        "VERY_EXPENSIVE": "$$$",
    }
    return price_mapping.get(price_level.upper(), "$$")


def _get_fallback_venues(location: str | None = None) -> list[Venue]:
    """Generate fallback venue examples when API is not available."""
    # Fallback venue data - can be replaced with database or other source
    all_venues = [
        Venue(
            id="v1",
            name="Station F",
            image="https://cdn.paris.fr/paris/2019/07/24/huge-b3f17e0874dcf107f84c6745e8581c55.jpeg?w=800",
            alt="Large Startup Campus",
            location="Paris, France",
            cost="$$$",
        ),
        Venue(
            id="v2",
            name="École 42",
            image="https://paris-promeneurs.com/wp-content/uploads/2024/01/ecole3-800.jpg?w=800",
            alt="Sleek Modern University Building",
            location="Paris, France",
            cost="$$",
        ),
    ]

    # If location is provided, try to match venues by location
    matched_venues = []
    if location:
        location_lower = location.lower()
        for venue in all_venues:
            if location_lower in venue.location.lower() or location_lower in venue.name.lower():
                matched_venues.append(venue)

    # Use matched venues if available, otherwise use all venues
    venue_pool = matched_venues if matched_venues else all_venues

    # Return two venues
    if len(venue_pool) >= 2:
        return venue_pool[:2]
    else:
        # If not enough matches, add from the general pool
        selected_venues = list(venue_pool[:1])
        for venue in all_venues:
            if venue not in selected_venues:
                selected_venues.append(venue)
                break
        return selected_venues[:2]


async def retrieve_venues(location: str | None = None) -> VenueComparisonData:
    """Retrieve two venues for comparison.

    First attempts to fetch from an external API (if configured).
    Falls back to example venues if API is unavailable.
    """
    _debug("retrieve_venues invoked", extra={"location": location})

    # Try to fetch from API first
    api_venues = await _fetch_venues_from_api(location)

    if api_venues and len(api_venues) >= 2:
        _debug("Using venues from API", extra={"count": len(api_venues)})
        return VenueComparisonData(venues=(api_venues[0], api_venues[1]))

    # Fall back to example venues
    _debug("Using fallback venues")
    fallback_venues = _get_fallback_venues(location)

    if len(fallback_venues) < 2:
        raise VenueLookupError("Unable to retrieve sufficient venue options.")

    return VenueComparisonData(venues=(fallback_venues[0], fallback_venues[1]))


def render_venue_comparison_widget(data: VenueComparisonData) -> WidgetRoot:
    """Build a venue comparison widget from venue data."""

    venue1, venue2 = data.venues

    return Card(
        key="venue-comparison",
        size="md",
        children=[
            Col(
                gap=3,
                children=[
                    Title(value="Compare venues", size="sm"),
                    Row(
                        gap=3,
                        align="stretch",
                        children=[
                            Col(
                                key=venue1.id,
                                flex=1,
                                gap=2,
                                children=[
                                    Image(
                                        src=venue1.image,
                                        alt=venue1.alt,
                                        aspectRatio=16 / 9,
                                    ),
                                    Text(
                                        value=venue1.name,
                                        size="sm",
                                        weight="semibold",
                                        maxLines=1,
                                    ),
                                    Row(
                                        gap=2,
                                        align="center",
                                        children=[
                                            Icon(name="map-pin", size="sm", color="secondary"),
                                            Caption(value=venue1.location),
                                            Spacer(),
                                            Badge(label=venue1.cost, color="info"),
                                        ],
                                    ),
                                ],
                            ),
                            Col(
                                key=venue2.id,
                                flex=1,
                                gap=2,
                                children=[
                                    Image(
                                        src=venue2.image,
                                        alt=venue2.alt,
                                        aspectRatio=16 / 9,
                                    ),
                                    Text(
                                        value=venue2.name,
                                        size="sm",
                                        weight="semibold",
                                        maxLines=1,
                                    ),
                                    Row(
                                        gap=2,
                                        align="center",
                                        children=[
                                            Icon(name="map-pin", size="sm", color="secondary"),
                                            Caption(value=venue2.location),
                                            Spacer(),
                                            Badge(label=venue2.cost, color="info"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def venue_comparison_copy_text(data: VenueComparisonData) -> str:
    """Generate human-readable fallback text for the venue comparison widget."""
    venue1, venue2 = data.venues

    return (
        f"Here are two venue options: {venue1.name} in {venue1.location} ({venue1.cost}) "
        f"and {venue2.name} in {venue2.location} ({venue2.cost})."
    )

