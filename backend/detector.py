import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np

from .rules import Detection, classify_name


class Detector:
    def __init__(self, settings):
        config = settings.data_dir / "ultralytics"
        config.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(config))
        os.environ.setdefault("YOLO_OFFLINE", "true")
        from ultralytics import YOLO

        if not settings.model_path.is_file():
            raise FileNotFoundError(f"Model not found: {settings.model_path}")
        self.model = YOLO(str(settings.model_path))
        if self.model.task != "detect":
            raise ValueError("best.pt must be a YOLO detection model")
        names = self.model.names
        self.names = {int(key): str(value) for key, value in names.items()}
        if len(self.names) != 10:
            raise ValueError(f"Expected the custom ten-class checkpoint, found {len(self.names)} classes")
        self.person_ids = {key for key, name in self.names.items() if classify_name(name) == "person"}
        self.ppe_ids = {key for key, name in self.names.items() if classify_name(name) == "ppe"}
        if not self.person_ids:
            raise ValueError("No person/human/worker class found in model.names")
        self.settings = settings
        self.sha256 = hashlib.sha256(settings.model_path.read_bytes()).hexdigest()
        self.training = None
        sidecar = settings.model_path.with_suffix(".metadata.json")
        if sidecar.exists():
            value = json.loads(sidecar.read_text(encoding="utf-8"))
            if value.get("sha256") == self.sha256:
                self.training = value
        # Validate the configured device and initialize inference before readiness.
        self.predict(np.zeros((settings.image_size, settings.image_size, 3), dtype=np.uint8), 0.25)

    def info(self):
        palette = ["#3b82f6", "#8b5cf6", "#06b6d4", "#64748b", "#d946ef", "#14b8a6", "#22c55e", "#f97316", "#6366f1", "#eab308"]
        return {
            "model_name": self.settings.model_path.name, "sha256": self.sha256,
            "device": self.settings.device, "class_count": len(self.names),
            "classes": [{"id": key, "name": name, "kind": classify_name(name), "color": palette[key % len(palette)]}
                        for key, name in self.names.items()],
            "person_class_ids": sorted(self.person_ids), "ppe_class_ids": sorted(self.ppe_ids),
            "training": self.training,
        }

    def predict(self, frame, confidence):
        height, width = frame.shape[:2]
        start = time.perf_counter()
        result = self.model.predict(frame, conf=confidence, imgsz=self.settings.image_size,
                                    device=self.settings.device, max_det=100, verbose=False)[0]
        detections = []
        if result.boxes is not None:
            for row in result.boxes.data.cpu().tolist():
                x1, y1, x2, y2, score, class_id = row[:6]
                class_id = int(class_id)
                box = (max(0, x1 / width), max(0, y1 / height), min(1, x2 / width), min(1, y2 / height))
                if class_id in self.names and box[2] > box[0] and box[3] > box[1]:
                    detections.append(Detection(class_id, self.names[class_id], float(score), box))
        return detections, (time.perf_counter() - start) * 1000
