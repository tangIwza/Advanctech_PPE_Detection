"""Native YOLO detection with checkpoint-owned class IDs and names."""

import hashlib
import json
from pathlib import Path
import threading

import cv2
from ultralytics import YOLO


class YOLOPPEEngine:
    # BGR colors, keyed by name so legacy and ten-class checkpoints agree.
    COLORS = {
        "person": (235, 130, 45), "ear-mufs": (180, 100, 220),
        "face-mask": (220, 190, 40), "foot": (160, 130, 100),
        "glasses": (210, 80, 160), "gloves": (80, 180, 180),
        "helmet": (40, 205, 65), "shoes": (150, 100, 240),
        "safety-suit": (190, 170, 60), "safety-vest": (20, 165, 250),
    }

    def __init__(self, model_path):
        self.lock = threading.RLock()
        self.conf_threshold = 0.25
        self.reload_model(model_path)

    def reload_model(self, model_path):
        path = Path(model_path).resolve()
        model = YOLO(str(path))
        if model.task != "detect":
            raise ValueError("Pipeline testing requires a YOLO object-detection model")
        raw_names = model.names
        names = dict(enumerate(raw_names)) if isinstance(raw_names, (list, tuple)) else dict(raw_names)
        names = {int(key): str(value) for key, value in sorted(names.items(), key=lambda pair: int(pair[0]))}
        if not names or set(names) != set(range(len(names))):
            raise ValueError("The model must contain contiguous class IDs starting at zero")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        report = None
        sidecar = path.with_suffix(".metadata.json")
        if sidecar.is_file():
            candidate = json.loads(sidecar.read_text(encoding="utf-8"))
            if candidate.get("sha256") == digest:
                report = candidate
        with self.lock:
            self.model = model
            self.model_path = path
            self.raw_names = names
            self.PPE_CLASS_NAMES = names.copy()
            self.CLASS_COLORS = {key: self.COLORS.get(name.lower(), (150, 170, 210)) for key, name in names.items()}
            self.is_custom_ppe_model = any(name.lower() in self.COLORS and name.lower() != "person" for name in names.values())
            self.model_sha256 = digest
            self.training_report = report

    def model_info(self):
        with self.lock:
            return {
                "model_name": self.model_path.name,
                "model_sha256": self.model_sha256,
                "task": "detect",
                "classes": self.PPE_CLASS_NAMES.copy(),
                "class_colors": {key: f"#{bgr[2]:02x}{bgr[1]:02x}{bgr[0]:02x}" for key, bgr in self.CLASS_COLORS.items()},
                "is_custom_ppe_model": self.is_custom_ppe_model,
                "inference_mode": "native_model",
                "compliance_scope": "helmet_count_only",
                "training_report": self.training_report,
            }

    def empty_prediction(self):
        with self.lock:
            return {
                "total_boxes": 0, "counts": dict.fromkeys(self.PPE_CLASS_NAMES.values(), 0),
                "classes": self.PPE_CLASS_NAMES.copy(), "model_sha256": self.model_sha256,
                "compliance_status": "READY", "is_compliant": None,
                "compliance_scope": "helmet_count_only", "detections": [], "yolo_labels_txt": "",
            }

    def predict_frame(self, frame):
        # Serialize inference and replacement so a frame's boxes and schema
        # always come from the same checkpoint, including during video export.
        with self.lock:
            return self._predict_frame(frame)

    def _predict_frame(self, frame):
        annotated = frame.copy()
        h, w = frame.shape[:2]
        scale = min(1.0, 1280.0 / max(h, w))
        infer_frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else frame
        results = self.model.predict(source=infer_frame, conf=self.conf_threshold, verbose=False)
        counts = dict.fromkeys(self.PPE_CLASS_NAMES.values(), 0)
        detections = []
        labels = []
        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            for box, confidence, class_id in zip(boxes.xyxy, boxes.conf, boxes.cls):
                class_id = int(class_id)
                if class_id not in self.PPE_CLASS_NAMES:
                    raise ValueError(f"Prediction class {class_id} is absent from checkpoint metadata")
                name = self.PPE_CLASS_NAMES[class_id]
                x1, y1, x2, y2 = [int(round(float(value) / scale)) for value in box]
                x1, x2 = max(0, min(w - 1, x1)), max(0, min(w - 1, x2))
                y1, y2 = max(0, min(h - 1, y1)), max(0, min(h - 1, y2))
                if x2 <= x1 or y2 <= y1:
                    continue
                detections.append({"class_id": class_id, "class_name": name, "confidence": round(float(confidence), 2), "bbox": [x1, y1, x2, y2]})
                counts[name] += 1
                labels.append(f"{class_id} {(x1+x2)/2/w:.6f} {(y1+y2)/2/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}")

        drawing_scale = max(0.6, min(2.2, min(w, h) / 720))
        thickness = max(2, round(2.5 * drawing_scale))
        font_scale = 0.58 * drawing_scale
        for detection in detections:
            x1, y1, x2, y2 = detection["bbox"]
            color = self.CLASS_COLORS[detection["class_id"]]
            text = f"{detection['class_name']} {detection['confidence']:.2f}"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            top = max(0, y1 - th - 8)
            cv2.rectangle(annotated, (x1, top), (min(w - 1, x1 + tw + 8), top + th + 8), color, -1)
            cv2.putText(annotated, text, (x1 + 4, top + th + 4), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

        # Preserve the existing helmet-count rule; it does not establish that
        # every worker is wearing all ten detected equipment/body-part classes.
        semantic = {name.lower(): count for name, count in counts.items()}
        persons, helmets = semantic.get("person", 0), semantic.get("helmet", 0)
        if "person" not in semantic or "helmet" not in semantic:
            status, compliant = "NOT_AVAILABLE", None
        elif persons:
            compliant = helmets >= persons
            status = "COMPLIANT" if compliant else "MISSING_PPE"
        else:
            status, compliant = ("PPE_DETECTED" if detections else "NO_PERSON"), None
        hud = f"Objects={len(detections)} | Persons={persons} | Helmets={helmets} | Vests={semantic.get('safety-vest', 0)}"
        cv2.rectangle(annotated, (8, 8), (min(w - 1, 15 + len(hud) * 10), 42), (15, 23, 42), -1)
        cv2.putText(annotated, hud, (14, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        return annotated, {
            "total_boxes": len(detections), "counts": counts,
            "classes": self.PPE_CLASS_NAMES.copy(), "model_sha256": self.model_sha256,
            "compliance_status": status, "is_compliant": compliant,
            "compliance_scope": "helmet_count_only", "detections": detections,
            "yolo_labels_txt": "\n".join(labels),
        }
