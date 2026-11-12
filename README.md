# AiCS · Smart Safety & PPE Monitoring

FastAPI + Ultralytics YOLO backend และ React + Tailwind frontend สำหรับตรวจ PPE
รายบุคคลและโซนห้ามเข้า ใช้โมเดลจริง `models/best.pt` จาก Kaggle และธีมของ
`C:/Users/DELL/Desktop/SCG_New_JCMS` ที่ตรวจไฟล์ก่อนสร้าง frontend
รายละเอียดสี/คอมโพเนนต์อยู่ใน [docs/UI_THEME.md](docs/UI_THEME.md)

## ใช้จาก GitHub

```powershell
git clone https://github.com/tangIwza/Advanctech_PPE_Detection.git
cd Advanctech_PPE_Detection
```

repository เผยแพร่ซอร์ส เอกสาร และ training notebook โดยไม่รวม weights,
วิดีโออัปโหลด ฐานข้อมูล runtime หรือ credentials ตาม `.gitignore`
ก่อนเริ่ม backend ให้นำ custom 10-class `best.pt` มาไว้ที่ `models/best.pt`
หรือกำหนด `PPE_MODEL_PATH` ไปยังไฟล์โมเดลของคุณ
ใช้ notebook ที่มีให้เพื่อเทรน SH17 หรือดาวน์โหลด output ของ Kaggle run ของคุณ
แล้วนำไฟล์ `runs/train/weights/best.pt` มาใช้
วิดีโอตัวอย่างและโซนตัวอย่างที่กล่าวถึงด้านล่างมีเฉพาะบนเครื่องต้นฉบับ
เมื่อ clone ใหม่ให้อัปโหลดวิดีโอหรือเริ่มกล้องแล้วสร้างโซนผ่าน UI

## เริ่มใช้บนเครื่องนี้

โปรเจกต์มี frontend ที่ build แล้ว และได้ทดสอบด้วย Python 3.11 / CPU และ NVIDIA CUDA GPU
ดับเบิลคลิก **`run_backend.bat`** แล้วเปิด <http://127.0.0.1:8000>
หยุดด้วย Ctrl+C ในหน้าต่างเซิร์ฟเวอร์

หากต้องติดตั้งใหม่ ใช้ **Python 3.11 64-bit, Node.js 22.12+** และรัน:

```powershell
cd C:\Users\DELL\Desktop\Advancetech
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
cd frontend
npx --yes npm@11.6.2 ci --no-fund
npm run build
cd ..
.\run_backend.bat
```

ใช้ npm 11 ตาม lockfile; npm 10 ที่มากับเครื่องนี้เคยเกิด Arborist error ระหว่าง
resolve dependencies จึงระบุรุ่นในคำสั่งติดตั้งไว้โดยตรง
ไม่ต้องโหลด weights เพิ่ม โมเดลที่ใช้งานอยู่คือ `models/best.pt`

## เปิดใช้ NVIDIA GPU

รันจาก project root:

~~~powershell
.\setup_gpu.bat
.\run_backend.bat
~~~

ตัวติดตั้งสร้าง environment แยกที่ .venv และติดตั้ง PyTorch 2.2.2 + CUDA 12.1
กับ torchvision รุ่นที่ตรงกันจากแหล่งทางการ ต้องมี NVIDIA driver และพื้นที่ว่าง
สำหรับชุด CUDA จากนั้น run_backend.bat จะใช้ Python ใน .venv อัตโนมัติ
รายละเอียดอยู่ใน [docs/GPU_SETUP.md](docs/GPU_SETUP.md)

## Backend และ Frontend แยกกันระหว่างพัฒนา

