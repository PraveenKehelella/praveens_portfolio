from __future__ import annotations

import json
import os
import time
import uuid
from collections import OrderedDict
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException

from .knowledge import ROOT_DIR, build_system_prompt

load_dotenv(ROOT_DIR / ".env")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "220"))
MAX_QUERY_CHARS = 400
MAX_HISTORY_TURNS = 6
MAX_CONVERSATIONS = 256
CONVERSATION_TTL_S = 60 * 30

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Praveen portfolio API", docs_url=None, redoc_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

client: AsyncOpenAI | None = None
SYSTEM_PROMPT = build_system_prompt()
_conversations: OrderedDict[str, dict] = OrderedDict()


def _client() -> AsyncOpenAI:
    global client
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not set")
    if client is None:
        client = AsyncOpenAI(api_key=key)
    return client


class ChatIn(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_CHARS)
    conversation_id: str | None = Field(default=None, max_length=64)


def _prune_conversations(now: float) -> None:
    stale = [cid for cid, row in _conversations.items() if now - row["ts"] > CONVERSATION_TTL_S]
    for cid in stale:
        _conversations.pop(cid, None)
    while len(_conversations) > MAX_CONVERSATIONS:
        _conversations.popitem(last=False)


def _history_for(conversation_id: str) -> list[dict]:
    now = time.time()
    _prune_conversations(now)
    row = _conversations.get(conversation_id)
    if not row:
        return []
    row["ts"] = now
    _conversations.move_to_end(conversation_id)
    return list(row["messages"])


def _remember(conversation_id: str, user: str, assistant: str) -> None:
    now = time.time()
    row = _conversations.get(conversation_id)
    if not row:
        row = {"ts": now, "messages": []}
        _conversations[conversation_id] = row
    row["ts"] = now
    row["messages"].append({"role": "user", "content": user})
    row["messages"].append({"role": "assistant", "content": assistant})
    row["messages"] = row["messages"][-MAX_HISTORY_TURNS * 2 :]
    _conversations.move_to_end(conversation_id)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
@limiter.limit("8/minute")
async def chat(request: Request, body: ChatIn) -> StreamingResponse:
    query = " ".join(body.query.split())
    if not query:
        raise HTTPException(status_code=400, detail="empty query")

    conversation_id = body.conversation_id or str(uuid.uuid4())
    openai_client = _client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *_history_for(conversation_id),
        {"role": "user", "content": query},
    ]

    async def event_stream() -> AsyncIterator[str]:
        yield _sse({"conversation_id": conversation_id})
        collected: list[str] = []
        try:
            stream = await openai_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=0.35,
                stream=True,
            )
            async for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if not token:
                    continue
                collected.append(token)
                yield _sse({"token": token})
        except Exception:
            yield _sse({"error": "the agent hit a provider error. try again shortly."})
            return
        text = "".join(collected).strip()
        if text:
            _remember(conversation_id, query, text)
        yield _sse({"done": True})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class SafeStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        lowered = path.lower().lstrip("/")
        blocked = (
            lowered.startswith(".env")
            or lowered.startswith("backend/")
            or lowered.startswith(".git")
            or lowered.startswith(".venv")
            or lowered.startswith("venv/")
            or lowered.endswith(".pdf")
            or lowered.endswith(".docx")
            or lowered.endswith("excellements/4.png")
            or lowered.endswith("excellements/5.png")
            or lowered.endswith("excellements/6.png")
            or lowered.endswith("excellements/7.png")
            or lowered.endswith("classic_barber_shop_booking_4.png")
            or lowered.endswith("classic_barber_shop_booking_5.png")
            or lowered.endswith("production_pulse_monitor_0.png")
            or lowered.endswith("production_pulse_monitor_1.png")
            or lowered.endswith("production_pulse_monitor_2.png")
            or lowered.endswith("production_pulse_monitor_3.png")
        )
        if blocked:
            raise StarletteHTTPException(status_code=404)
        return await super().get_response(path, scope)


app.mount("/", SafeStaticFiles(directory=str(ROOT_DIR), html=True), name="static")
