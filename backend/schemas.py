from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .geometry import validate_polygon


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Rect(StrictModel):
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self):
        if self.x2 - self.x1 < 0.005 or self.y2 - self.y1 < 0.005:
            raise ValueError("Rectangle must have positive width and height of at least 0.005")
        return self


class Point(StrictModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class ZoneInput(StrictModel):
    source_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["ppe", "restricted"]
    shape: Literal["rectangle", "polygon"] = "rectangle"
    rect: Rect | None = None
    points: list[Point] | None = Field(default=None, min_length=3, max_length=64)
    required_class_ids: list[int] = Field(default_factory=list, max_length=20)
    anchor: Literal["feet", "centroid"] = "feet"
    enabled: bool = True

    @model_validator(mode="after")
    def meaningful(self):
        if self.shape == "polygon":
            if not self.points:
                raise ValueError("Polygon zones require points")
            validate_polygon([(point.x, point.y) for point in self.points])
            self.rect = Rect(x1=min(point.x for point in self.points), y1=min(point.y for point in self.points),
                             x2=max(point.x for point in self.points), y2=max(point.y for point in self.points))
        elif self.rect is None or self.points is not None:
            raise ValueError("Rectangle zones require rect and must not contain polygon points")
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Zone name cannot be blank")
        if len(set(self.required_class_ids)) != len(self.required_class_ids):
            raise ValueError("Required PPE classes must be unique")
        if self.kind == "ppe" and not self.required_class_ids:
            raise ValueError("Select at least one required PPE class")
        if self.kind == "restricted" and self.required_class_ids:
            raise ValueError("Restricted zones do not have PPE requirements")
        return self


class Zone(ZoneInput):
    id: str
    version: int = 1
    updated_at: str


class ZonePatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: Literal["ppe", "restricted"] | None = None
    rect: Rect | None = None
    shape: Literal["rectangle", "polygon"] | None = None
    points: list[Point] | None = Field(default=None, min_length=3, max_length=64)
    required_class_ids: list[int] | None = Field(default=None, max_length=20)
    anchor: Literal["feet", "centroid"] | None = None
    enabled: bool | None = None
    expected_version: int | None = Field(default=None, ge=1)


class StartRequest(StrictModel):
    kind: Literal["camera", "video"]
    address: str | None = Field(default=None, max_length=2048)
    video_id: str | None = Field(default=None, max_length=100)
    loop: bool = False

    @model_validator(mode="after")
    def source(self):
        if self.kind == "camera" and (not self.address or self.video_id):
            raise ValueError("Camera mode requires an address and no video_id")
        if self.kind == "video" and (not self.video_id or self.address):
            raise ValueError("Video mode requires video_id and no camera address")
        return self


class MonitorSettings(StrictModel):
    confidence: float = Field(default=0.25, ge=0.05, le=0.95)
    association_threshold: float = Field(default=0.5, ge=0.2, le=0.95)
    resolve_after_seconds: float = Field(default=1.5, ge=0.2, le=10)
