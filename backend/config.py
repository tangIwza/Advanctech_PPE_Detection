from dataclasses import dataclass, field
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    model_path: Path = ROOT / "models/best.pt"
    data_dir: Path = ROOT / "backend/data"
    frontend_dir: Path = ROOT / "frontend/dist"
    api_token: str = field(default="", repr=False)
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8000", "http://127.0.0.1:8000",
    )
    max_upload_bytes: int = 500 * 1024 * 1024
    max_zones: int = 32
    max_alerts: int = 5000
    retention_days: int = 30
    max_fps: float = 15.0
    image_size: int = 640
    device: str = "cpu"
    production: bool = False

    @classmethod
    def from_env(cls):
        def path(name, default):
            value = Path(os.getenv(name, str(default))).expanduser()
            return (value if value.is_absolute() else ROOT / value).resolve()

        production = os.getenv("PPE_ENV", "development") == "production"
        token = os.getenv("PPE_API_TOKEN", "")
        if production and len(token) < 32:
            raise ValueError("Production requires PPE_API_TOKEN with at least 32 characters")
        if token and any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in token):
            raise ValueError("PPE_API_TOKEN must contain only letters, numbers, underscores or hyphens")
        origins = tuple(value.strip().rstrip("/") for value in os.getenv(
            "PPE_ALLOWED_ORIGINS", ",".join(cls.allowed_origins)
        ).split(",") if value.strip())
        if not origins or "*" in origins:
            raise ValueError("Configure explicit PPE_ALLOWED_ORIGINS; wildcards are not supported")
        upload_mb = int(os.getenv("PPE_MAX_UPLOAD_MB", "500"))
        image_size = int(os.getenv("PPE_IMAGE_SIZE", "640"))
        max_fps = float(os.getenv("PPE_MAX_FPS", "15"))
        if not 1 <= upload_mb <= 4096:
            raise ValueError("PPE_MAX_UPLOAD_MB must be between 1 and 4096")
        if not 320 <= image_size <= 1536 or image_size % 32:
            raise ValueError("PPE_IMAGE_SIZE must be a multiple of 32 between 320 and 1536")
        if not math.isfinite(max_fps) or not 1 <= max_fps <= 30:
            raise ValueError("PPE_MAX_FPS must be between 1 and 30")
        return cls(
            model_path=path("PPE_MODEL_PATH", cls.model_path),
            data_dir=path("PPE_DATA_DIR", cls.data_dir),
            frontend_dir=path("PPE_FRONTEND_DIR", cls.frontend_dir),
            api_token=token, allowed_origins=origins,
            max_upload_bytes=upload_mb * 1024 * 1024,
            max_fps=max_fps, image_size=image_size,
            device=os.getenv("PPE_DEVICE", "cpu"), production=production,
        )
