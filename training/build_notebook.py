"""Rebuild the self-contained Kaggle notebook from the tested preparation code."""

import json
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
cells = []


def markdown(source):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": textwrap.dedent(source).strip().splitlines(keepends=True)})


def code(source):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": textwrap.dedent(source).strip().splitlines(keepends=True)})


markdown("""
    # เทรน YOLOv8 สำหรับ PPE 10 คลาสบน Kaggle

    Notebook นี้ใช้ **SH17 ต้นฉบับ** และแปลงหมายเลขคลาสใหม่ตามรายการที่เลือก
    ไฟล์นี้รันได้ด้วยตัวเอง ไม่ต้องอัปโหลดไฟล์ Python อื่นร่วมด้วย

    1. นำเข้า Notebook นี้ใน Kaggle (File → Import Notebook หรือ Upload Notebook)
    2. เพิ่ม Input: https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection
    3. เปิด GPU ใน Settings → Accelerator และเปิด Internet สำหรับติดตั้งแพ็กเกจ/ดาวน์โหลดน้ำหนักเริ่มต้น
    4. กด Run All; ตรวจตารางจำนวนตัวอย่างและภาพ Label ก่อนปล่อยให้เทรนต่อ
    5. หลังรันจบ ดาวน์โหลด ZIP ที่มี `best.pt`, `last.pt`, mapping, กราฟ และผลประเมิน

    | ID ใหม่ | ชื่อคลาส | ID เดิมของ SH17 |
    |---:|---|---:|
    | 0 | person | 0 |
    | 1 | ear-mufs | 2 |
    | 2 | face-mask | 5 |
    | 3 | foot | 6 |
    | 4 | glasses | 8 |
    | 5 | gloves | 9 |
    | 6 | helmet | 10 |
    | 7 | shoes | 14 |
    | 8 | safety-suit | 15 |
    | 9 | safety-vest | 16 |

    ใช้ชื่อ `ear-mufs` ตาม SH17 เพื่อให้ mapping ตรงกัน และไม่ใช้ภาพที่วาดกรอบแล้วจาก `captures/` มาเทรน
    Notebook เดิมและผลประเมิน 3 คลาสในโปรเจกต์เป็นคนละการทดลองกับงานนี้
""")

code(r'''
    %pip install --quiet "ultralytics==8.4.29"
''')

markdown("""
    ## 1. ตรวจ GPU และตั้งค่าการทดลอง

    ค่าเริ่มต้นคือ YOLOv8n, ภาพขนาด 640, batch 8 และสูงสุด 100 epochs
    ตั้งค่าเหล่านี้ได้ใน cell ถัดไป ก่อนเริ่มเทรน หาก GPU memory ไม่พอให้ลด `BATCH`
    การเพิ่ม `IMGSZ` เป็น 960 เป็นการทดลองเพิ่มเติมสำหรับวัตถุเล็ก และใช้ memory/เวลามากขึ้น
""")

code(r'''
    import os
    from pathlib import Path
    import json
    import random
    import shutil
    import subprocess
    import sys
    import tempfile
    import warnings

    WORK_DIR = Path('/kaggle/working')
    INPUT_DIR = Path('/kaggle/input')
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    RUN_ROOT = Path(tempfile.mkdtemp(prefix='ppe10_', dir=WORK_DIR))
    ARTIFACT_DIR = RUN_ROOT / 'artifacts'
    ARTIFACT_DIR.mkdir()
    CONFIG_DIR = RUN_ROOT / '.ultralytics'
    CONFIG_DIR.mkdir()
    os.environ['YOLO_CONFIG_DIR'] = str(CONFIG_DIR)
    os.environ['WANDB_MODE'] = 'disabled'

    import torch
    import ultralytics
    from ultralytics import YOLO, settings
    import pandas as pd
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw
    from IPython.display import display, FileLink

    settings.update({key: False for key in ('wandb', 'mlflow', 'comet', 'clearml', 'neptune', 'dvc', 'hub') if key in settings})
    print('Python:', sys.version.split()[0])
    print('Ultralytics:', ultralytics.__version__, 'PyTorch:', torch.__version__)
    if not torch.cuda.is_available():
        raise RuntimeError('ยังไม่พบ CUDA GPU: เปิด Settings → Accelerator → GPU แล้ว restart session ก่อน Run All')
    print('GPU:', torch.cuda.get_device_name(0))
    print('GPU memory:', round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1), 'GiB')

    SOURCE_DIR = INPUT_DIR / 'sh17-dataset-for-ppe-detection'
    MODEL_WEIGHTS = 'yolov8n.pt'
    EPOCHS = 100
    PATIENCE = 25
    IMGSZ = 640
    BATCH = 8
    WORKERS = 2
    SEED = 42
    DEVICE = 0
    EXPORT_ONNX = False
    print('Run directory:', RUN_ROOT)
''')

