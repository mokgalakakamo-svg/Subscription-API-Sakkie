from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import TenderDB
from .routers import email_updates as email_updates_router

settings = get_settings()
db: TenderDB | None = None
web_dir = Path(__file__).with_name("web")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = await TenderDB.connect()
    await db.ensure_email_updates_schema()
    yield
    await db.close()


app = FastAPI(
    title="Tender Email Updates API",
    description="Subscribe email addresses to tender update notifications.",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/assets", StaticFiles(directory=web_dir), name="assets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(email_updates_router.router)


@app.get("/", include_in_schema=False)
async def frontend():
    return FileResponse(web_dir / "index.html", headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/email-updates/confirm", include_in_schema=False)
async def email_updates_confirmation_page():
    return FileResponse(web_dir / "confirm.html", headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "email-updates-api"}
