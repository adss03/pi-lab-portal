import asyncio
import json
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from app.auth import require_auth
from app.config import settings
from app.models import User
from app.templates_config import templates

router = APIRouter(prefix="/pl")

PL_BASE = "https://api.football-data.org/v4"

# ── demo data ─────────────────────────────────────────────────────────────────

_now = datetime.now(timezone.utc)
DEMO_MATCHES = [
    {
        "id": -1,
        "status": "IN_PLAY",
        "minute": 67,
        "utcDate": _now.isoformat(),
        "homeTeam": {"id": -1, "name": "Arsenal FC", "shortName": "Arsenal"},
        "awayTeam": {"id": -2, "name": "Manchester City FC", "shortName": "Man City"},
        "score": {
            "fullTime": {"home": 2, "away": 1},
            "halfTime": {"home": 2, "away": 1},
        },
    },
    {
        "id": -2,
        "status": "TIMED",
        "minute": None,
        "utcDate": _now.replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
        "homeTeam": {"id": -3, "name": "Tottenham Hotspur FC", "shortName": "Spurs"},
        "awayTeam": {"id": -4, "name": "Liverpool FC", "shortName": "Liverpool"},
        "score": {
            "fullTime": {"home": None, "away": None},
            "halfTime": {"home": None, "away": None},
        },
    },
]

# (delay_seconds_from_previous, event_dict)
DEMO_SEQ = [
    (0, {"type": "SCORE", "home": "Arsenal", "away": "Man City",
         "home_score": 2, "away_score": 1, "status": "IN_PLAY", "minute": 67}),
    (0, {"type": "STATUS", "text": "Match in progress", "status": "IN_PLAY"}),
    (0, {"type": "GOAL", "minute": 12, "team": "Arsenal",
         "player": "B. Saka", "assist": "M. Ødegaard"}),
    (0, {"type": "YELLOW_CARD", "minute": 28, "team": "Man City", "player": "Rodri"}),
    (0, {"type": "GOAL", "minute": 34, "team": "Arsenal",
         "player": "G. Martinelli", "assist": "B. White"}),
    (0, {"type": "GOAL", "minute": 41, "team": "Man City",
         "player": "E. Haaland", "assist": "K. De Bruyne"}),
    (0, {"type": "STATUS", "text": "Half time", "status": "PAUSED"}),
    (0, {"type": "STATUS", "text": "Second half", "status": "IN_PLAY"}),
    (0, {"type": "SUBSTITUTION", "minute": 60, "team": "Man City",
         "player_in": "P. Foden", "player_out": "B. Silva"}),
    # live events
    (6,  {"type": "SCORE", "home": "Arsenal", "away": "Man City",
          "home_score": 2, "away_score": 1, "status": "IN_PLAY", "minute": 68}),
    (4,  {"type": "YELLOW_CARD", "minute": 72, "team": "Arsenal", "player": "T. Partey"}),
    (7,  {"type": "GOAL", "minute": 78, "team": "Man City",
          "player": "E. Haaland", "assist": "P. Foden"}),
    (1,  {"type": "SCORE", "home": "Arsenal", "away": "Man City",
          "home_score": 2, "away_score": 2, "status": "IN_PLAY", "minute": 78}),
    (7,  {"type": "SUBSTITUTION", "minute": 81, "team": "Arsenal",
          "player_in": "E. Nketiah", "player_out": "G. Jesus"}),
    (8,  {"type": "RED_CARD", "minute": 85, "team": "Man City", "player": "Rodri"}),
    (9,  {"type": "GOAL", "minute": 90, "team": "Arsenal",
          "player": "E. Nketiah", "assist": "", "injury_time": 2}),
    (1,  {"type": "SCORE", "home": "Arsenal", "away": "Man City",
          "home_score": 3, "away_score": 2, "status": "IN_PLAY", "minute": 90}),
    (6,  {"type": "STATUS", "text": "Full time — Arsenal 3–2 Man City", "status": "FINISHED"}),
]


async def _demo_stream(_match_id: int):
    for delay, ev in DEMO_SEQ:
        if delay > 0:
            await asyncio.sleep(delay)
        yield f"data: {json.dumps(ev)}\n\n"


# ── helpers ───────────────────────────────────────────────────────────────────

def _team_name(team: dict) -> str:
    return team.get("shortName") or team.get("tla") or team.get("name", "?")


async def _fetch(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{PL_BASE}{path}",
            params=params,
            headers={"X-Auth-Token": settings.football_data_api_key},
        )
        r.raise_for_status()
        return r.json()


# ── live stream ───────────────────────────────────────────────────────────────

