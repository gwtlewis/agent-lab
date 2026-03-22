"""WebSocket server that exposes the LangChain agent to a browser UI.

Protocol (client → server):
  {"type": "message", "content": "...", "system_prompt": "..."}
  {"type": "ping"}
  {"type": "clear"}

Protocol (server → client):
  {"type": "status",    "content": "thinking"}
  {"type": "reasoning", "content": "<chunk>"}
  {"type": "token",     "content": "<chunk>"}
  {"type": "final",     "content": "<full answer>", "metadata": {...}}
  {"type": "error",     "content": "<message>"}
  {"type": "pong"}
  {"type": "cleared"}
  {"type": "status",    "content": "connected", "metadata": {"provider": "...", "model": "..."}}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── agent imports ──────────────────────────────────────────────────────────────
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import IntegratedAgent, OLLAMA_MODEL, LLM_PROVIDER  # noqa: E402
from event_model import AgentEvent  # noqa: E402

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Agent Lab WebSocket Server")

# Serve the UI static files if the directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    """Serve the chat UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Agent Lab WebSocket Server is running. Connect via /ws"}


@app.get("/health")
async def health():
    return {"status": "ok", "provider": LLM_PROVIDER, "model": OLLAMA_MODEL}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """One WebSocket connection = one isolated conversation session."""
    await ws.accept()
    logger.info("WebSocket client connected")

    # Each connection gets its own agent instance → isolated history
    try:
        agent = IntegratedAgent(provider=LLM_PROVIDER)
    except Exception as e:
        await ws.send_text(AgentEvent.error(f"Agent init failed: {e}").to_json())
        await ws.close()
        return

    # Send initial handshake
    await ws.send_text(
        AgentEvent(
            type="status",
            content="connected",
            metadata={"provider": LLM_PROVIDER, "model": OLLAMA_MODEL},
        ).to_json()
    )

    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(AgentEvent.error("Invalid JSON").to_json())
                continue

            msg_type = payload.get("type", "")

            if msg_type == "ping":
                await ws.send_text(AgentEvent.pong().to_json())
                continue

            if msg_type == "clear":
                agent.clear_memory()
                await ws.send_text(AgentEvent.cleared().to_json())
                continue

            if msg_type == "message":
                content = (payload.get("content") or "").strip()
                if not content:
                    await ws.send_text(AgentEvent.error("Empty message").to_json())
                    continue

                system_prompt = payload.get("system_prompt") or None
                enable_reasoning = bool(payload.get("enable_reasoning", True))

                # Run the blocking generator in a thread pool so we don't block
                # the asyncio event loop while the LLM streams.
                await _stream_to_ws(ws, agent, content, system_prompt, enable_reasoning)
                continue

            # Unknown message type — ignore gracefully
            logger.warning("Unknown message type from client: %s", msg_type)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("Unexpected WebSocket error: %s", e)
        try:
            await ws.send_text(AgentEvent.error(str(e)).to_json())
        except Exception:
            pass
    finally:
        agent.close()


async def _stream_to_ws(
    ws: WebSocket,
    agent: IntegratedAgent,
    content: str,
    system_prompt: str | None,
    enable_reasoning: bool,
) -> None:
    """Stream agent events to the websocket in real time using an asyncio Queue.

    The synchronous generator runs in a thread pool executor; each event is
    placed on a queue which the main coroutine drains and forwards to the client.
    """
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
    loop = asyncio.get_event_loop()
    sentinel = None

    def _produce():
        try:
            for event in agent.stream_events(
                content, system_prompt=system_prompt, enable_reasoning=enable_reasoning
            ):
                asyncio.run_coroutine_threadsafe(queue.put(event), loop)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(sentinel), loop)

    loop.run_in_executor(None, _produce)

    while True:
        event = await queue.get()
        if event is None:
            break
        try:
            await ws.send_text(event.to_json())
        except Exception:
            break


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("WEB_PORT", "8000"))
    uvicorn.run("web_server:app", host="0.0.0.0", port=port, reload=False)
