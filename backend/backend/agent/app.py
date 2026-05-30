from fastapi import FastAPI

from backend.agent.router import router

app = FastAPI(title="tanomude-agent", version="0.1.0")
app.include_router(router)
