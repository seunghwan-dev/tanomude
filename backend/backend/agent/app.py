import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.agent.manager import manager
from backend.agent.router import router
from backend.agent.ws import ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="tanomude-agent", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(ws_router)
