from fastapi import FastAPI

from backend.agent.router import router
from backend.agent.ws import ws_router

app = FastAPI(title="tanomude-agent", version="0.1.0")
app.include_router(router)
app.include_router(ws_router)