Terminal 1 จาก project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 65536
```

Terminal 2:

```powershell
cd C:\Users\DELL\Desktop\Advancetech\frontend
npm run dev
```

เปิด <http://127.0.0.1:5173> Vite proxy `/api`, `/health`, `/ws` ไป backend
หรือใช้ `run_frontend.bat` สำหรับ terminal ที่สอง
หากยังไม่มี `.venv` แต่ Python 3.11 มี dependencies แล้ว ใช้ `py -3.11` แทน
`.\.venv\Scripts\python.exe` ได้

สำหรับใช้งาน build: `npm run build` แล้วใช้ backend เพียงตัวเดียวที่พอร์ต 8000
FastAPI จะเสิร์ฟ `frontend/dist` พร้อม API และ WebSocket
`run_app.bat` เดิมยังเป็น workbench รุ่นก่อน; แอปใหม่นี้ใช้ `run_backend.bat`

## วิธีใช้งาน

1. หน้า **Live Monitoring** เลือกวิดีโอตัวอย่าง หรือกด Upload & play video
   รองรับ `.mp4`, `.avi`, `.mov` ที่ OpenCV/FFmpeg ถอดรหัสได้ สูงสุด 500 MB
2. โหมด **Live camera** ใช้ดัชนีกล้อง `0` หรือ URL `rtsp://`, `rtsps://`,
   `http://`, `https://` กด Start monitoring
   Webcam คือกล้องบนเครื่องที่รัน backend ไม่ใช่กล้องของ browser ฝั่งผู้ชม
3. เลือกโหมดวาดแล้วกด **Draw zone**:
   - **Rectangle:** คลิกและลากกรอบสี่เหลี่ยมตามปกติ
   - **Polygon / Pen:** คลิกวางจุดทีละมุม ปิดรูปด้วยการคลิกจุดแรก
     หรือกด **Finish polygon** / Enter ใช้ Undo / Backspace ย้อนจุด และ Esc ยกเลิก
     รองรับ 3–64 จุด รวมรูปเว้า โดยเส้นต้องไม่ตัดกัน
4. หลังวาดเสร็จ ตั้งชื่อและเลือกกฎ (ใช้ได้กับทั้งสองรูปทรง):
   - **PPE compliance:** เลือก PPE ที่บังคับในโซน
   - **Restricted / no entry:** แจ้งเมื่อมีคนในโซน
5. เลือกจุดอ้างอิงคน **Bottom-center** (ตำแหน่งเท้า) หรือ **Centroid**
   แล้ว Save zone กฎทำงานทันที ไม่ต้องเริ่มวิดีโอใหม่
6. เปิด/ปิด แก้ไข วาดโซนใหม่ หรือลบโซนจากการ์ด Detection zones
   หรือหน้า Detection Zones โซนแต่ละชุดผูกกับ source แยกกัน
   ใช้ Redraw zone แล้วเลือกอีกโหมดเพื่อเปลี่ยนรูปทรงของโซนเดิม
7. ดูข้อความแจ้งเตือนสีแดง เปิด Snapshot, Acknowledge หรือ Export CSV
   ในหน้า Alert History เปิดเสียงได้ด้วยปุ่มลำโพงหลังมีการกดจากผู้ใช้

มีโซนตัวอย่างชื่อ `Sample PPE check` และ `Sample no-entry area` ที่สร้างระหว่าง
ทดสอบกับวิดีโอตัวอย่างเท่านั้น แก้ไขหรือลบผ่าน UI ได้
โซนของวิดีโอตัวอย่างไม่ถูกนำไปใช้กับกล้องหรือวิดีโอที่อัปโหลดใหม่

## โมเดลและการจับคู่ PPE

โหลด `YOLO(settings.model_path)` หนึ่งครั้งใน lifespan และ warm up ก่อน readiness
อ่าน `model.names` จริงผ่าน `GET /api/classes`; UI ไม่ hard-code หมายเลข PPE
ชื่อ person/human/worker ถูกจัดเป็นคน ชื่ออุปกรณ์ที่รู้จักถูกจัดเป็น wearable PPE
คลาสที่ไม่รู้จักแสดงใน UI เป็น other โดยไม่เดาให้เป็นอุปกรณ์บังคับ

โมเดลปัจจุบันมี 10 คลาส:

| ID | ชื่อ | บทบาท |
| --- | --- | --- |
| 0 | person | คน |
| 1 | ear-mufs | PPE |
| 2 | face-mask | PPE |
| 3 | foot | อวัยวะ; ตรวจแสดงผลได้ แต่ไม่ใช้เป็น PPE ที่ต้องสวม |
| 4 | glasses | PPE |
| 5 | gloves | PPE |
| 6 | helmet | PPE |
| 7 | shoes | PPE |
| 8 | safety-suit | PPE |
| 9 | safety-vest | PPE |