markdown("""
    ## 2. เตรียมข้อมูล 10 คลาส

    ใช้รายชื่อ train/val ของ SH17 เดิม ไม่สุ่มแบ่งใหม่และไม่ undersample validation
    ภาพที่ไม่มีวัตถุใน 10 คลาสจะยังอยู่ใน split เดิม โดยมีไฟล์ Label ว่างเป็น background
    จะตรวจ Label ทุกแถว, ไฟล์ที่หาย, คลาสที่ไม่มีตัวอย่างเทรน และภาพซ้ำระหว่าง train/val

    รูปภาพจะใช้ hardlink หรือ symlink เมื่อทำได้ เพื่อลดการใช้พื้นที่ Kaggle
    Label ที่แปลงแล้วเขียนแยกใน `/kaggle/working`; ต้นฉบับใน Input ไม่ถูกแก้ไข
""")

code((ROOT / 'training/ppe10.py').read_text(encoding='utf-8'))

code(r'''
    def is_sh17_root(path):
        return all((path / name).exists() for name in ('images', 'labels', 'train_files.txt', 'val_files.txt'))

    if not is_sh17_root(SOURCE_DIR):
        candidates = sorted({p.parent for p in INPUT_DIR.rglob('train_files.txt') if is_sh17_root(p.parent)})
        if len(candidates) != 1:
            raise FileNotFoundError('เพิ่ม SH17 Dataset เป็น Input แล้วตั้ง SOURCE_DIR ให้ตรงกับโฟลเดอร์ที่มี images, labels, train_files.txt และ val_files.txt; พบ: ' + str(candidates))
        SOURCE_DIR = candidates[0]

    # A new empty output on every run prevents old 3-class labels from surviving.
    DATASET_DIR = Path(tempfile.mkdtemp(prefix='dataset_', dir=RUN_ROOT))
    summary = prepare_dataset(SOURCE_DIR, DATASET_DIR)
    DATA_YAML = DATASET_DIR / 'data.yaml'
    rows = []
    for class_id, name in CLASS_NAMES.items():
        rows.append({
            'id': class_id,
            'source_id': TARGET_SOURCE_IDS[class_id],
            'class': name,
            'train_instances': summary['splits']['train']['instances'][name],
            'val_instances': summary['splits']['val']['instances'][name],
            'train_images': summary['splits']['train']['images_per_class'][name],
            'val_images': summary['splits']['val']['images_per_class'][name],
        })
    distribution = pd.DataFrame(rows)
    display(distribution)
    print('Images / backgrounds:', {split: (values['images'], values['background_images']) for split, values in summary['splits'].items()})
    print('Image storage:', dict(summary['image_storage']))
    missing_val = distribution.loc[distribution.val_instances == 0, 'class'].tolist()
    if missing_val:
        warnings.warn('ไม่มีตัวอย่าง validation ของคลาสเหล่านี้ จึงยังวัดผลคลาสนั้นไม่ได้: ' + ', '.join(missing_val))
    distribution.to_csv(ARTIFACT_DIR / 'class_distribution.csv', index=False)
    for name in ('data.yaml', 'class_mapping.json', 'preparation_summary.json'):
        shutil.copy2(DATASET_DIR / name, ARTIFACT_DIR / name)

    ax = distribution.set_index('class')[['train_instances', 'val_instances']].plot.bar(figsize=(12, 5), logy=True)
    ax.set_ylabel('Instances (log scale)')
    ax.set_title('SH17 selected 10 classes — official train/val splits')
    plt.tight_layout()
    plt.savefig(ARTIFACT_DIR / 'class_distribution.png', dpi=150)
    plt.show()
''')

markdown("""
    ## 3. ตรวจภาพและ Label ที่แปลงแล้ว

    ตัวอย่างนี้มาจากชุด train ใช้ตรวจว่า Bounding Box และชื่อคลาสตรงกันก่อนเทรน
""")

