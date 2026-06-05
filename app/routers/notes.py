from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.auth import require_auth
from app.database import get_session
from app.models import Note, User
from app.templates_config import templates

router = APIRouter(prefix="/notes")

TAGS = ["general", "ci-cd", "devops", "fastapi", "infra", "ai"]


@router.get("/", response_class=HTMLResponse, name="notes_list")
def notes_list(
    request: Request,
    tag: str = "",
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
):
    query = select(Note).order_by(Note.updated_at.desc())
    if tag:
        query = query.where(Note.tag == tag)
    notes = session.exec(query).all()
    return templates.TemplateResponse(
        "notes/list.html",
        {"request": request, "user": user, "notes": notes, "active_tag": tag, "tags": TAGS},
    )


@router.get("/new/", response_class=HTMLResponse, name="notes_new")
def notes_new_get(request: Request, user: User = Depends(require_auth)):
    return templates.TemplateResponse(
        "notes/form.html",
        {"request": request, "user": user, "note": None, "tags": TAGS},
    )


@router.post("/new/", response_class=HTMLResponse)
def notes_new_post(
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    tag: str = Form("general"),
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
):
    note = Note(title=title.strip(), body=body.strip(), tag=tag)
    session.add(note)
    session.commit()
    session.refresh(note)
    return RedirectResponse(url=f"/notes/{note.id}/", status_code=302)


@router.get("/{note_id}/", response_class=HTMLResponse, name="notes_detail")
def notes_detail(
    note_id: int,
    request: Request,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
):
    note = session.get(Note, note_id)
    if not note:
        return RedirectResponse(url="/notes/", status_code=302)
    return templates.TemplateResponse(
        "notes/detail.html",
        {"request": request, "user": user, "note": note},
    )


@router.get("/{note_id}/edit/", response_class=HTMLResponse, name="notes_edit")
def notes_edit_get(
    note_id: int,
    request: Request,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
):
    note = session.get(Note, note_id)
    if not note:
        return RedirectResponse(url="/notes/", status_code=302)
    return templates.TemplateResponse(
        "notes/form.html",
        {"request": request, "user": user, "note": note, "tags": TAGS},
    )


@router.post("/{note_id}/edit/")
def notes_edit_post(
    note_id: int,
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    tag: str = Form("general"),
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
):
    note = session.get(Note, note_id)
    if not note:
        return RedirectResponse(url="/notes/", status_code=302)
    note.title = title.strip()
    note.body = body.strip()
    note.tag = tag
    note.updated_at = datetime.utcnow()
    session.add(note)
    session.commit()
    return RedirectResponse(url=f"/notes/{note.id}/", status_code=302)


@router.post("/{note_id}/delete/")
def notes_delete(
    note_id: int,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
):
    note = session.get(Note, note_id)
    if note:
        session.delete(note)
        session.commit()
    return RedirectResponse(url="/notes/", status_code=302)
