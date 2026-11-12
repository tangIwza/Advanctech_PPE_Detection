from dataclasses import replace

import cv2
from fastapi.testclient import TestClient
import numpy as np
import pytest

from backend.config import Settings
from backend.main import create_app
from backend.rules import Detection, classify_name

NAMES = dict(enumerate(("person", "ear-mufs", "face-mask", "foot", "glasses", "gloves", "helmet", "shoes", "safety-suit", "safety-vest")))


def example_detections():
    return [
        Detection(0, "person", .9, (.1,.1,.4,.9), 1),
        Detection(0, "person", .9, (.6,.1,.9,.9), 2),
        Detection(6, "helmet", .9, (.2,.12,.3,.2)),
        Detection(6, "helmet", .9, (.7,.12,.8,.2)),
        Detection(9, "safety-vest", .9, (.17,.3,.35,.55)),
    ]


class FakeDetector:
    def __init__(self, settings):
        self.names, self.person_ids, self.ppe_ids = NAMES.copy(), {0}, {1,2,4,5,6,7,8,9}

    def info(self):
        return {"model_name": "best.pt", "sha256": "test-checkpoint", "device": "cpu", "class_count": 10,
                "classes": [{"id": key, "name": value, "kind": classify_name(value), "color": "#3b82f6"} for key,value in self.names.items()],
                "person_class_ids": [0], "ppe_class_ids": sorted(self.ppe_ids), "training": None}

    def predict(self, frame, confidence):
        return [item for item in example_detections() if item.confidence >= confidence], 1.0


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", frontend_dir=tmp_path / "frontend", max_upload_bytes=100_000)


@pytest.fixture
def client(settings):
    app = create_app(settings, FakeDetector)
    with TestClient(app) as value:
        yield value


@pytest.fixture
def video_bytes(tmp_path):
    path = tmp_path / "fixture.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    assert writer.isOpened()
    for _ in range(100):
        writer.write(np.zeros((120,160,3), dtype=np.uint8))
    writer.release()
    return path.read_bytes()


def zone_payload(source_id="test-video", kind="ppe"):
    return {"source_id": source_id, "name": "Test zone", "kind": kind,
            "rect": {"x1": 0, "y1": 0, "x2": 1, "y2": 1},
            "required_class_ids": [6,9] if kind == "ppe" else [], "anchor": "feet", "enabled": True}
