from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ppe_engine import YOLOPPEEngine
from training.ppe10 import CLASS_NAMES


class FakeModel:
    def __init__(self, names, task="detect"):
        self.names = names
        self.task = task
        self.calls = []
        self.class_ids = list(names)

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        n = len(self.class_ids)
        boxes = SimpleNamespace(
            xyxy=np.array([[10, 20, 50, 80]] * n),
            conf=np.array([0.81] * n), cls=np.array(self.class_ids),
        )
        return [SimpleNamespace(boxes=boxes)]


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.weights = Path(self.temporary.name) / "best.pt"
        self.weights.write_bytes(b"fixture checkpoint")
        self.fake = FakeModel(CLASS_NAMES)
        self.patcher = patch("ppe_engine.YOLO", return_value=self.fake)
        self.loader = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.engine = YOLOPPEEngine(self.weights)

    def test_native_ids_survive_detections_counts_and_labels(self):
        _, info = self.engine.predict_frame(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertEqual([d["class_id"] for d in info["detections"]], list(range(10)))
        self.assertEqual([d["class_name"] for d in info["detections"]], list(CLASS_NAMES.values()))
        self.assertEqual(info["counts"], dict.fromkeys(CLASS_NAMES.values(), 1))
        self.assertEqual([int(row.split()[0]) for row in info["yolo_labels_txt"].splitlines()], list(range(10)))
        self.assertEqual(info["detections"][1]["class_name"], "ear-mufs")
        self.assertEqual(info["detections"][2]["class_name"], "face-mask")
        self.assertEqual(info["detections"][6]["class_name"], "helmet")
        self.assertEqual(info["detections"][9]["class_name"], "safety-vest")

    def test_no_heuristic_ppe_is_invented(self):
        self.fake.class_ids = [0]
        _, info = self.engine.predict_frame(np.full((100, 100, 3), (0, 255, 255), dtype=np.uint8))
        self.assertEqual(info["total_boxes"], 1)
        self.assertEqual(info["counts"]["helmet"], 0)
        self.assertEqual(info["counts"]["safety-vest"], 0)
        self.assertEqual(info["compliance_status"], "MISSING_PPE")

    def test_confidence_is_delegated_to_the_model(self):
        self.engine.conf_threshold = 0.8
        self.engine.predict_frame(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertEqual(self.fake.calls[-1]["conf"], 0.8)

    def test_reloading_legacy_names_preserves_their_own_ids(self):
        legacy = FakeModel({0: "person", 1: "helmet", 2: "safety-vest"})
        self.loader.return_value = legacy
        self.engine.reload_model(self.weights)
        _, info = self.engine.predict_frame(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertEqual(info["classes"], legacy.names)
        self.assertEqual(len(info["counts"]), 3)
        self.assertEqual(info["detections"][1]["class_name"], "helmet")

    def test_invalid_reload_keeps_the_working_model(self):
        self.loader.return_value = FakeModel(CLASS_NAMES, task="classify")
        with self.assertRaises(ValueError):
            self.engine.reload_model(self.weights)
        self.assertIs(self.engine.model, self.fake)
        self.assertEqual(self.engine.PPE_CLASS_NAMES, CLASS_NAMES)

    def test_prediction_schema_is_a_snapshot(self):
        before = self.engine.empty_prediction()
        self.loader.return_value = FakeModel({0: "person", 1: "helmet"})
        self.engine.reload_model(self.weights)
        self.assertEqual(before["classes"], CLASS_NAMES)
        self.assertEqual(len(before["counts"]), 10)

    def test_unsupported_helmet_check_is_explicit(self):
        self.loader.return_value = FakeModel({0: "person", 1: "car"})
        self.engine.reload_model(self.weights)
        _, info = self.engine.predict_frame(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertIsNone(info["is_compliant"])
        self.assertEqual(info["compliance_status"], "NOT_AVAILABLE")


if __name__ == "__main__":
    unittest.main()
