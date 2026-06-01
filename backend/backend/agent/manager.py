import asyncio
import datetime as dt
import logging
from concurrent.futures import Future

from fastapi import WebSocket

from backend.agent.schemas import Envelope, EventType

logger = logging.getLogger(__name__)


def _log_emit_result(future: Future) -> None:
    exc = future.exception()
    if exc is not None:
        logger.warning("step broadcast failed: %r", exc)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._seq = 0
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    def emit_threadsafe(self, event_type: EventType, task_id: int, payload: dict) -> None:
        if self._loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            self.broadcast(event_type, task_id, payload), self._loop
        )
        future.add_done_callback(_log_emit_result)

    async def broadcast(self, event_type: EventType, task_id: int, payload: dict) -> None:
        async with self._lock:
            self._seq += 1
            envelope = Envelope(
                type=event_type,
                task_id=task_id,
                seq=self._seq,
                ts=dt.datetime.now(dt.timezone.utc),
                payload=payload,
            )
            message = envelope.model_dump(mode="json")
            for websocket in list(self._connections):
                try:
                    await websocket.send_json(message)
                except Exception:
                    self.disconnect(websocket)


manager = ConnectionManager()
