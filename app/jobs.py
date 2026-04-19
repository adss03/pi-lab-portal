import datetime
import logging
import threading

from sqlmodel import Session, col, select

from app.database import engine
from app.models import IdeaPost, ScrapeJob

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_running = False


def _run(job_id: int, source: str) -> None:
    global _running
    from app.scrapers import hackernews, indiehackers, reddit

    try:
        with Session(engine) as session:
            job = session.get(ScrapeJob, job_id)
            job.status = "running"
            session.add(job)
            session.commit()

        scrapers = {
            "reddit": reddit.scrape,
            "hackernews": hackernews.scrape,
            "indiehackers": indiehackers.scrape,
        }

        all_results = []
        note_lines = []

        for key, fn in scrapers.items():
            if source not in (key, "all"):
                continue
            try:
                results = fn()
                all_results.extend(results)
                note_lines.append(f"{key}: {len(results)} posts")
                logger.info("Scraper %s: %d posts", key, len(results))
            except Exception as exc:
                note_lines.append(f"{key}: failed ({exc})")
                logger.warning("Scraper %s failed", key, exc_info=True)

        created = 0
        with Session(engine) as session:
            post_ids = [d["post_id"] for d in all_results]
            existing_map = {
                p.post_id: p
                for p in session.exec(
                    select(IdeaPost).where(col(IdeaPost.post_id).in_(post_ids))
                ).all()
            }
            for data in all_results:
                existing = existing_map.get(data["post_id"])
                if existing:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    session.add(existing)
                else:
                    session.add(IdeaPost(**data))
                    created += 1
            session.commit()

        with Session(engine) as session:
            job = session.get(ScrapeJob, job_id)
            job.status = "done"
            job.posts_found = len(all_results)
            job.posts_created = created
            job.notes = " | ".join(note_lines)
            job.finished_at = datetime.datetime.now(datetime.timezone.utc)
            session.add(job)
            session.commit()

    except Exception as exc:
        logger.error("ScrapeJob %d failed: %s", job_id, exc, exc_info=True)
        try:
            with Session(engine) as session:
                job = session.get(ScrapeJob, job_id)
                if job:
                    job.status = "failed"
                    job.error = str(exc)
                    job.finished_at = datetime.datetime.now(datetime.timezone.utc)
                    session.add(job)
                    session.commit()
        except Exception:
            pass
    finally:
        _running = False


def start(job_id: int, source: str) -> bool:
    global _running
    with _lock:
        if _running:
            return False
        _running = True

    t = threading.Thread(target=_run, args=(job_id, source), daemon=True)
    t.start()
    return True