code(r'''
    image_files = sorted(p for p in (DATASET_DIR / 'images/train').rglob('*') if p.suffix.lower() in IMAGE_SUFFIXES)
    samples = random.Random(SEED).sample(image_files, min(4, len(image_files)))
    fig, axes = plt.subplots(1, len(samples), figsize=(5 * len(samples), 6), squeeze=False)
    for axis, image_path in zip(axes[0], samples):
        with Image.open(image_path) as original:
            image = original.convert('RGB')
        draw = ImageDraw.Draw(image)
        width, height = image.size
        label_path = DATASET_DIR / 'labels/train' / image_path.relative_to(DATASET_DIR / 'images/train').with_suffix('.txt')
        for line in label_path.read_text().splitlines():
            class_id, xc, yc, bw, bh = map(float, line.split())
            box = ((xc - bw / 2) * width, (yc - bh / 2) * height, (xc + bw / 2) * width, (yc + bh / 2) * height)
            draw.rectangle(box, outline='lime', width=max(2, width // 400))
            draw.text((box[0], max(0, box[1] - 14)), CLASS_NAMES[int(class_id)], fill='red')
        axis.imshow(image)
        axis.set_title(image_path.name, fontsize=8)
        axis.axis('off')
    plt.tight_layout()
    plt.show()
''')

markdown("""
    ## 4. เทรนโมเดล

    บันทึก checkpoint ทุก 10 epochs และใช้ validation สำหรับเลือก `best.pt`
    หาก session หยุดก่อนจบ สามารถใช้ `last.pt` ที่บันทึกไว้เพื่อ resume ใน session ที่มีข้อมูลพาธเดิม
    เวลาที่ใช้ขึ้นกับ GPU, จำนวนภาพ, ขนาดภาพ และการตั้งค่า จึงยังไม่ระบุเวลาจบล่วงหน้า
""")

code(r'''
    training_config = {
        'model': MODEL_WEIGHTS, 'data': str(DATA_YAML), 'epochs': EPOCHS,
        'patience': PATIENCE, 'imgsz': IMGSZ, 'batch': BATCH, 'workers': WORKERS,
        'device': DEVICE, 'seed': SEED, 'deterministic': True, 'cache': False,
    }
    (ARTIFACT_DIR / 'training_config.json').write_text(json.dumps(training_config, indent=2), encoding='utf-8')
    model = YOLO(MODEL_WEIGHTS)
    train_results = model.train(
        data=str(DATA_YAML), epochs=EPOCHS, patience=PATIENCE,
        imgsz=IMGSZ, batch=BATCH, workers=WORKERS, device=DEVICE,
        seed=SEED, deterministic=True, cache=False, amp=True,
        pretrained=True, plots=True, save=True, save_period=10,
        project=str(RUN_ROOT / 'runs'), name='train',
    )
    RUN_DIR = Path(model.trainer.save_dir)
    BEST_WEIGHTS = RUN_DIR / 'weights/best.pt'
    LAST_WEIGHTS = RUN_DIR / 'weights/last.pt'
    if not BEST_WEIGHTS.is_file():
        raise FileNotFoundError('Training did not create best.pt: ' + str(RUN_DIR))
    best = YOLO(str(BEST_WEIGHTS))
    actual_names = {int(key): value for key, value in best.names.items()}
    if actual_names != CLASS_NAMES:
        raise RuntimeError('Checkpoint class schema mismatch: ' + str(actual_names))
    print('Best weights:', BEST_WEIGHTS)
    print('Checkpoint classes:', actual_names)
''')

markdown("""
    ## 5. ประเมินผลแยกทั้ง 10 คลาส

    แสดง Precision, Recall, AP@50 และ AP@50–95 ต่อคลาส
    นี่คือผลบน validation ที่ใช้เลือก checkpoint ไม่ใช่ผลบนชุดทดสอบอิสระ
    คลาสที่ไม่มี ground truth ใน validation จะแสดงค่าว่าง ไม่แทนด้วยคะแนนของคลาสอื่น
""")

code(r'''
    EVAL_DIR = RUN_ROOT / 'evaluation/val'
    metrics = best.val(
        data=str(DATA_YAML), split='val', imgsz=IMGSZ, batch=BATCH,
        device=DEVICE, workers=WORKERS, plots=True,
        project=str(EVAL_DIR.parent), name=EVAL_DIR.name, exist_ok=True,
    )
    metric_rows = {class_id: {'id': class_id, 'class': name, 'precision': None, 'recall': None, 'AP50': None, 'AP50_95': None} for class_id, name in CLASS_NAMES.items()}
    for index, class_id in enumerate(metrics.box.ap_class_index):
        precision, recall, ap50, ap = metrics.box.class_result(index)
        metric_rows[int(class_id)].update(precision=float(precision), recall=float(recall), AP50=float(ap50), AP50_95=float(ap))
    evaluation = pd.DataFrame(metric_rows.values())
    display(evaluation)
    evaluation.to_csv(ARTIFACT_DIR / 'per_class_metrics.csv', index=False)
    print('Overall mAP50:', round(float(metrics.box.map50), 4))
    print('Overall mAP50-95:', round(float(metrics.box.map), 4))
    (ARTIFACT_DIR / 'overall_metrics.json').write_text(json.dumps({key: float(value) for key, value in metrics.results_dict.items()}, indent=2), encoding='utf-8')
    for chart in (RUN_DIR / 'results.png', EVAL_DIR / 'confusion_matrix_normalized.png'):
        if chart.exists():
            display(Image.open(chart))
''')

