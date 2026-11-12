"""Prepare the original SH17 dataset for ten-class YOLO detection.

This module uses only Python's standard library. Its source is also embedded
in ppe-training-10classes.ipynb so that the Kaggle notebook is self-contained.
"""

from collections import Counter
import json
import math
from pathlib import Path, PurePosixPath
import shutil


SOURCE_NAMES = (
    "person", "ear", "ear-mufs", "face", "face-guard", "face-mask",
    "foot", "tool", "glasses", "gloves", "helmet", "hands", "head",
    "medical-suit", "shoes", "safety-suit", "safety-vest",
)
TARGET_SOURCE_IDS = (0, 2, 5, 6, 8, 9, 10, 14, 15, 16)
CLASS_NAMES = {new: SOURCE_NAMES[old] for new, old in enumerate(TARGET_SOURCE_IDS)}
CLASS_MAP = {old: new for new, old in enumerate(TARGET_SOURCE_IDS)}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def remap_labels(text, context="label"):
    """Validate every original annotation and retain selected classes.

    Empty output is a valid background image. Bounding-box values are kept
    verbatim; this function only changes class IDs and removes other classes.
    """
    output = []
    counts = Counter()
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        location = f"{context}:{line_number}"
        if len(parts) != 5:
            raise ValueError(f"{location}: expected class x_center y_center width height")
        try:
            source_id = int(parts[0])
            coordinates = [float(value) for value in parts[1:]]
        except ValueError as exc:
            raise ValueError(f"{location}: non-numeric annotation") from exc
        if not 0 <= source_id < len(SOURCE_NAMES):
            raise ValueError(f"{location}: original SH17 class ID must be 0..16")
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in coordinates):
            raise ValueError(f"{location}: coordinates must be finite and normalized to 0..1")
        if coordinates[2] <= 0 or coordinates[3] <= 0:
            raise ValueError(f"{location}: bounding-box width and height must be positive")
        if source_id in CLASS_MAP:
            new_id = CLASS_MAP[source_id]
            output.append(f"{new_id} {' '.join(parts[1:])}")
            counts[new_id] += 1
    return "\n".join(output) + ("\n" if output else ""), counts


def read_split(source, split):
    """Resolve official split entries relative to SH17's images directory."""
    source = Path(source).resolve()
    split_file = source / f"{split}_files.txt"
    if not split_file.is_file():
        raise FileNotFoundError(f"Missing SH17 split file: {split_file}")
    records = []
    seen = set()
    for line_number, raw_entry in enumerate(split_file.read_text(encoding="utf-8-sig").splitlines(), 1):
        entry = raw_entry.strip().replace("\\", "/")
        if not entry:
            continue
        relative = PurePosixPath(entry)
        if relative.is_absolute() or ".." in relative.parts or ":" in entry:
            raise ValueError(f"{split_file}:{line_number}: expected a relative image path")
        if relative.parts and relative.parts[0] == "images":
            relative = relative.relative_to("images")
        if relative.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f"{split_file}:{line_number}: unsupported image path {entry!r}")
        label_key = relative.with_suffix(".txt").as_posix()
        if label_key in seen:
            raise ValueError(f"{split_file}:{line_number}: duplicate image/label stem {entry!r}")
        seen.add(label_key)
        image = source / "images" / Path(relative.as_posix())
        label = source / "labels" / Path(label_key)
        if not image.is_file():
            raise FileNotFoundError(f"Missing source image: {image}")
        if not label.is_file():
            raise FileNotFoundError(f"Missing source annotation: {label}")
        remapped, counts = remap_labels(label.read_text(encoding="utf-8-sig"), str(label))
        records.append((relative, image, remapped, counts))
    if not records:
        raise ValueError(f"No images listed in {split_file}")
    return records


def dataset_yaml(dataset):
    """Use an absolute dataset root and contiguous class IDs."""
    lines = [
        f"path: {json.dumps(Path(dataset).resolve().as_posix(), ensure_ascii=False)}",
        "train: images/train",
        "val: images/val",
        "names:",
    ]
    lines.extend(f"  {class_id}: {name}" for class_id, name in CLASS_NAMES.items())
    return "\n".join(lines) + "\n"


def link_or_copy(source, destination):
    """Avoid copying SH17's large images when links are available."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.hardlink_to(source)
        return "hardlink"
    except OSError:
        pass
    try:
        destination.symlink_to(source)
        return "symlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def prepare_dataset(source, destination):
    """Preserve official train/val splits and all images, including backgrounds.

    Validate inputs before writing. An existing non-empty output is rejected
    so labels from previous class configurations cannot remain in the dataset.
    """
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be separate, non-nested directories")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError(f"Output must be a new or empty directory: {destination}")
    splits = {split: read_split(source, split) for split in ("train", "val")}
    train_keys = {record[0].with_suffix(".txt").as_posix() for record in splits["train"]}
    val_keys = {record[0].with_suffix(".txt").as_posix() for record in splits["val"]}
    overlap = train_keys & val_keys
    if overlap:
        raise ValueError(f"Train/val leakage: {len(overlap)} overlapping image stems; examples: {sorted(overlap)[:5]}")
    train_counts = sum((record[3] for record in splits["train"]), Counter())
    missing_train = [name for class_id, name in CLASS_NAMES.items() if train_counts[class_id] == 0]
    if missing_train:
        raise ValueError(f"No training examples for requested classes: {missing_train}")

    summary = {
        "source": str(source),
        "dataset": str(destination),
        "class_mapping": [
            {"id": new, "source_id": old, "name": CLASS_NAMES[new]}
            for new, old in enumerate(TARGET_SOURCE_IDS)
        ],
        "splits": {},
        "image_storage": Counter(),
    }
    destination.mkdir(parents=True, exist_ok=True)
    for split, records in splits.items():
        instance_counts = Counter()
        image_counts = Counter()
        backgrounds = 0
        for relative, image, remapped, counts in records:
            image_destination = destination / "images" / split / Path(relative.as_posix())
            storage = link_or_copy(image, image_destination)
            summary["image_storage"][storage] += 1
            label_destination = destination / "labels" / split / Path(relative.with_suffix(".txt").as_posix())
            label_destination.parent.mkdir(parents=True, exist_ok=True)
            label_destination.write_text(remapped, encoding="utf-8")
            instance_counts.update(counts)
            image_counts.update(counts.keys())
            backgrounds += not bool(remapped)
        summary["splits"][split] = {
            "images": len(records),
            "background_images": backgrounds,
            "instances": {name: instance_counts[class_id] for class_id, name in CLASS_NAMES.items()},
            "images_per_class": {name: image_counts[class_id] for class_id, name in CLASS_NAMES.items()},
        }
    (destination / "data.yaml").write_text(dataset_yaml(destination), encoding="utf-8")
    (destination / "class_mapping.json").write_text(json.dumps(summary["class_mapping"], indent=2), encoding="utf-8")
    (destination / "preparation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
