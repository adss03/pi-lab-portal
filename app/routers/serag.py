from fastapi import APIRouter, Depends
from fastapi.requests import Request
from fastapi.responses import HTMLResponse

from app.auth import require_auth
from app.models import User
from app.templates_config import templates

router = APIRouter(prefix="/serag")


@router.get("/", response_class=HTMLResponse, name="serag_sign")
def serag_sign(request: Request, _: User = Depends(require_auth)):
    return templates.TemplateResponse("serag/sign.html", {"request": request})