markdown("""
    ## 6. ทดลองทำนายภาพและส่งออก ONNX (เลือกได้)

    ค่าเริ่มต้นแสดงภาพตัวอย่างจาก validation ซึ่งเป็นเพียงการตรวจด้วยสายตา
    หากมีภาพใหม่ ให้ตั้ง `PREDICT_SOURCE` เป็นพาธภาพใน Input ที่เพิ่มเข้ามา
    ตั้ง `EXPORT_ONNX = True` ใน cell ตั้งค่า หากต้องการไฟล์ ONNX เพิ่มเติม
""")

code(r'''
    PREDICT_SOURCE = None
    example = PREDICT_SOURCE or str(next(p for p in (DATASET_DIR / 'images/val').rglob('*') if p.suffix.lower() in IMAGE_SUFFIXES))
    predictions = best.predict(source=example, imgsz=IMGSZ, conf=0.25, device=DEVICE, save=True, project=str(RUN_ROOT / 'predictions'), name='examples', exist_ok=True)
    for result in predictions:
        display(Image.fromarray(result.plot()[..., ::-1]))
    onnx_path = None
    if EXPORT_ONNX:
        onnx_path = Path(best.export(format='onnx', imgsz=IMGSZ, dynamic=False, simplify=False))
        shutil.copy2(onnx_path, ARTIFACT_DIR / 'best.onnx')
''')

markdown("""
    ## 7. ดาวน์โหลดน้ำหนักและผลการเทรน

    ZIP นี้รวม `best.pt`, `last.pt`, class mapping, config, สถิติ, metrics และกราฟ
    ไม่รวมภาพ SH17 ต้นฉบับ จึงไม่ต้องดาวน์โหลด Dataset ซ้ำ

    แอปเดิมในโปรเจกต์รองรับ 3 คลาสแบบ hardcode อยู่: ก่อนนำโมเดล 10 คลาสนี้ไปใช้
    ต้องปรับ `server.py` และหน้าเว็บให้ตรงกับ mapping ใหม่ มิฉะนั้นชื่อและหมายเลขคลาสอาจผิด
""")

code(r'''
    shutil.copy2(BEST_WEIGHTS, ARTIFACT_DIR / 'best.pt')
    if LAST_WEIGHTS.exists():
        shutil.copy2(LAST_WEIGHTS, ARTIFACT_DIR / 'last.pt')
    for source_dir, folder in ((RUN_DIR, 'training'), (EVAL_DIR, 'evaluation')):
        target_dir = ARTIFACT_DIR / folder
        target_dir.mkdir(exist_ok=True)
        for artifact in source_dir.iterdir():
            if artifact.is_file() and artifact.suffix.lower() in ('.png', '.jpg', '.csv', '.json', '.yaml'):
                shutil.copy2(artifact, target_dir / artifact.name)
    packages = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (ARTIFACT_DIR / 'requirements-used.txt').write_text(packages, encoding='utf-8')
    (ARTIFACT_DIR / 'README.txt').write_text(
        'YOLOv8 PPE 10-class training artifacts.\n'
        + '\n'.join(f'{key}: {value}' for key, value in CLASS_NAMES.items())
        + '\n\nMetrics are validation results, not an independent test result.\n'
        + 'The existing three-class application needs its class mapping and UI updated before loading this checkpoint.\n',
        encoding='utf-8',
    )
    archive = Path(shutil.make_archive(str(WORK_DIR / (RUN_ROOT.name + '_training_artifacts')), 'zip', root_dir=ARTIFACT_DIR))
    print('Download:', archive)
    display(FileLink(str(archive)))
''')

markdown("""
    อ้างอิง:
    - SH17 class schema: https://github.com/ahmadmughees/SH17dataset/blob/master/sh17.yaml
    - YOLO dataset format: https://docs.ultralytics.com/datasets/detect/
    - YOLOv8 training: https://docs.ultralytics.com/models/yolov8/
""")

notebook = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "kaggle": {"language": "python", "sourceType": "notebook", "isInternetEnabled": True, "isGpuEnabled": True},
    },
    "cells": cells,
}
for index, cell in enumerate(notebook["cells"]):
    cell["id"] = f"ppe10-{index:02d}"
destination = ROOT / 'ppe-training-10classes.ipynb'
destination.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(destination)