- คนอยู่ในโซนเมื่อจุดอ้างอิงอยู่ภายในรูปทรงจริงที่มีพิกัด normalized `[0, 1]`
- จับคู่ PPE ด้วย `intersection(person, PPE) / area(PPE)` ค่าเริ่มต้น 0.5
  เลือกเจ้าของที่เหมาะที่สุดเพียงคนเดียวต่อกล่อง PPE
- ตรวจ required PPE แยกต่อคน; PPE ของคนอื่นไม่เติมรายการที่ขาดให้คนข้าง ๆ
- ขาดอุปกรณ์อย่างน้อยหนึ่งชนิด หรือเข้าพื้นที่ห้ามเข้า จะสร้าง event ทันที
  และทำกรอบคน/โซนเป็นสีแดง
- IoU tracker ให้หมายเลขชั่วคราวเพื่อ deduplicate ตามโซน/คน/ประเภท/ชุด PPE ที่ขาด
  หมายเลขนี้ไม่ใช่การระบุตัวบุคคล และรีเซ็ตเมื่อเปลี่ยนแหล่งภาพหรือวนวิดีโอ
- ถ้าไม่พบ violation เดิม 1.5 วินาที event จะปิด; Acknowledge คือรับทราบ
  ไม่ได้ปิดกฎ การหยุด/เปลี่ยน source และแก้กฎมีเหตุผลการปิด event แยกไว้
  หลัง backend restart event ค้างจะปิดด้วย `monitoring_restarted`
- ปรับ confidence, association threshold และระยะปิด event ที่หน้า Settings

SHA-256 weights: `b1a4c6457086c77f90c8dab5ebf65086f507b380357844bb72486e076f57c984`
อ่าน training report เฉพาะเมื่อ hash ตรงกับ `models/best.metadata.json`
checkpoint นี้เทรนได้ **41/100 epochs**, validation **mAP@50 44.9%**,
**mAP@50–95 27.4%** ผลตรวจจึงยังอาจพลาดหรือแจ้งเกิน โดยเฉพาะคนซ้อนกัน/
PPE ขนาดเล็ก ต้องประเมินกับภาพหน้างานก่อนใช้ตัดสินสถานการณ์จริง
นี่เป็นข้อจำกัดของ checkpoint และ spatial association ไม่ใช่ผลทดสอบความแม่นยำภาคสนาม

## สถาปัตยกรรมและข้อมูล

```text
OpenCV capture -> YOLO -> temporary person tracker -> per-zone rule engine
                         |                         |
                         +-> latest JPEG + metadata -> WebSocket -> React canvas
                                                   +-> SQLite + alert snapshots
```

- หนึ่ง decoder/inference worker ต่อ backend process ใช้ร่วมกันทุก viewer
  รองรับแหล่งภาพที่ active พร้อมกัน **หนึ่งแหล่ง** และไม่ทำ inference ซ้ำตามผู้ชม
  ต้องรัน `--workers 1` เพราะ source/worker state อยู่ใน process
- WebSocket ส่ง JSON `type=frame` แล้ว binary JPEG ที่ตรงกันเมื่อ `has_frame=true`
  มี sequence, state, normalized detections/zones, violations, alerts และ metrics
  ถ้าผู้ชมช้า จะรับเฟรมล่าสุดแทนการสะสมคิว ภาพแสดงผลกับ overlay จับคู่ sequence
- หน้าเว็บ reconnect อัตโนมัติ และทิ้งภาพ decode ค้างจาก connection เดิม
- ภาพถูกย่อตามอัตราส่วน สูงสุด 1280×960; inference size เริ่มต้น 640
  วิดีโอข้ามบางเฟรมเมื่อประมวลผลไม่ทันเพื่อรักษาจังหวะการเล่นโดยประมาณ
  จำนวน FPS ขึ้นกับ CPU/GPU/กล้อง ไม่รับประกันทุกเฟรมของวิดีโอจะถูกตรวจ
