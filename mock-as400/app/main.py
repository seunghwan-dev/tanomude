from fastapi import FastAPI

from app.routers import health, session, trip

app = FastAPI(title="mock-as400", version="0.1.0")
app.include_router(health.router)
app.include_router(trip.router)
app.include_router(session.router)
