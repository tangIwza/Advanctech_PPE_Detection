"""Exercise the generated notebook on tiny synthetic images, without a GPU.

Run with a Python environment containing ultralytics==8.4.29. This verifies
plumbing and exported class names; it does not measure detection accuracy.
All generated data, checkpoints, and archives live in a temporary directory.
"""

import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="ppe10-smoke-") as temporary:
        temporary = Path(temporary)
        config_directory = temporary / "ultralytics"
        config_directory.mkdir()
        os.environ["YOLO_CONFIG_DIR"] = str(config_directory)
        os.environ["MPLCONFIGDIR"] = str(temporary / "matplotlib")
        os.environ["MPLBACKEND"] = "Agg"
        os.environ["YOLO_AUTOINSTALL"] = "False"

        import random
        import shutil
        import subprocess
        import sys
        import warnings

        import matplotlib.pyplot as plt
        import pandas as pd
        from PIL import Image, ImageDraw
        import torch
        from ultralytics import YOLO, settings

        torch.set_num_threads(2)
        settings.update({key: False for key in ("wandb", "mlflow", "comet", "clearml", "neptune", "dvc", "hub") if key in settings})
        source = temporary / "input/sh17"
        (source / "images").mkdir(parents=True)
        (source / "labels").mkdir()
        source_ids = (0, 2, 5, 6, 8, 9, 10, 14, 15, 16)
        for split, image_count in (("train", 4), ("val", 2)):
            filenames = []
            for index in range(image_count):
                filename = f"{split}_{index}.jpg"
                image = Image.new("RGB", (96, 96), (30 + index * 40, 40, 70))
                draw = ImageDraw.Draw(image)
                labels = []
                for position, source_id in enumerate(source_ids):
                    x, y = 0.1 + (position % 5) * 0.2, 0.25 + (position // 5) * 0.5
                    labels.append(f"{source_id} {x:.4f} {y:.4f} 0.12 0.20")
                    draw.rectangle(((x - 0.06) * 96, (y - 0.10) * 96, (x + 0.06) * 96, (y + 0.10) * 96), fill=(source_id * 13 % 255, 180, 150))
                image.save(source / "images" / filename)
                (source / "labels" / Path(filename).with_suffix(".txt")).write_text("\n".join(labels), encoding="utf-8")
                filenames.append(filename)
            (source / f"{split}_files.txt").write_text("\n".join(filenames), encoding="utf-8")

        work = temporary / "work"
        run = work / "smoke_run"
        artifacts = run / "artifacts"
        artifacts.mkdir(parents=True)
        namespace = {
            "os": os, "Path": Path, "json": json, "random": random,
            "shutil": shutil, "subprocess": subprocess, "sys": sys,
            "tempfile": tempfile, "warnings": warnings, "torch": torch,
            "YOLO": YOLO, "pd": pd, "plt": plt,
            "Image": Image, "ImageDraw": ImageDraw,
            "display": lambda *args, **kwargs: None,
            "FileLink": lambda path: path,
            "WORK_DIR": work, "INPUT_DIR": temporary / "input",
            "RUN_ROOT": run, "ARTIFACT_DIR": artifacts, "SOURCE_DIR": source,
            "MODEL_WEIGHTS": str(ROOT / "yolov8n.pt"),
            "EPOCHS": 1, "PATIENCE": 1, "IMGSZ": 64, "BATCH": 2,
            "WORKERS": 0, "SEED": 42, "DEVICE": "cpu", "EXPORT_ONNX": False,
        }
        notebook = json.loads((ROOT / "ppe-training-10classes.ipynb").read_text(encoding="utf-8"))
        # Skip only package installation and Kaggle-specific GPU initialization.
        code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        for number, cell in enumerate(code_cells[2:], 2):
            print(f"SMOKE notebook code cell {number}", flush=True)
            exec(compile("".join(cell["source"]), f"notebook-cell-{number}", "exec"), namespace)
        expected = dict(enumerate(("person", "ear-mufs", "face-mask", "foot", "glasses", "gloves", "helmet", "shoes", "safety-suit", "safety-vest")))
        assert namespace["actual_names"] == expected
        assert len(namespace["evaluation"]) == 10
        assert (artifacts / "best.pt").is_file()
        assert namespace["archive"].is_file()
        print("SMOKE PASS: dataset preparation, one training epoch, checkpoint schema, per-class evaluation, prediction and artifact ZIP")
        plt.close("all")


if __name__ == "__main__":
    main()
