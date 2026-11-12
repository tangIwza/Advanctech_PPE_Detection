import hashlib
import logging
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
import uuid

import cv2

from .config import ROOT
from .rules import PersonTracker, evaluate_zones
from .store import utc_now

logger = logging.getLogger(__name__)


def draw_overlay(frame, detections, zones, evaluation):
    image = frame.copy()
    h, w = image.shape[:2]
    red_people = {item["track_id"] for item in evaluation["violations"]}
    red_zones = {item["zone_id"] for item in evaluation["violations"]}
    for zone in zones:
        if not zone.enabled:
            continue
        color = (68, 68, 239) if zone.id in red_zones else (30, 160, 245) if zone.kind == "restricted" else (100, 190, 30)
        r = zone.rect
        a, b = (int(r.x1*w), int(r.y1*h)), (int(r.x2*w), int(r.y2*h))
        cv2.rectangle(image, a, b, color, 2)
        cv2.putText(image, zone.name.encode("ascii", "replace").decode()[:35], (a[0]+4, min(h-8, a[1]+20)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    for item in detections:
        a, b = (int(item.bbox[0]*w), int(item.bbox[1]*h)), (int(item.bbox[2]*w), int(item.bbox[3]*h))
        color = (68, 68, 239) if item.track_id in red_people else (240, 135, 60) if item.track_id else (70, 200, 70)
        cv2.rectangle(image, a, b, color, 2)
        label = f"{item.class_name}{' #' + str(item.track_id) if item.track_id else ''} {item.confidence:.2f}"
        cv2.putText(image, label, (a[0]+2, max(15, a[1]-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    return image


class Monitor:
    """One decoder/inference worker shared by all connected viewers."""

    def __init__(self, settings, detector, store):
        self.settings, self.detector, self.store = settings, detector, store
        self.lock = threading.RLock()
        self.lifecycle = threading.RLock()
        self.evaluation_lock = threading.RLock()
        self.stop_event = threading.Event()
        self.paused = threading.Event()
        self.thread = None
        self.revision = 0
        self.state = "idle"
        self.error = None
        self.source = None
        self.jpeg = None
        self.last_frame = None
        self.detections = []
        self.evaluation = {"violations": [], "zone_results": [], "people": []}
        self.gates = {}
        self.tracker = PersonTracker()
        self.frame_id = 0
        self.frames_processed = 0
        self.fps = 0.0
        self.inference_ms = 0.0
        self.position_seconds = 0.0
        self.duration_seconds = 0.0
        self.ready_event = threading.Event()

    def videos(self):
        videos = [{"id": row["id"], "name": row["name"], "size": row["size"], "sample": False}
                  for row in self.store.videos()]
        if (ROOT / "uploads/Safety Helmet Videos.mp4").is_file():
            videos.insert(0, {"id": "sample-video", "name": "Safety Helmet Videos.mp4", "size": 0, "sample": True})
        return videos

    def resolve_source(self, request):
        if request.kind == "camera":
            address = request.address.strip()
            if address.isdigit():
                if int(address) > 32:
                    raise ValueError("Camera index must be between 0 and 32")
                target = int(address)
                label = f"Camera {target}"
            else:
                parsed = urlsplit(address)
                if parsed.scheme not in {"rtsp", "rtsps", "http", "https"} or not parsed.hostname:
                    raise ValueError("Enter a camera index or an RTSP/HTTP(S) stream URL")
                target, label = address, "Network camera"
            return {"id": "camera-" + hashlib.sha256(address.encode()).hexdigest()[:24], "name": label,
                    "kind": "camera", "loop": False}, target
        if request.video_id == "sample-video" and (ROOT / "uploads/Safety Helmet Videos.mp4").is_file():
            return {"id": "sample-video", "name": "Safety Helmet Videos.mp4", "kind": "video", "loop": request.loop}, str(ROOT / "uploads/Safety Helmet Videos.mp4")
        for video in self.store.videos():
            if video["id"] == request.video_id:
                return {"id": video["id"], "name": video["name"], "kind": "video", "loop": request.loop}, str(self.store.uploads / video["filename"])
        raise KeyError("Video not found")

    def start(self, request):
        source, target = self.resolve_source(request)
        with self.lifecycle:
            self.stop()
            with self.lock:
                self.source, self.state, self.error = source, "opening", None
                self.jpeg, self.last_frame = None, None
                self.detections = []
                self.evaluation = {"violations": [], "zone_results": [], "people": []}
                self.tracker = PersonTracker()
                self.frames_processed = 0
                self.position_seconds = self.duration_seconds = 0
                self.stop_event = threading.Event()
                self.paused.clear()
                self.ready_event.clear()
                self.revision += 1
            self.thread = threading.Thread(target=self._worker, args=(source, target), name="ppe-inference", daemon=True)
            self.thread.start()
            if not self.ready_event.wait(8):
                self.stop_event.set()
                raise RuntimeError("Opening the source timed out; wait for it to stop before retrying")
            if self.error:
                raise ValueError(self.error)

    def stop(self):
        with self.lifecycle:
            self.stop_event.set()
            self.paused.clear()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=8)
                if self.thread.is_alive():
                    raise RuntimeError("The capture driver is still stopping; retry shortly")
            with self.evaluation_lock:
                for entry in self.gates.values():
                    self.store.resolve(entry["id"], "monitoring_stopped")
                self.gates.clear()
            with self.lock:
                if self.source:
                    self.state = "stopped"
                self.fps = 0
                self.revision += 1

    def pause(self, value):
        with self.lock:
            if self.state not in {"running", "paused"}:
                raise ValueError("No running source")
            self.paused.set() if value else self.paused.clear()
            self.state = "paused" if value else "running"
            self.revision += 1

    def _capture(self, target):
        if isinstance(target, int):
            cap = cv2.VideoCapture(target, cv2.CAP_DSHOW) if __import__('os').name == "nt" else cv2.VideoCapture(target)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            return cap
        if str(target).startswith(("rtsp://", "rtsps://", "http://", "https://")):
            return cv2.VideoCapture(target, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
        return cv2.VideoCapture(target)

    def _worker(self, source, target):
        cap = None
        try:
            cap = self._capture(target)
            if not cap.isOpened():
                raise ValueError("Unable to open the video or camera; check its connection and format")
            fps = cap.get(cv2.CAP_PROP_FPS)
            fps = fps if 0 < fps <= 240 else 25
            total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            with self.lock:
                self.duration_seconds = total / fps if source["kind"] == "video" and total > 0 else 0
                self.state = "running"
                self.revision += 1
            self.ready_event.set()
            skip_fraction = 0.0
            while not self.stop_event.is_set():
                if self.paused.wait(0) and not self.stop_event.wait(0.05):
                    continue
                started = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    if source["kind"] == "video" and source["loop"]:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        self.tracker = PersonTracker()
                        self._clear_gates()
                        continue
                    if source["kind"] == "video":
                        with self.lock:
                            self.state = "ended"
                        break
                    raise ValueError("Camera stream disconnected; reconnect the source")
                h, w = frame.shape[:2]
                scale = min(1, 1280 / w, 960 / h)
                if scale < 1:
                    frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
                options = self.store.monitor_settings()
                detections, inference_ms = self.detector.predict(frame, options.confidence)
                if self.stop_event.is_set():
                    break
                if self.paused.is_set():
                    continue
                with self.evaluation_lock:
                    people = [item for item in detections if item.class_id in self.detector.person_ids]
                    self.tracker.update(people, time.monotonic())
                    self._evaluate(frame, detections, emit=True)
                    success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                    if not success:
                        raise ValueError("Unable to encode video frame")
                    with self.lock:
                        self.last_frame, self.detections = frame, detections
                        self.jpeg = buffer.tobytes()
                        self.frame_id += 1
                        self.frames_processed += 1
                        self.inference_ms = round(inference_ms, 1)
                        self.position_seconds = cap.get(cv2.CAP_PROP_POS_FRAMES) / fps if source["kind"] == "video" else 0
                        self.fps = round(1 / max(0.001, time.monotonic() - started), 1)
                        self.revision += 1
                self.stop_event.wait(max(0, 1 / min(fps, self.settings.max_fps) - (time.monotonic() - started)))
                if source["kind"] == "video":
                    skip_fraction += max(0, (time.monotonic() - started) * fps - 1)
                    skip = min(120, int(skip_fraction))
                    skip_fraction -= skip
                    for _ in range(skip):
                        if not cap.grab():
                            break
        except Exception as error:
            # Capture errors are deliberately generic: camera URLs can contain credentials.
            logger.error("Monitoring stopped (%s)", type(error).__name__)
            with self.lock:
                self.error = str(error) if isinstance(error, ValueError) else "Monitoring failed; inspect the backend log and reconnect"
                self.state = "error"
        finally:
            if cap is not None:
                cap.release()
            self.ready_event.set()
            self._clear_gates()
            with self.lock:
                if self.stop_event.is_set() and self.state != "error":
                    self.state = "stopped"
                self.fps = 0
                self.revision += 1

    def _clear_gates(self):
        with self.evaluation_lock:
            for entry in self.gates.values():
                self.store.resolve(entry["id"], "monitoring_stopped")
            self.gates.clear()

    def _evaluate(self, frame, detections, emit):
        source = self.source
        if not source:
            return
        zones = self.store.zones(source["id"])
        options = self.store.monitor_settings()
        evaluation = evaluate_zones(detections, zones, self.detector.person_ids, self.detector.ppe_ids, options.association_threshold)
        if emit:
            now = time.monotonic()
            current = {}
            for item in evaluation["violations"]:
                key = (item["zone_id"], item["track_id"], item["kind"], tuple(item["missing_class_ids"]))
                current[key] = item
            newcomers = [key for key in current if key not in self.gates]
            snapshot = None
            if newcomers:
                snapshot = uuid.uuid4().hex + '.jpg'
                annotated = draw_overlay(frame, detections, zones, evaluation)
                ok, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ok:
                    (self.store.snapshots / snapshot).write_bytes(buffer.tobytes())
                else:
                    snapshot = None
            for key, item in current.items():
                if key not in self.gates:
                    payload = {**item, "source_name": source["name"],
                               "missing_classes": [self.detector.names[value] for value in item["missing_class_ids"]]}
                    self.gates[key] = {"id": self.store.add_alert(payload, snapshot), "last_seen": now}
                self.gates[key]["last_seen"] = now
            enabled = {zone.id for zone in zones if zone.enabled}
            for key, entry in list(self.gates.items()):
                if key not in current and (key[0] not in enabled or now - entry["last_seen"] >= options.resolve_after_seconds):
                    self.store.resolve(entry["id"])
                    del self.gates[key]
            if newcomers:
                self.store.prune()
        with self.lock:
            self.evaluation = evaluation

    def refresh(self, rules_changed=False):
        with self.evaluation_lock:
            if self.last_frame is not None:
                self._evaluate(self.last_frame, self.detections, emit=self.state == "running")
                if rules_changed:
                    current = {(item["zone_id"], item["track_id"], item["kind"], tuple(item["missing_class_ids"])) for item in self.evaluation["violations"]}
                    for key, entry in list(self.gates.items()):
                        if key not in current:
                            self.store.resolve(entry["id"], "rule_changed")
                            del self.gates[key]
            with self.lock:
                self.revision += 1

    def snapshot(self):
        # Lock order matches the worker: evaluation first, then public state.
        with self.evaluation_lock, self.lock:
            zones = self.store.zones(self.source["id"]) if self.source else []
            counts = dict.fromkeys(self.detector.names.values(), 0)
            for detection in self.detections:
                counts[detection.class_name] += 1
            h, w = self.last_frame.shape[:2] if self.last_frame is not None else (0, 0)
            packet = {
                "type": "frame", "sequence": self.revision, "frame_id": self.frame_id,
                "timestamp": utc_now(), "has_frame": self.jpeg is not None,
                "width": w, "height": h, "state": self.state, "error": self.error,
                "source": self.source, "fps": self.fps, "inference_ms": self.inference_ms,
                "frames_processed": self.frames_processed, "position_seconds": self.position_seconds,
                "duration_seconds": self.duration_seconds, "counts": counts,
                "detections": [item.public() for item in self.detections],
                "zones": [zone.model_dump(mode="json") for zone in zones],
                **self.evaluation, "active_alert_count": len(self.gates),
                "alerts": self.store.alerts(limit=50)["items"],
            }
            return packet, self.jpeg
