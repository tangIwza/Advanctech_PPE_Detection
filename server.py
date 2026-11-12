import base64
import os
import shutil
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import uvicorn
import uuid
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from ppe_engine import YOLOPPEEngine

BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"
CAPTURES_DIR = BASE_DIR / "captures"
LABELS_DIR = BASE_DIR / "labels_out"
STATIC_DIR = BASE_DIR / "static"
VIDEOS_DIR = BASE_DIR / "uploads"
DATA_YAML_PATH = BASE_DIR / "data.yaml"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
LABELS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Copy sample video from Downloads if available and not yet in uploads
DOWNLOADS_SAMPLE_VIDEO = Path(r"C:\Users\DELL\Downloads\Safety Helmet Videos.mp4")
if DOWNLOADS_SAMPLE_VIDEO.exists() and not (VIDEOS_DIR / "Safety Helmet Videos.mp4").exists():
    try:
        shutil.copy2(DOWNLOADS_SAMPLE_VIDEO, VIDEOS_DIR / "Safety Helmet Videos.mp4")
    except Exception:
        pass


def imwrite_unicode(path: str, img: np.ndarray) -> bool:
    try:
        ext = os.path.splitext(path)[1] or ".jpg"
        success, encoded = cv2.imencode(ext, img)
        if success:
            encoded.tofile(path)
            return True
        return False
    except Exception:
        return False


