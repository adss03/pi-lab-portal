from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app import jobs
from app.auth import require_auth
from app.database import get_session
from app.models import LABEL_CHOICES, IdeaPost, ScrapeJob, SOURCE_CHOICES, User
from app.templates_config import templates

router = APIRouter(prefix="/ideas")


@router.get("/", response_class=HTMLResponse, name="idea_list")
def idea_list(
    request: Request,
    source: str = "",
    label: str = "",
    q: str = "",
    session: Session = Depends(get_session),
    user: User = Depends(require_auth),
):
    stmt = select(IdeaPost).order_by(col(IdeaPost.score).desc(), col(IdeaPost.posted_at).desc())
    if source:
        stmt = stmt.where(IdeaPost.source == source)
    if label:
        stmt = stmt.where(IdeaPost.label == label)
    if q:
        q = q.strip()
        stmt = stmt.where(
            or_(
                col(IdeaPost.title).ilike(f"%{q}%"),
                col(IdeaPost.body).ilike(f"%{q}%"),
            )
        )

    all_posts = session.exec(stmt).all()
    total = len(all_posts)

    latest_job = session.exec(
        select(ScrapeJob).order_by(col(ScrapeJob.started_at).desc())
    ).first()

    return templates.TemplateResponse(
        "saas_ideas/list.html",
        {
            "request": request,
            "user": user,
            "posts": all_posts[:300],
            "source_choices": SOURCE_CHOICES,
            "label_choices": LABEL_CHOICES,
            "active_source": source,
            "active_label": label,
            "query": q,
            "total": total,
            "latest_job": latest_job,
        },
    )


@router.post("/scrape/", name="scrape_start")
def scrape_start(
    request: Request,
    source: str = Form(default="all"),
    session: Session = Depends(get_session),
    _: User = Depends(require_auth),
):
    active = session.exec(
        select(ScrapeJob).where(col(ScrapeJob.status).in_(["pending", "running"]))
    ).first()
    if active:
        return JSONResponse({"error": "A scrape is already running."}, status_code=409)

    if source not in ("all", "reddit", "hackernews", "indiehackers"):
        source = "all"

    job = ScrapeJob(source=source)
    session.add(job)
    session.commit()
    session.refresh(job)

    if not jobs.start(job.id, source):
        session.delete(job)
        session.commit()
        return JSONResponse({"error": "A scrape is already running."}, status_code=409)

    return JSONResponse({"job_id": job.id, "status": job.status})


@router.get("/scrape/{job_id}/status/", name="scrape_status")
def scrape_status(
    job_id: int,
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(require_auth),
):
    job = session.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404)
    return JSONResponse({
        "status": job.status,
        "posts_found": job.posts_found,
        "posts_created": job.posts_created,
        "notes": job.notes,
        "error": job.error,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    })


@router.get("/{pk}/", response_class=HTMLResponse, name="idea_detail")
def idea_detail(
    pk: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_auth),
):
    post = session.get(IdeaPost, pk)
    if not post:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "saas_ideas/detail.html",
        {"request": request, "user": user, "post": post},
    )
