import asyncio
import glob as _glob
import json
import time

import psutil
from fastapi import APIRouter, Depends, Form
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from app.auth import require_auth
from app.models import User
from app.templates_config import templates

router = APIRouter(prefix="/pi-health")

PWM_GLOB = "/sys/devices/platform/cooling_fan/hwmon/hwmon*/pwm1"

_fan: dict = {"task": None, "ends_at": 0.0, "speed": 0}


def _pwm_path() -> str | None:
    m = _glob.glob(PWM_GLOB)
    return m[0] if m else None


def _write_pwm(path: str, value) -> None:
    with open(path, "w") as f:
        f.write(str(value))


async def _spin(seconds: int, speed: int, path: str, original: str) -> None:
    deadline = time.monotonic() + seconds
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            _write_pwm(path, speed)
            await asyncio.sleep(min(1.0, remaining))
    finally:
        _fan["task"] = None
        _fan["ends_at"] = 0.0
        _fan["speed"] = 0
        try:
            _write_pwm(path, original)
        except OSError:
            pass


def _cpu_temp() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
        for key in ("cpu_thermal", "coretemp", "cpu-thermal", "soc_thermal"):
            if key in temps and temps[key]:
                return round(temps[key][0].current, 1)
    except (AttributeError, NotImplementedError):
        pass
    return None


async def _stream():
    psutil.cpu_percent(interval=None)
    prev_net = psutil.net_io_counters()
    prev_t = time.monotonic()

    while True:
        await asyncio.sleep(2)
        now = time.monotonic()
        dt = now - prev_t

        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        load1, _, _ = psutil.getloadavg()

        send_kbps = max(0.0, (net.bytes_sent - prev_net.bytes_sent) / dt / 1024)
        recv_kbps = max(0.0, (net.bytes_recv - prev_net.bytes_recv) / dt / 1024)
        prev_net = net
        prev_t = now

        payload = {
            "cpu": round(cpu, 1),
            "mem_pct": round(mem.percent, 1),
            "mem_used": round(mem.used / 1024**3, 2),
            "mem_total": round(mem.total / 1024**3, 2),
            "disk_pct": round(disk.percent, 1),
            "disk_used": round(disk.used / 1024**3, 1),
            "disk_total": round(disk.total / 1024**3, 1),
            "temp": _cpu_temp(),
            "net_send": round(send_kbps, 1),
            "net_recv": round(recv_kbps, 1),
            "load1": round(load1, 2),
            "uptime": int(time.time() - psutil.boot_time()),
        }
        yield f"data: {json.dumps(payload)}\n\n"


@router.get("/", response_class=HTMLResponse, name="pi_health")
def pi_health(request: Request, user: User = Depends(require_auth)):
    return templates.TemplateResponse(
        "pi_health/dashboard.html", {"request": request, "user": user}
    )


@router.get("/stream/", name="pi_health_stream")
async def pi_health_stream(_: User = Depends(require_auth)):
    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/fan/spin/", name="pi_health_fan_spin")
async def fan_spin(
    seconds: int = Form(...),
    speed: int = Form(255),
    _: User = Depends(require_auth),
):
    if not 1 <= seconds <= 3600:
        return JSONResponse({"error": "seconds must be 1–3600"}, status_code=422)
    if not 0 <= speed <= 255:
        return JSONResponse({"error": "speed must be 0–255"}, status_code=422)

    path = _pwm_path()
    if path is None:
        return JSONResponse({"error": "Fan PWM not found"}, status_code=503)

    if _fan["task"] and not _fan["task"].done():
        _fan["task"].cancel()
        try:
            await _fan["task"]
        except asyncio.CancelledError:
            pass

    try:
        with open(path) as f:
            original = f.read().strip()
    except PermissionError:
        return JSONResponse({"error": "Permission denied writing to PWM"}, status_code=403)

    _fan["speed"] = speed
    _fan["ends_at"] = time.monotonic() + seconds
    _fan["task"] = asyncio.create_task(_spin(seconds, speed, path, original))
    return JSONResponse({"ok": True, "seconds": seconds, "speed": speed})


@router.get("/fan/status/", name="pi_health_fan_status")
async def fan_status(_: User = Depends(require_auth)):
    spinning = bool(_fan["task"] and not _fan["task"].done())
    remaining = max(0.0, _fan["ends_at"] - time.monotonic()) if spinning else 0.0
    return JSONResponse({
        "spinning": spinning,
        "seconds_remaining": round(remaining, 1),
        "speed": _fan["speed"] if spinning else 0,
    })