def img_to_base64(bgr_img: Optional[np.ndarray], quality: int = 86) -> str:
    if bgr_img is None:
        return ""
    ok, buf = cv2.imencode(".jpg", bgr_img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def find_initial_model() -> Path:
    # Prefer custom trained PPE weights if present in workspace or models/
    candidates = [
        MODELS_DIR / "best.pt",
        BASE_DIR / "best.pt",
        BASE_DIR / "ppe_best.pt",
        MODELS_DIR / "ppe_best.pt",
        BASE_DIR / "best.onnx",
        MODELS_DIR / "best.onnx",
        BASE_DIR / "yolov8n.pt",
        MODELS_DIR / "yolov8n.pt",
    ]
    for c in candidates:
        if c.exists():
            return c
    return BASE_DIR / "yolov8n.pt"


engine = YOLOPPEEngine(find_initial_model())


class RuntimeState:
    def __init__(self):
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running: bool = False
        self.source: str = "0"
        self.fps: float = 0.0
        self.latest_jpeg: Optional[bytes] = None
        self.lock = threading.Lock()

        self.current_prediction: dict = engine.empty_prediction()
        self.class_totals = dict.fromkeys(engine.PPE_CLASS_NAMES.values(), 0)
        self.logs: List[dict] = []
        self.last_log_time: float = 0.0
        self.total_frames_tested: int = 0
        self.total_helmets_detected: int = 0
        self.total_vests_detected: int = 0
        self.total_persons_detected: int = 0
        self.last_labeled_video_url: str = ""

    def add_log(
        self,
        event_type: str,
        counts: Dict[str, int],
        total_boxes: int,
        snapshot_url: str = "",
        label_url: str = "",
        message: str = "",
    ):
        entry = {
            "id": int(time.time() * 1000) + len(self.logs),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": event_type,  # "PPE_COMPLIANT", "MISSING_PPE", "IMAGE_LABELED", "SYSTEM"
            "counts": counts,
            "total_boxes": total_boxes,
            "snapshot_url": snapshot_url,
            "label_url": label_url,
            "message": message,
        }
        self.logs.insert(0, entry)
        if len(self.logs) > 120:
            self.logs = self.logs[:120]


runtime = RuntimeState()
runtime.add_log(
    "SYSTEM",
    engine.empty_prediction()["counts"],
    0,
    message=f"Initialized PPE Detection Pipeline with '{engine.model_path.name}' (Classes: {engine.PPE_CLASS_NAMES})",
)


def count_summary(counts):
    return ", ".join(f"{name}: {count}" for name, count in counts.items() if count) or "no objects"


def detection_event(info):
    if info["is_compliant"] is None:
        return "DETECTION"
    return "PPE_COMPLIANT" if info["is_compliant"] else "MISSING_PPE"


def record_prediction(info):
    with runtime.lock:
        runtime.total_frames_tested += 1
        runtime.current_prediction = info
        for name, count in info["counts"].items():
            runtime.class_totals[name] = runtime.class_totals.get(name, 0) + count
        runtime.total_persons_detected = runtime.class_totals.get("person", 0)
        runtime.total_helmets_detected = runtime.class_totals.get("helmet", 0)
        runtime.total_vests_detected = runtime.class_totals.get("safety-vest", 0)


def record_stream_detection(annotated: np.ndarray, info: dict, source_tag: str = "Stream"):
    record_prediction(info)
    now = time.time()

    c = info["counts"]
    if info["total_boxes"] > 0 and (now - runtime.last_log_time >= 3.0):
        runtime.last_log_time = now

        ts_file = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        img_name = f"ppe_{ts_file}.jpg"
        txt_name = f"ppe_{ts_file}.txt"

        imwrite_unicode(str(CAPTURES_DIR / img_name), annotated)
        (LABELS_DIR / txt_name).write_text(info["yolo_labels_txt"], encoding="utf-8")

        ev_type = detection_event(info)
        runtime.add_log(
            ev_type,
            c,
            info["total_boxes"],
            snapshot_url=f"/captures/{img_name}",
            label_url=f"/labels_out/{txt_name}",
            message=f"[{source_tag}] Labeled {info['total_boxes']} objects ({count_summary(c)})",
        )


def camera_worker():
    prev_time = time.time()
    while runtime.is_running and runtime.cap is not None:
        ret, frame = runtime.cap.read()
        if not ret or frame is None:
            if not str(runtime.source).isdigit() and os.path.exists(str(runtime.source)):
                runtime.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            time.sleep(0.05)
            continue

        annotated, info = engine.predict_frame(frame)
        record_stream_detection(annotated, info, source_tag="Video/Stream")

        now = time.time()
        runtime.fps = round(1.0 / max(1e-4, now - prev_time), 1)
        prev_time = now

        # Resize display frame if > 1280w for smooth MJPEG streaming
        disp = annotated
        if disp.shape[1] > 1280:
            scale = 1280.0 / disp.shape[1]
            disp = cv2.resize(disp, (1280, int(disp.shape[0] * scale)), interpolation=cv2.INTER_AREA)

        ok, buf = cv2.imencode(".jpg", disp, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if ok:
            with runtime.lock:
                runtime.latest_jpeg = buf.tobytes()

        time.sleep(0.01)


app = FastAPI(title="YOLOv8 PPE Detection & Auto-Labeling Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CameraStartRequest(BaseModel):
    source: str = "0"


class ThresholdRequest(BaseModel):
    threshold: float


class FrameRequest(BaseModel):
    image_base64: str


@app.get("/api/status")
def get_status():
    sample_video_exists = (VIDEOS_DIR / "Safety Helmet Videos.mp4").exists()
    return {
        "is_running": runtime.is_running,
        "source": runtime.source,
        "fps": runtime.fps if runtime.is_running else 0.0,
        "threshold": round(engine.conf_threshold, 2),
        **engine.model_info(),
        "current_prediction": runtime.current_prediction,
        "total_frames_tested": runtime.total_frames_tested,
        "total_class_detections": runtime.class_totals.copy(),
        "total_persons_detected": runtime.total_persons_detected,
        "total_helmets_detected": runtime.total_helmets_detected,
        "total_vests_detected": runtime.total_vests_detected,
        "sample_video_available": sample_video_exists,
        "last_labeled_video_url": runtime.last_labeled_video_url,
    }


@app.post("/api/threshold")
def set_threshold(req: ThresholdRequest):
    engine.conf_threshold = max(0.05, min(0.95, float(req.threshold)))
    return {"success": True, "threshold": engine.conf_threshold}


@app.post("/api/upload_model")
async def upload_model(file: UploadFile = File(...)):
    """Upload a trained YOLO .pt or .onnx model weight file (e.g. best.pt) and hot-reload the engine."""
    filename = Path((file.filename or "best.pt").replace("\\", "/")).name
    if not filename.lower().endswith((".pt", ".onnx")):
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์โมเดลนามสกุล .pt หรือ .onnx เท่านั้น")

    save_path = MODELS_DIR / f"{uuid.uuid4().hex[:12]}_{filename}"
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    try:
        engine.reload_model(save_path)
        runtime.current_prediction = engine.empty_prediction()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ไม่สามารถโหลดไฟล์โมเดลได้: {e}")

    runtime.add_log(
        "SYSTEM",
        engine.empty_prediction()["counts"],
        0,
        message=f"Switched active model weights to '{filename}' (Custom PPE weights: {engine.is_custom_ppe_model})",
    )
    return {
        "success": True,
        "model_name": engine.model_path.name,
        "is_custom_ppe_model": engine.is_custom_ppe_model,
        "raw_names": engine.raw_names,
        "classes": engine.PPE_CLASS_NAMES,
        "model_sha256": engine.model_sha256,
    }


@app.post("/api/camera/start")
def start_camera(req: CameraStartRequest):
    if runtime.is_running:
        stop_camera()

    src_str = req.source.strip()
    source = int(src_str) if src_str.isdigit() else src_str

    if isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถเปิดกล้องหรือไฟล์วิดีโอจาก '{src_str}' ได้",
        )

    runtime.cap = cap
    runtime.source = src_str
    runtime.is_running = True
    runtime.add_log(
        "SYSTEM",
        engine.empty_prediction()["counts"],
        0,
        message=f"Started PPE video/stream detection (Source: {Path(src_str).name if not src_str.isdigit() else src_str})",
    )
    threading.Thread(target=camera_worker, daemon=True).start()
    return {"success": True, "source": src_str}


@app.post("/api/camera/stop")
def stop_camera():
    runtime.is_running = False
    time.sleep(0.1)
    if runtime.cap is not None:
        runtime.cap.release()
        runtime.cap = None
    runtime.latest_jpeg = None
    return {"success": True}


@app.post("/api/upload_video")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file (.mp4/.avi/.mov) and start real-time PPE detection & labeling on it."""
    safe_name = "".join(c for c in (file.filename or "test_video.mp4") if c not in r'\/:*?"<>|')
    save_path = VIDEOS_DIR / safe_name
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    return start_camera(CameraStartRequest(source=str(save_path)))


@app.post("/api/play_sample_video")
def play_sample_video():
    """Start streaming the sample 'Safety Helmet Videos.mp4' or notebook predicted video."""
    sample_path = VIDEOS_DIR / "Safety Helmet Videos.mp4"
    if not sample_path.exists() and DOWNLOADS_SAMPLE_VIDEO.exists():
        shutil.copy2(DOWNLOADS_SAMPLE_VIDEO, sample_path)
    if not sample_path.exists():
        fallback = STATIC_DIR / "assets" / "notebook_predicted_video.mp4"
        if fallback.exists():
            sample_path = fallback
        else:
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์วิดีโอตัวอย่าง")

    return start_camera(CameraStartRequest(source=str(sample_path)))


@app.post("/api/export_labeled_video")
def export_labeled_video():
    """Render and save a complete annotated .mp4 file of the currently selected video in uploads/."""
    src_path = Path(runtime.source)
    if not src_path.exists() or not src_path.is_file():
        sample_path = VIDEOS_DIR / "Safety Helmet Videos.mp4"
        if sample_path.exists():
            src_path = sample_path
        else:
            raise HTTPException(status_code=400, detail="กรุณาอัปโหลดหรือเลือกไฟล์วิดีโอก่อนส่งออก")

    cap = cv2.VideoCapture(str(src_path))
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="ไม่สามารถเปิดไฟล์วิดีโอต้นฉบับได้")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

    # Cap output width at 1280p for fast export & easy playback
    if orig_w > 1280:
        out_w = 1280
        out_h = int(round(orig_h * (1280.0 / orig_w)))
    else:
        out_w, out_h = orig_w, orig_h

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"labeled_{src_path.stem}_{ts}.mp4"
    out_path = CAPTURES_DIR / out_name

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (out_w, out_h))

    frames_count = 0
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        if ( frame.shape[1], frame.shape[0] ) != ( out_w, out_h ):
            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)
        annotated, _ = engine.predict_frame(frame)
        writer.write(annotated)
        frames_count += 1

    cap.release()
    writer.release()

    runtime.last_labeled_video_url = f"/captures/{out_name}"
    runtime.add_log(
        "SYSTEM",
        engine.empty_prediction()["counts"],
        frames_count,
        snapshot_url="",
        message=f"Exported full labeled video '{out_name}' ({frames_count} frames) to captures/",
    )
    return {
        "success": True,
        "video_url": runtime.last_labeled_video_url,
        "filename": out_name,
        "frames_processed": frames_count,
    }


@app.post("/api/process_frame")
def process_frame(req: FrameRequest):
    raw_b64 = req.image_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    img_bytes = base64.b64decode(raw_b64)
    nparr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid frame")

    annotated, info = engine.predict_frame(frame)
    record_stream_detection(annotated, info, source_tag="Webcam")

    return {
        "annotated_base64": img_to_base64(annotated),
        "prediction": info,
    }


@app.post("/api/test_image")
def test_single_image(file: UploadFile = File(...)):
    """Upload 1 or more images to run PPE detection, draw bounding boxes, and export YOLO .txt labels."""
    content = file.file.read()
    nparr = np.frombuffer(content, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="ไม่สามารถอ่านไฟล์รูปภาพนี้ได้")

    annotated, info = engine.predict_frame(frame)
    record_prediction(info)

    c = info["counts"]

    ts_file = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    safe_stem = "".join(ch for ch in Path(file.filename or "image").stem if ch.isalnum() or ch in ("_", "-"))[:30] or "image"
    img_filename = f"labeled_{safe_stem}_{ts_file}.jpg"
    txt_filename = f"labeled_{safe_stem}_{ts_file}.txt"

    imwrite_unicode(str(CAPTURES_DIR / img_filename), annotated)
    (LABELS_DIR / txt_filename).write_text(info["yolo_labels_txt"], encoding="utf-8")

    ev_type = detection_event(info)
    runtime.add_log(
        ev_type,
        c,
        info["total_boxes"],
        snapshot_url=f"/captures/{img_filename}",
        label_url=f"/labels_out/{txt_filename}",
        message=f"[Image: {file.filename}] Detected {info['total_boxes']} objects ({count_summary(c)})",
    )

    return {
        "filename": file.filename,
        "annotated_base64": img_to_base64(annotated, quality=90),
        "snapshot_url": f"/captures/{img_filename}",
        "label_url": f"/labels_out/{txt_filename}",
        "prediction": info,
    }


def mjpeg_generator():
    while runtime.is_running:
        with runtime.lock:
            frame_bytes = runtime.latest_jpeg
        if frame_bytes:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
        time.sleep(0.03)


@app.get("/api/video_feed")
def video_feed():
    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/logs")
def get_logs():
    return {"logs": runtime.logs}


@app.delete("/api/logs")
def clear_logs():
    runtime.logs.clear()
    return {"success": True}


@app.post("/api/open_captures")
def open_captures():
    try:
        os.startfile(str(CAPTURES_DIR))
    except Exception:
        pass
    return {"success": True}


@app.post("/api/open_labels")
def open_labels():
    try:
        os.startfile(str(LABELS_DIR))
    except Exception:
        pass
    return {"success": True}


app.mount("/captures", StaticFiles(directory=str(CAPTURES_DIR)), name="captures")
app.mount("/labels_out", StaticFiles(directory=str(LABELS_DIR)), name="labels_out")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    port = 8070
    url = f"http://localhost:{port}"
    print(f"Starting YOLOv8 PPE Detection & Auto-Labeling Server at {url}")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

