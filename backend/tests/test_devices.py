import pytest

from backend.devices import resolve_device


def test_auto_uses_gpu_when_cuda_is_available(monkeypatch):
    monkeypatch.setattr("backend.devices.torch.cuda.is_available", lambda: True)
    assert str(resolve_device("auto")) == "cuda:0"


def test_auto_uses_cpu_when_cuda_is_unavailable(monkeypatch):
    monkeypatch.setattr("backend.devices.torch.cuda.is_available", lambda: False)
    assert str(resolve_device("auto")) == "cpu"
    assert str(resolve_device("cpu")) == "cpu"


@pytest.mark.parametrize("value", ["0", "cuda:0", "cuda"])
def test_explicit_gpu_requires_a_working_cuda_runtime(monkeypatch, value):
    monkeypatch.setattr("backend.devices.torch.cuda.is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        resolve_device(value)


def test_explicit_gpu_index_is_validated(monkeypatch):
    monkeypatch.setattr("backend.devices.torch.cuda.is_available", lambda: True)
    monkeypatch.setattr("backend.devices.torch.cuda.device_count", lambda: 1)
    assert str(resolve_device("0")) == "cuda:0"
    with pytest.raises(ValueError, match="not available"):
        resolve_device("1")
    with pytest.raises(ValueError, match="PPE_DEVICE"):
        resolve_device("typo")
