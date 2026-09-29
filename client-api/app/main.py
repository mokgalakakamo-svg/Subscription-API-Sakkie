from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import TenderDB
from .routers import subscriptions as subscriptions_router

settings = get_settings()
db: TenderDB | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = await TenderDB.connect()
    await db.ensure_subscription_schema()
    yield
    await db.close()


app = FastAPI(
    title="Tender Subscription API",
    description="Customer accounts, subscription plans, and subscription management.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(subscriptions_router.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "subscription-api"}
