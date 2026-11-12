import asyncio
from contextlib import asynccontextmanager, suppress
import csv
import io
import logging
from pathlib import Path
import secrets
import time
import uuid

import cv2
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import ValidationError

from .config import Settings
from .detector import Detector
from .monitor import Monitor
from .rules import classify_name
from .schemas import MonitorSettings, StartRequest, ZoneInput, ZonePatch
from .store import ConflictError, Store

logger = logging.getLogger(__name__)


class BodyTooLarge(HTTPException):
    def __init__(self):
        super().__init__(status_code=413, detail="Video exceeds the upload size limit")


class UploadLimitMiddleware:
    def __init__(self, app, limit):
        self.app, self.limit = app, limit + 1024 * 1024

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/api/videos":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        length = headers.get(b"content-length", b"0")
        if length.isdigit() and int(length) > self.limit:
            return await JSONResponse({"detail": "Video exceeds the upload size limit"}, status_code=413)(scope, receive, send)
        count = 0

        async def limited_receive():
            nonlocal count
            message = await receive()
            count += len(message.get("body", b""))
            if count > self.limit:
                raise BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except BodyTooLarge:
            await JSONResponse({"detail": "Video exceeds the upload size limit"}, status_code=413)(scope, receive, send)


def create_app(settings=None, detector_factory=Detector):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        detector = await asyncio.to_thread(detector_factory, settings)
        store = Store(settings, detector.names)
        store.close_interrupted_alerts()
        store.prune()
        monitor = Monitor(settings, detector, store)
        app.state.detector, app.state.store, app.state.monitor = detector, store, monitor
        app.state.clients = set()
        try:
            yield
        finally:
            await asyncio.to_thread(monitor.stop)

    app = FastAPI(title="Smart Safety & PPE Monitoring", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(UploadLimitMiddleware, limit=settings.max_upload_bytes)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"], expose_headers=["Content-Disposition"])

    @app.middleware("http")
    async def protect_api(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method != "OPTIONS":
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in settings.allowed_origins:
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
            if settings.api_token:
                value = request.headers.get("authorization", "")
                if not value.startswith("Bearer ") or not secrets.compare_digest(value[7:], settings.api_token):
                    return JSONResponse({"detail": "API token required"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(KeyError)
    async def not_found(request, error):
        return JSONResponse({"detail": "Record or source not found"}, status_code=404)

    @app.exception_handler(ConflictError)
    async def conflict(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(RuntimeError)
    async def unavailable(request, error):
        return JSONResponse({"detail": str(error)}, status_code=503)

    @app.get("/health")
    def health():
        return {"status": "ok", "model_loaded": True, "monitor_state": app.state.monitor.state}

    @app.get("/api/classes")
    def classes():
        return app.state.detector.info()

    @app.get("/api/status")
    def status():
        return app.state.monitor.snapshot()[0]

    @app.get("/api/settings")
    def get_settings():
        return {**app.state.store.monitor_settings().model_dump(), "max_upload_mb": settings.max_upload_bytes // (1024*1024),
                "max_zones": settings.max_zones, "retention_days": settings.retention_days,
                "authentication_enabled": bool(settings.api_token)}

    @app.put("/api/settings")
    def save_settings(value: MonitorSettings):
        app.state.store.save_settings(value)
        app.state.monitor.refresh(rules_changed=True)
        return get_settings()

    @app.get("/api/videos")
    def videos():
        return {"items": app.state.monitor.videos()}

    def probe_video(path):
        cap = cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened():
                raise ValueError("Unsupported or unreadable video")
            width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            if width <= 0 or height <= 0 or width * height > 40_000_000:
                raise ValueError("Unsupported video dimensions")
            ok, frame = cap.read()
            if not ok or frame is None:
                raise ValueError("Video has no readable frames")
        finally:
            cap.release()

    @app.post("/api/videos", status_code=201)
    async def upload_video(file: UploadFile = File(...)):
        name = Path((file.filename or "video").replace("\\", "/")).name
        name = "".join(character for character in name if character.isprintable())[:160]
        suffix = Path(name).suffix.lower()
        if suffix not in {".mp4", ".avi", ".mov"}:
            raise HTTPException(400, "Supported video formats: .mp4, .avi, .mov")
        video_id = uuid.uuid4().hex
        path = app.state.store.uploads / (video_id + suffix)
        count = 0
        try:
            with path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    count += len(chunk)
                    if count > settings.max_upload_bytes:
                        raise HTTPException(413, "Video exceeds the upload size limit")
                    await asyncio.to_thread(output.write, chunk)
            await asyncio.to_thread(probe_video, path)
            app.state.store.add_video(video_id, name, path.name, count)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return {"id": video_id, "name": name, "size": count, "sample": False}

    @app.post("/api/stream/start")
    def start(value: StartRequest):
        app.state.monitor.start(value)
        return status()

    @app.post("/api/stream/stop")
    def stop():
        app.state.monitor.stop()
        return status()

    @app.post("/api/stream/pause")
    def pause():
        app.state.monitor.pause(True)
        return status()

    @app.post("/api/stream/resume")
    def resume():
        app.state.monitor.pause(False)
        return status()

    @app.get("/api/zones")
    def zones(source_id: str = Query(min_length=1, max_length=120)):
        return {"items": app.state.store.zones(source_id)}

    def validate_zone(value):
        if set(value.required_class_ids) - app.state.detector.ppe_ids:
            raise HTTPException(422, "Required classes must be wearable PPE; person and body-part classes cannot be required equipment")

    @app.post("/api/zones", status_code=201)
    def create_zone(value: ZoneInput):
        validate_zone(value)
        zone = app.state.store.create_zone(value)
        app.state.monitor.refresh(rules_changed=True)
        return zone

    @app.patch("/api/zones/{zone_id}")
    def update_zone(zone_id: str, value: ZonePatch):
        old = app.state.store.zone(zone_id)
        changes = value.model_dump(exclude_unset=True)
        expected = changes.pop("expected_version", None)
        if any(item is None for item in changes.values()):
            raise HTTPException(422, "Zone fields cannot be null")
        try:
            merged = ZoneInput.model_validate({**old.model_dump(exclude={"id", "version", "updated_at"}), **changes})
        except ValidationError as error:
            raise HTTPException(422, str(error)) from error
        validate_zone(merged)
        zone = app.state.store.update_zone(merged, zone_id, expected)
        app.state.monitor.refresh(rules_changed=True)
        return zone

    @app.delete("/api/zones/{zone_id}", status_code=204)
    def delete_zone(zone_id: str):
        app.state.store.delete_zone(zone_id)
        app.state.monitor.refresh(rules_changed=True)
        return Response(status_code=204)

    @app.get("/api/alerts")
    def alerts(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
               kind: str | None = Query(default=None, pattern="^(intrusion|missing_ppe)$"), acknowledged: bool | None = None):
        return app.state.store.alerts(limit, offset, kind, acknowledged)

    @app.post("/api/alerts/{alert_id}/acknowledge")
    def acknowledge(alert_id: str):
        app.state.store.acknowledge(alert_id)
        app.state.monitor.refresh()
        return {"ok": True}

    @app.get("/api/alerts/{alert_id}/snapshot")
    def snapshot(alert_id: str):
        return FileResponse(app.state.store.snapshot_path(alert_id), media_type="image/jpeg")

    @app.get("/api/alerts/export")
    def export_alerts():
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["time_utc", "type", "zone", "source", "track_id", "missing_ppe", "acknowledged_at", "closed_at"])
        for row in app.state.store.alerts(limit=settings.max_alerts)["items"]:
            values = [row["created_at"], row["kind"], row["zone_name"], row["source_name"], row["track_id"],
                      ", ".join(row["missing_classes"]), row["acknowledged_at"] or "", row["resolved_at"] or ""]
            writer.writerow(["'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value for value in values])
        return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="safety-alerts.csv"'})

    @app.websocket("/ws/stream")
    async def stream(websocket: WebSocket):
        origin = websocket.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.allowed_origins:
            await websocket.close(code=4403)
            return
        protocols = [value.strip() for value in websocket.headers.get("sec-websocket-protocol", "").split(",")]
        supplied = next((value[7:] for value in protocols if value.startswith("bearer.")), "")
        if settings.api_token and not secrets.compare_digest(supplied, settings.api_token):
            await websocket.close(code=4401)
            return
        if len(app.state.clients) >= 16:
            await websocket.close(code=4429)
            return
        app.state.clients.add(id(websocket))
        await websocket.accept(subprotocol="safety-stream" if "safety-stream" in protocols else None)

        async def receive_until_disconnect():
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return

        receiver = asyncio.create_task(receive_until_disconnect())
        last, heartbeat = -1, time.monotonic()
        try:
            while not receiver.done():
                monitor = app.state.monitor
                if monitor.revision != last:
                    packet, jpeg = await asyncio.to_thread(monitor.snapshot)
                    await asyncio.wait_for(websocket.send_json(packet), 8)
                    if jpeg:
                        await asyncio.wait_for(websocket.send_bytes(jpeg), 8)
                    last = packet["sequence"]
                    heartbeat = time.monotonic()
                elif time.monotonic() - heartbeat > 10:
                    await websocket.send_json({"type": "heartbeat"})
                    heartbeat = time.monotonic()
                await asyncio.sleep(0.075)
        except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError, OSError):
            pass
        finally:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
            app.state.clients.discard(id(websocket))

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith(("api/", "ws/")):
            raise HTTPException(404, "Endpoint not found")
        candidate = (settings.frontend_dir / path).resolve()
        if candidate.is_relative_to(settings.frontend_dir.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        index = settings.frontend_dir / "index.html"
        if index.is_file():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return JSONResponse({"message": "Backend ready. Run the frontend on http://localhost:5173 or build frontend/dist."})

    return app


app = create_app()
