"""Select a single inference device without hiding explicit CUDA failures."""

import torch


def resolve_device(requested: str):
    value = requested.strip().lower()
    if value == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    if value == "cpu":
        return torch.device("cpu")
    index = value.removeprefix("cuda:")
    if value == "cuda":
        index = "0"
    if not index.isdigit():
        raise ValueError("PPE_DEVICE must be auto, cpu, or a single CUDA index such as 0 or cuda:0")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable in this Python environment. Run setup_gpu.bat with an NVIDIA GPU, or set PPE_DEVICE=cpu.")
    if int(index) >= torch.cuda.device_count():
        raise ValueError("PPE_DEVICE refers to a CUDA GPU that is not available")
    return torch.device("cuda:" + str(int(index)))
