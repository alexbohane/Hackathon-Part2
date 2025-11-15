"""ChatKit server integration for the boilerplate backend."""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime
from typing import Annotated, Any, AsyncIterator, Final, Literal
from uuid import uuid4

from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

from agents import Agent, RunContextWrapper, Runner, StopAtTools, function_tool
from chatkit.agents import (
    AgentContext,
    ClientToolCall,
    stream_agent_response,
)
from chatkit.server import ChatKitServer
from chatkit.types import (
    AssistantMessageItem,
    Attachment,
    HiddenContextItem,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
from openai.types.responses import ResponseInputContentParam, ResponseInputTextParam
from pydantic import ConfigDict, Field

from .constants import INSTRUCTIONS, MODEL
from .facts import fact_store
from .memory_store import MemoryStore
from .sample_widget import render_weather_widget, weather_widget_copy_text
from .thread_item_converter import BasicThreadItemConverter
from .venue_compare import (
    VenueLookupError,
    render_venue_comparison_widget,
    retrieve_venues,
    venue_comparison_copy_text,
)
from .weather import (
    WeatherLookupError,
    retrieve_weather,
)
from .weather import (
    normalize_unit as normalize_temperature_unit,
)

# If you want to check what's going on under the hood, set this to DEBUG
logging.basicConfig(level=logging.INFO)

SUPPORTED_COLOR_SCHEMES: Final[frozenset[str]] = frozenset({"light", "dark"})
CLIENT_THEME_TOOL_NAME: Final[str] = "switch_theme"


def _normalize_color_scheme(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in SUPPORTED_COLOR_SCHEMES:
        return normalized
    if "dark" in normalized:
        return "dark"
    if "light" in normalized:
        return "light"
    raise ValueError("Theme must be either 'light' or 'dark'.")


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


class FactAgentContext(AgentContext):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    store: Annotated[MemoryStore, Field(exclude=True)]
    request_context: dict[str, Any]


# Import paris_fact after FactAgentContext is defined to avoid circular import
from .paris_tool import paris_fact


@function_tool(description_override="Record an event detail shared by the user so it is saved immediately.")
async def save_fact(
    ctx: RunContextWrapper[FactAgentContext],
    fact: str,
) -> dict[str, str] | None:
    # Play ElevenLabs TTS announcement
    try:
        elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
        if elevenlabs_api_key:
            tts_messages = [
                "I am going to add this event detail to my database",
                "Got it, I'll save that event detail right away",
                "Perfect, I'm recording this event detail now",
                "I'm adding this information to your event details",
                "Let me save that event detail for you",
                "I'll make sure this event detail is saved",
                "Adding this event detail to the database now",
                "I'm documenting this event detail right away",
                "Got it, saving this event detail immediately",
                "I'll add this event detail to your event planning notes",
            ]
            selected_message = random.choice(tts_messages)
            elevenlabs = ElevenLabs(api_key=elevenlabs_api_key)
            audio = elevenlabs.text_to_speech.convert(
                text=selected_message,
                voice_id="JBFqnCBsd6RMkjVDRZzb",
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            play(audio)
        else:
            logging.warning("ELEVENLABS_API_KEY not found, skipping TTS")
    except Exception as tts_exc:
        logging.warning(f"Failed to play TTS: {str(tts_exc)}")

    try:
        saved = await fact_store.create(text=fact)
        confirmed = await fact_store.mark_saved(saved.id)
        if confirmed is None:
            raise ValueError("Failed to save fact")

        await ctx.context.store.add_thread_item(
            ctx.context.thread.id,
            HiddenContextItem(
                id=_gen_id("msg"),
                thread_id=ctx.context.thread.id,
                created_at=datetime.now(),
                content=(
                    f'<FACT_SAVED id="{confirmed.id}" threadId="{ctx.context.thread.id}">{confirmed.text}</FACT_SAVED>'
                ),
            ),
            ctx.context.request_context,
        )
        ctx.context.client_tool_call = ClientToolCall(
            name="record_fact",
            arguments={"fact_id": confirmed.id, "fact_text": confirmed.text},
        )
        print(f"EVENT DETAIL SAVED: {confirmed}")
        return {"fact_id": confirmed.id, "status": "saved"}
    except Exception:
        logging.exception("Failed to save event detail")
        return None


@function_tool(
    description_override="Switch the chat interface between light and dark color schemes."
)
async def switch_theme(
    ctx: RunContextWrapper[FactAgentContext],
    theme: str,
) -> dict[str, str] | None:
    logging.debug(f"Switching theme to {theme}")
    try:
        requested = _normalize_color_scheme(theme)
        ctx.context.client_tool_call = ClientToolCall(
            name=CLIENT_THEME_TOOL_NAME,
            arguments={"theme": requested},
        )
        return {"theme": requested}
    except Exception:
        logging.exception("Failed to switch theme")
        return None


@function_tool(
    description_override="Look up the current weather and upcoming forecast for a location and render an interactive weather dashboard."
)
async def get_weather(
    ctx: RunContextWrapper[FactAgentContext],
    location: str,
    unit: Literal["celsius", "fahrenheit"] | str | None = None,
) -> dict[str, str | None]:
    print("[WeatherTool] tool invoked", {"location": location, "unit": unit})
    try:
        normalized_unit = normalize_temperature_unit(unit)
    except WeatherLookupError as exc:
        print("[WeatherTool] invalid unit", {"error": str(exc)})
        raise ValueError(str(exc)) from exc

    try:
        data = await retrieve_weather(location, normalized_unit)
    except WeatherLookupError as exc:
        print("[WeatherTool] lookup failed", {"error": str(exc)})
        raise ValueError(str(exc)) from exc

    print(
        "[WeatherTool] lookup succeeded",
        {
            "location": data.location,
            "temperature": data.temperature,
            "unit": data.temperature_unit,
        },
    )
    try:
        widget = render_weather_widget(data)
        copy_text = weather_widget_copy_text(data)
        payload: Any
        try:
            payload = widget.model_dump()
        except AttributeError:
            payload = widget
        print("[WeatherTool] widget payload", payload)
    except Exception as exc:  # noqa: BLE001
        print("[WeatherTool] widget build failed", {"error": str(exc)})
        raise ValueError("Weather data is currently unavailable for that location.") from exc

    print("[WeatherTool] streaming widget")
    try:
        await ctx.context.stream_widget(widget, copy_text=copy_text)
    except Exception as exc:  # noqa: BLE001
        print("[WeatherTool] widget stream failed", {"error": str(exc)})
        raise ValueError("Weather data is currently unavailable for that location.") from exc

    print("[WeatherTool] widget streamed")

    observed = data.observation_time.isoformat() if data.observation_time else None

    return {
        "location": data.location,
        "unit": normalized_unit,
        "observed_at": observed,
    }


@function_tool(
    description_override="Compare venue options for an event. When a user asks about venue options or wants to see venue comparisons, this tool retrieves two example venues and displays them side-by-side with images, locations, and cost information."
)
async def compare_venues(
    ctx: RunContextWrapper[FactAgentContext],
    location: str | None = None,
) -> dict[str, str | None]:
    print("[VenueTool] tool invoked", {"location": location})
    try:
        data = await retrieve_venues(location)
    except VenueLookupError as exc:
        print("[VenueTool] lookup failed", {"error": str(exc)})
        raise ValueError(str(exc)) from exc

    print(
        "[VenueTool] lookup succeeded",
        {
            "venue1": data.venues[0].name,
            "venue2": data.venues[1].name,
        },
    )
    try:
        widget = render_venue_comparison_widget(data)
        copy_text = venue_comparison_copy_text(data)
        payload: Any
        try:
            payload = widget.model_dump()
        except AttributeError:
            payload = widget
        print("[VenueTool] widget payload", payload)
    except Exception as exc:  # noqa: BLE001
        print("[VenueTool] widget build failed", {"error": str(exc)})
        raise ValueError("Venue comparison data is currently unavailable.") from exc

    print("[VenueTool] streaming widget")
    try:
        await ctx.context.stream_widget(widget, copy_text=copy_text)
    except Exception as exc:  # noqa: BLE001
        print("[VenueTool] widget stream failed", {"error": str(exc)})
        raise ValueError("Venue comparison data is currently unavailable.") from exc

    print("[VenueTool] widget streamed")

    return {
        "venue1": data.venues[0].name,
        "venue2": data.venues[1].name,
        "location": location,
    }


class FactAssistantServer(ChatKitServer[dict[str, Any]]):
    """ChatKit server wired up with the event planning assistant."""

    def __init__(self) -> None:
        self.store: MemoryStore = MemoryStore()
        super().__init__(self.store)
        tools = [save_fact, switch_theme, get_weather, paris_fact, compare_venues]
        self.assistant = Agent[FactAgentContext](
            model=MODEL,
            name="Event Planner",
            instructions=INSTRUCTIONS,
            tools=tools,  # type: ignore[arg-type]
            # Stop generating response after client tool calls are made
            tool_use_behavior=StopAtTools(stop_at_tool_names=[save_fact.name, switch_theme.name]),
        )
        self.thread_item_converter = BasicThreadItemConverter()

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        agent_context = FactAgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )

        # Load all items from the thread to send as agent input.
        # Needed to ensure that the agent is aware of the full conversation
        # when generating a response.
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=20,
            order="desc",
            context=context,
        )
        # Runner expects last message last
        items = list(reversed(items_page.data))

        # If thread is empty (first message), send welcome message first
        if len(items) == 0:
            welcome_message = "Hello, I am here to assist you in planning an event, feel free to use the chat and we can start building the event of your dreams"
            welcome_item = AssistantMessageItem(
                id=_gen_id("msg"),
                thread_id=thread.id,
                created_at=datetime.now(),
                content=[
                    ResponseInputTextParam(
                        type="input_text",
                        text=welcome_message,
                    )
                ],
                role="assistant",
            )

            # Save the welcome message to the thread
            await self.store.add_thread_item(thread.id, welcome_item, context)

            # Yield the welcome message as a stream event
            yield ThreadStreamEvent(
                type="thread.message.delta",
                thread_id=thread.id,
                id=welcome_item.id,
                delta={
                    "type": "message.delta",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "input_text_delta",
                            "text": welcome_message,
                        }
                    ],
                },
            )

            yield ThreadStreamEvent(
                type="thread.message.completed",
                thread_id=thread.id,
                id=welcome_item.id,
                message=welcome_item,
            )

            # If no user message, we're done (just showing welcome)
            if item is None:
                return

            # If there's a user message, reload items to include the welcome message
            items_page = await self.store.load_thread_items(
                thread.id,
                after=None,
                limit=20,
                order="desc",
                context=context,
            )
            items = list(reversed(items_page.data))

        input_items = await self.thread_item_converter.to_agent_input(items)

        result = Runner.run_streamed(
            self.assistant,
            # Use default ThreadItemConverter to convert chatkit thread items to agent input
            input_items,
            context=agent_context,
        )

        async for event in stream_agent_response(agent_context, result):
            yield event
        return

    async def to_message_content(self, _input: Attachment) -> ResponseInputContentParam:
        raise RuntimeError("File attachments are not supported in this demo.")


def create_chatkit_server() -> FactAssistantServer | None:
    """Return a configured ChatKit server instance if dependencies are available."""
    return FactAssistantServer()
