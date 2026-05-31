from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.agent.manager import manager

ws_router = APIRouter()


@ws_router.websocket("/ws/agent")
async def agent_ws(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
