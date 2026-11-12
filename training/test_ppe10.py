"""Regression checks for class remapping and dataset split integrity."""

from pathlib import Path
import tempfile
import unittest

from training.ppe10 import CLASS_NAMES, TARGET_SOURCE_IDS, prepare_dataset, remap_labels


class LabelTests(unittest.TestCase):
    def test_all_selected_ids_and_coordinates(self):
        source = "\n".join(f"{class_id} 0.500000 0.400000 0.200000 0.100000" for class_id in range(17))
        output, counts = remap_labels(source)
        rows = output.splitlines()
        self.assertEqual(len(rows), 10)
        self.assertEqual([int(row.split()[0]) for row in rows], list(range(10)))
        self.assertTrue(all(row.split()[1:] == ["0.500000", "0.400000", "0.200000", "0.100000"] for row in rows))
        self.assertEqual(dict(counts), {class_id: 1 for class_id in range(10)})
        self.assertEqual(list(CLASS_NAMES.values()), ["person", "ear-mufs", "face-mask", "foot", "glasses", "gloves", "helmet", "shoes", "safety-suit", "safety-vest"])

    def test_excluded_objects_become_background(self):
        self.assertEqual(remap_labels("1 0.5 0.5 0.1 0.1\n3 0.5 0.5 0.1 0.1")[0], "")

    def test_invalid_annotations_are_rejected(self):
        for row in ["17 0.5 0.5 0.1 0.1", "-1 0.5 0.5 0.1 0.1", "0 nan 0.5 0.1 0.1", "0 0.5 0.5 0 0.1", "0 1.1 0.5 0.1 0.1", "0 0.5 0.5 0.1", "0.5 0.5 0.5 0.1 0.1"]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                remap_labels(row)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.source = Path(self.temporary.name) / "sh17"
        self.destination = Path(self.temporary.name) / "ppe10"
        for directory in ("images", "labels"):
            (self.source / directory).mkdir(parents=True)
        labels = "\n".join(f"{old} 0.5 0.5 0.2 0.2" for old in TARGET_SOURCE_IDS)
        for name, annotation in [("train", labels), ("validation", labels), ("background", "1 0.5 0.5 0.2 0.2")]:
            (self.source / "images" / f"{name}.jpg").write_bytes(b"fixture image bytes")
            (self.source / "labels" / f"{name}.txt").write_text(annotation, encoding="utf-8")
        (self.source / "train_files.txt").write_text("images/train.jpg\n", encoding="utf-8")
        (self.source / "val_files.txt").write_text("validation.jpg\nbackground.jpg\n", encoding="utf-8")

    def test_splits_backgrounds_and_source_are_preserved(self):
        summary = prepare_dataset(self.source, self.destination)
        self.assertEqual(summary["splits"]["train"]["images"], 1)
        self.assertEqual(summary["splits"]["val"]["images"], 2)
        self.assertEqual(summary["splits"]["val"]["background_images"], 1)
        self.assertEqual((self.destination / "labels/val/background.txt").read_text(), "")
        self.assertEqual((self.destination / "images/val/validation.jpg").read_bytes(), b"fixture image bytes")
        original = (self.source / "labels/validation.txt").read_text()
        self.assertIn("16 0.5 0.5 0.2 0.2", original)
        self.assertIn("9 0.5 0.5 0.2 0.2", (self.destination / "labels/val/validation.txt").read_text())
        yaml_text = (self.destination / "data.yaml").read_text()
        self.assertIn("  6: helmet\n", yaml_text)
        self.assertIn("  9: safety-vest\n", yaml_text)

    def test_overlap_is_rejected_before_output_is_written(self):
        (self.source / "val_files.txt").write_text("train.jpg\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "leakage"):
            prepare_dataset(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_source_label_is_not_treated_as_background(self):
        (self.source / "labels/validation.txt").unlink()
        with self.assertRaises(FileNotFoundError):
            prepare_dataset(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_training_class_is_rejected(self):
        (self.source / "labels/train.txt").write_text("0 0.5 0.5 0.2 0.2", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "No training examples"):
            prepare_dataset(self.source, self.destination)

    def test_stale_output_is_rejected(self):
        self.destination.mkdir()
        (self.destination / "old-label.txt").write_text("old class schema")
        with self.assertRaisesRegex(ValueError, "new or empty"):
            prepare_dataset(self.source, self.destination)
        self.assertEqual((self.destination / "old-label.txt").read_text(), "old class schema")

    def test_unsafe_and_duplicate_entries_are_rejected(self):
        for entries in ("../train.jpg", "/images/train.jpg", "C:/images/train.jpg", "train.jpg\nimages/train.jpg"):
            (self.source / "train_files.txt").write_text(entries, encoding="utf-8")
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                prepare_dataset(self.source, self.destination)


if __name__ == "__main__":
    unittest.main()