async def _live_stream(match_id: int):
    seen = {"goals": 0, "bookings": 0, "substitutions": 0}
    first = True
    last_status = None

    while True:
        try:
            match = await _fetch(f"/matches/{match_id}")
            status = match.get("status", "")
            home = _team_name(match.get("homeTeam", {}))
            away = _team_name(match.get("awayTeam", {}))
            sc = match.get("score", {})
            ft = sc.get("fullTime") or {}
            ht = sc.get("halfTime") or {}
            minute = match.get("minute")

            if first:
                text = {
                    "IN_PLAY": "Match in progress",
                    "PAUSED": "Half time",
                    "FINISHED": "Full time",
                    "TIMED": "Match not started yet",
                    "SCHEDULED": "Match not started yet",
                }.get(status, status)
                yield f"data: {json.dumps({'type': 'STATUS', 'text': text, 'status': status, 'minute': minute})}\n\n"
                first = False
                last_status = status
            elif status != last_status:
                if status == "IN_PLAY" and last_status in ("TIMED", "SCHEDULED"):
                    yield f"data: {json.dumps({'type': 'STATUS', 'text': 'Kick off!', 'status': status})}\n\n"
                elif status == "PAUSED":
                    yield f"data: {json.dumps({'type': 'STATUS', 'text': 'Half time', 'status': status})}\n\n"
                elif status == "IN_PLAY" and last_status == "PAUSED":
                    yield f"data: {json.dumps({'type': 'STATUS', 'text': 'Second half', 'status': status})}\n\n"
                elif status == "FINISHED":
                    yield f"data: {json.dumps({'type': 'STATUS', 'text': 'Full time', 'status': status})}\n\n"
                last_status = status

            new_events: list[dict] = []

            goals = match.get("goals") or []
            for g in goals[seen["goals"]:]:
                etype = {"OWN_GOAL": "OWN_GOAL", "PENALTY": "PENALTY"}.get(g.get("type", ""), "GOAL")
                new_events.append({
                    "minute": g.get("minute") or 0,
                    "injury_time": g.get("injuryTime"),
                    "type": etype,
                    "team": _team_name(g.get("team") or {}),
                    "player": ((g.get("scorer") or {}).get("name") or ""),
                    "assist": ((g.get("assist") or {}).get("name") or ""),
                })
            seen["goals"] = len(goals)

            bookings = match.get("bookings") or []
            for b in bookings[seen["bookings"]:]:
                new_events.append({
                    "minute": b.get("minute") or 0,
                    "injury_time": b.get("injuryTime"),
                    "type": b.get("cardType", "YELLOW_CARD"),
                    "team": _team_name(b.get("team") or {}),
                    "player": ((b.get("player") or {}).get("name") or ""),
                })
            seen["bookings"] = len(bookings)

            subs = match.get("substitutions") or []
            for s in subs[seen["substitutions"]:]:
                new_events.append({
                    "minute": s.get("minute") or 0,
                    "injury_time": s.get("injuryTime"),
                    "type": "SUBSTITUTION",
                    "team": _team_name(s.get("team") or {}),
                    "player_in": ((s.get("playerIn") or {}).get("name") or ""),
                    "player_out": ((s.get("playerOut") or {}).get("name") or ""),
                })
            seen["substitutions"] = len(subs)

            new_events.sort(key=lambda e: (e["minute"], e.get("injury_time") or 0))
            for ev in new_events:
                yield f"data: {json.dumps(ev)}\n\n"

            current = ft if any(v is not None for v in ft.values()) else ht
            yield f"data: {json.dumps({'type': 'SCORE', 'home': home, 'away': away, 'home_score': current.get('home') or 0, 'away_score': current.get('away') or 0, 'status': status, 'minute': minute})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'ERROR', 'text': str(e)})}\n\n"

        if last_status == "FINISHED":
            break

        await asyncio.sleep(30)


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, name="pl_feed")
async def pl_feed(request: Request, user: User = Depends(require_auth)):
    return templates.TemplateResponse(
        "premier_league/feed.html", {"request": request, "user": user}
    )


@router.get("/matches/", name="pl_matches")
async def pl_matches(_: User = Depends(require_auth)):
    if not settings.football_data_api_key:
        return JSONResponse({"matches": DEMO_MATCHES, "demo": True})
    try:
        today = date.today().isoformat()
        data = await _fetch("/competitions/PL/matches", {"dateFrom": today, "dateTo": today})
        return JSONResponse({"matches": data.get("matches", []), "demo": False})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@router.get("/feed/{match_id}/", name="pl_match_feed")
async def pl_match_feed(match_id: int, _: User = Depends(require_auth)):
    if not settings.football_data_api_key or match_id < 0:
        return StreamingResponse(
            _demo_stream(match_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return StreamingResponse(
        _live_stream(match_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
