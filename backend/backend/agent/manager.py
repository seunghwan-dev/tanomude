import asyncio
import datetime as dt

from fastapi import WebSocket

from backend.agent.schemas import Envelope, EventType


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._seq = 0
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

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
