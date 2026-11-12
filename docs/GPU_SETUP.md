# NVIDIA GPU setup

The backend defaults to **auto**: CUDA GPU 0 when available, otherwise CPU.
Explicit PPE_DEVICE=0 (or cuda:0) requires working CUDA and fails visibly when it
is unavailable. PPE_DEVICE=cpu always selects CPU.

Run from the project root on Windows with Python 3.11 and an NVIDIA driver:

~~~powershell
.\setup_gpu.bat
.\run_backend.bat
~~~

The setup creates a project-local .venv and installs matching CUDA wheels from the
official PyTorch index, followed by the application's dependencies, pinned through backend/constraints-gpu.txt.
It does not replace the global Python environment. The launcher prefers .venv.

The pinned Torch/NumPy baseline is kept compatible with the supplied model:
Torch 2.2.2+cu121, torchvision 0.17.2+cu121, NumPy 1.26.4 and OpenCV 4.11.
The CUDA wheel download is approximately 2.5 GB. Installing the full CUDA Toolkit
separately is not necessary for these packaged PyTorch wheels.

Manual installation:

~~~powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.2.2+cu121 torchvision==0.17.2+cu121 --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -c backend/constraints-gpu.txt
~~~

Verify this exact environment:

~~~powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
~~~

The application's AI Model page and GET /api/classes report the selected device
(e.g. cuda:0) and its actual hardware name. Startup warms up the real model on the
selected device before readiness. GPU acceleration applies to YOLO inference;
video capture/decoding and the rule engine continue to use their existing CPU paths.

Override the device before starting:

~~~powershell
$env:PPE_DEVICE = "0"    # Require NVIDIA GPU 0
.\run_backend.bat
~~~

Use cpu to force CPU, or auto to restore automatic selection. Restart the backend
after changing the Python environment or device. Use one backend worker.

NVIDIA-SMI's displayed CUDA version describes driver support. It does not mean
PyTorch must use that exact CUDA runtime version. The installed driver supports
older compatible CUDA runtimes through backward compatibility.

References: [official PyTorch version-specific commands](https://pytorch.org/get-started/previous-versions/),
[NVIDIA CUDA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html),
and [Ultralytics prediction devices](https://docs.ultralytics.com/modes/predict/).


## Verified on this machine

- NVIDIA GeForce RTX 3050 Laptop GPU, 4 GB; CUDA device 0.
- PyTorch 2.2.2+cu121 and torchvision 0.17.2+cu121, CUDA runtime 12.1.
- A complete project-local Python 3.11 virtualenv; global Python remains separate.
- Actual CUDA tensor computation, model parameters on cuda:0, real video inference,
  JSON/JPEG WebSocket delivery and both rule types passed.
- 40 backend tests, 21 frontend tests, production build and pip check passed.

Using 12 identical 1280x720 frames at inference size 640 after warm-up in the same
environment, median inference time was **125.52 ms on CPU** and **24.78 ms on GPU**,
approximately **5.07x faster**. This is inference time, not guaranteed stream FPS.
Capture/decoding, resizing, JPEG encoding and the configured frame-rate cap still
affect the displayed stream. The original CPU environment measured 179.79 ms;
the matched-environment comparison above avoids mixing package environments.

The main application on port 8000 was restarted using .venv and reports cuda:0 and
the RTX 3050 hardware name. Existing zones were verified. The previous video had
ended; start monitoring again to open a source. Details:
[validation-gpu.json](validation-gpu.json) and [GPU page](screenshots/gpu-model.jpg).