- normalized canvas รองรับ Rectangle แบบลากย้อนทิศ และ Polygon แบบคลิกวางจุด
  ใช้หลายรูปทรงร่วมกันได้ รองรับ resize, fullscreen และหน้าจอมือถือ
- SQLite WAL: `backend/data/safety.sqlite3`; uploads และ snapshots อยู่ใต้ data เดียวกัน
  ข้อมูลคงอยู่เมื่อ restart; source จะไม่เปิดกล้องเองหลัง restart
- เก็บ alerts สูงสุด 5,000 รายการ / 30 วัน pruning ตอน startup และเมื่อมี event ใหม่
  ลบ snapshot ที่ไม่มี alert อ้างถึงแล้ว; uploads คงอยู่จนผู้ดูแลจัดการพื้นที่
- เปลี่ยนโมเดลที่มีชื่อ/ลำดับคลาสต่างจาก schema ที่เก็บไว้จะปฏิเสธ startup
  ให้สำรองและ migrate zone IDs หรือเลือก `PPE_DATA_DIR` ใหม่ก่อนเปลี่ยน schema

## API

Swagger UI: <http://127.0.0.1:8000/docs>

| Method | Endpoint | ใช้สำหรับ |
| --- | --- | --- |
| GET | `/health` | Readiness หลัง model warm-up |
| GET | `/api/classes` | โมเดล/hash/คลาสแบบ dynamic |
| GET | `/api/status` | สถานะและ metadata ล่าสุด |
| GET/PUT | `/api/settings` | ค่ากฎและ inference confidence |
| GET/POST | `/api/videos` | รายการ / multipart upload field `file` |
| POST | `/api/stream/start` | `{kind:"video", video_id:"...", loop:false}` หรือ `{kind:"camera", address:"0"}` |
| POST | `/api/stream/pause`, `/resume`, `/stop` | ควบคุม source (prefix `/api/stream` ทุก endpoint) |
| GET | `/api/zones?source_id=...` | โซนของ source |
| POST | `/api/zones` | สร้าง rectangle/rules |
| PATCH/DELETE | `/api/zones/{id}` | แก้/เปิดปิด/ลบ; PATCH รองรับ `expected_version` ป้องกันแก้ทับ |
| GET | `/api/alerts` | `limit`, `offset`, `kind`, `acknowledged` |
| POST | `/api/alerts/{id}/acknowledge` | รับทราบเหตุการณ์ |
| GET | `/api/alerts/{id}/snapshot` | ภาพหลักฐานที่ต้องผ่าน auth |
| GET | `/api/alerts/export` | CSV พร้อมป้องกัน formula injection |
| WS | `/ws/stream` | JSON + binary JPEG, heartbeat |

ตัวอย่าง zone body:

```json
{
  "source_id": "sample-video", "name": "Helmet and vest",
  "kind": "ppe", "rect": {"x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 1.0},
  "required_class_ids": [6, 9], "anchor": "feet", "enabled": true
}
```

## ตั้งค่าสำหรับ deployment

ตัวอย่างตัวแปรอยู่ใน `backend/.env.example` เป็นเอกสารค่าเท่านั้น
โปรแกรมอ่านจาก environment; ไม่โหลดไฟล์ `.env` ให้อัตโนมัติ
สำหรับ local production mode ตั้งใน PowerShell ก่อนเริ่ม backend:

```powershell
$env:PPE_ENV = "production"
$env:PPE_API_TOKEN = (py -3.11 -c "import secrets; print(secrets.token_urlsafe(32))")
$env:PPE_ALLOWED_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000"
.\run_backend.bat
```

ใช้ token จาก environment เดียวกันกรอกที่ Connection settings บนเว็บ
เก็บ token ใน secret manager ของ deployment และส่งให้ผู้ดูแลผ่านช่องทางขององค์กร
backend บังคับ token อย่างน้อย 32 ตัวใน production รองรับ letters/digits/`_`/`-`
HTTP ใช้ `Authorization: Bearer ...`; WS ใช้ subprotocols `safety-stream` และ
`bearer.<token>` เพื่อไม่ใส่ secret ใน URL หน้าเว็บเก็บใน sessionStorage ของ tab
สิทธิ์ token นี้เป็น operator ของ workspace เดียว ไม่ได้มีระบบผู้ใช้หลายระดับ

