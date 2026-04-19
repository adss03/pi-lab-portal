import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.auth import hash_password
from app.config import settings
from app.database import engine, init_db
from app.models import User
from app.routers import core, pi_health, saas_ideas

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        existing = session.exec(
            select(User).where(User.username == settings.admin_username)
        ).first()
        if not existing:
            session.add(User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
            ))
            session.commit()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=86400 * 30)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(core.router)
app.include_router(saas_ideas.router)
app.include_router(pi_health.router)


@app.exception_handler(HTTPException)
async def auth_redirect_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login/", status_code=302)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
