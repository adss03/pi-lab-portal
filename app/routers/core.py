from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.auth import require_auth, verify_password
from app.database import get_session
from app.models import User
from app.templates_config import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse, name="dashboard")
def dashboard(request: Request, user: User = Depends(require_auth)):
    return templates.TemplateResponse("core/dashboard.html", {"request": request, "user": user})


@router.get("/login/", response_class=HTMLResponse, name="login")
def login_get(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("core/login.html", {"request": request})


@router.post("/login/", response_class=HTMLResponse)
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "core/login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401,
        )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout/", name="logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login/", status_code=302)