หากนำขึ้นเซิร์ฟเวอร์ ใช้ HTTPS reverse proxy ที่รองรับ WebSocket Upgrade,
ตั้ง `PPE_ALLOWED_ORIGINS` เป็น origin จริง และกำหนด upload limit/timeout ของ proxy
ให้สอดคล้องกับวิดีโอ ใช้ service manager รัน process เดียวและ restart เมื่อ crash
bind backend ที่ loopback หลัง proxy; คง auth, firewall และสิทธิ์ data directory
สำรอง SQLite ด้วย SQLite backup API หรือหยุด backend ก่อน copy ทั้ง data directory
health check ใช้ `/health`; กล้องของ site ต้องเข้าถึงได้จากเครื่อง backend

| Environment | Default |
| --- | --- |
| `PPE_MODEL_PATH` | `models/best.pt` |
| `PPE_DATA_DIR` | `backend/data` |
| `PPE_FRONTEND_DIR` | `frontend/dist` |
| `PPE_DEVICE` | `auto` (เลือก CUDA GPU 0 หากพร้อม; บังคับได้ด้วย `0` หรือ `cpu`) |
| `PPE_IMAGE_SIZE` | `640` (multiple of 32, 320–1536) |
| `PPE_MAX_FPS` | `15` (1–30) |
| `PPE_MAX_UPLOAD_MB` | `500` (1–4096) |
| `PPE_ENV` | `development` |
| `PPE_API_TOKEN` | ว่างสำหรับ local development |
| `PPE_ALLOWED_ORIGINS` | localhost และ 127.0.0.1 พอร์ต 5173 / 8000 |

paths แบบ relative อ้างจาก project root ค่า auto เลือก CUDA เมื่อ PyTorch มองเห็น GPU
และใช้ CPU บน environment ที่ไม่มี CUDA หากบังคับ GPU ด้วย PPE_DEVICE=0 แล้ว CUDA
ไม่พร้อม ระบบจะแจ้งข้อผิดพลาดแทนการเปลี่ยนไป CPU โดยไม่แจ้ง
startup warm-up จะตรวจ device ก่อนรายงานว่า backend พร้อม

## การทดสอบ

```powershell
py -3.11 -m pip install -r backend/requirements-dev.txt
py -3.11 -m pytest backend/tests -q
cd frontend
npm test
npm run build
npx --yes npm@11.6.2 audit
```

Backend tests ใช้ controlled detector เพื่อพิสูจน์ spatial matching, แยกเจ้าของ PPE,
โซน normalized, tracker, event dedup, persistence, CRUD/conflicts,
multipart size limits (รวม chunked), auth/origin, JSON/JPEG WebSocket,
pause/resume/hot edit, snapshots, acknowledgement และ restart recovery
Frontend tests ครอบคลุม geometry, dynamic PPE form และ frame/reconnect ordering

ทดสอบ browser จริงกับ `best.pt` และวิดีโอตัวอย่าง: ลากสร้าง PPE/restricted zones,
พบทั้ง missing-PPE/intrusion events, ปิด/เปิดโซนทันที, เปิด snapshot และ acknowledge
ตรวจ UI desktop/mobile และธีม light/dark โดยยังไม่ได้ทดสอบ hardware webcam/RTSP จริง
รายงานและภาพอยู่ใน `docs/VALIDATION.md` และ `docs/screenshots/`

อ้างอิง API ที่ตรวจระหว่างพัฒนา:
[Ultralytics predict](https://docs.ultralytics.com/modes/predict/) และ
[FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)



## โซน Polygon / Pen

Backend ตรวจตำแหน่งคนด้วย point-in-polygon ตามขอบรูปจริง รวมจุดบนขอบและรูปเว้า
โดยทั้งสองโหมดใช้กฎ PPE และ Restricted ได้เหมือนกัน โซนสี่เหลี่ยมเดิมยังอ่านได้
รายละเอียด API รูปทรง การแก้จุด และตัวอย่างอยู่ใน [docs/POLYGON_ZONES.md](docs/POLYGON_ZONES.md)
