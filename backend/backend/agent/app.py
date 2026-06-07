import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.agent.manager import manager
from backend.agent.router import router
from backend.agent.ws import ws_router
from backend.config import settings
from backend.db import SessionLocal
from backend.ingest import run_startup_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.bind_loop(asyncio.get_running_loop())
    with SessionLocal() as db:
        run_startup_seed(db)
    yield


RESERVED_PREFIXES = ("api/", "tasks/", "ws/")


class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.replace("\\", "/").startswith(RESERVED_PREFIXES):
                return await super().get_response("index.html", scope)
            raise


def mount_frontend(app: FastAPI, dist: Path) -> None:
    if (dist / "index.html").is_file():
        app.mount("/", SpaStaticFiles(directory=str(dist), html=True), name="frontend")


app = FastAPI(title="tanomude-agent", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(router, prefix="/api")
app.include_router(ws_router)
mount_frontend(app, Path(settings.frontend_dist))
