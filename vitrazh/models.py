from __future__ import annotations

import enum
import os
from dataclasses import dataclass

from pydantic import BaseModel, Field


class PoseClass(str, enum.Enum):
    IDLE = "idle"
    PHOTOGRAPHING = "photographing"
    PHONE_VIEWING = "phone_viewing"


class InstallationState(str, enum.Enum):
    SPINNING = "spinning"
    TEASING = "teasing"
    PURSUIT = "pursuit"
    ASSEMBLING = "assembling"
    ASSEMBLED = "assembled"


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    z: float
    visibility: float


class BBox(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(ge=0.0, le=1.0)
    h: float = Field(ge=0.0, le=1.0)


class Detection(BaseModel):
    object_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BBox
    tracking_id: str | None = None


# --- Config models ---


class CameraConfig(BaseModel):
    source: str | int = 0
    camera_id: str = "pavilion_cam1"
    fps_limit: int = Field(default=15, gt=0)


class DetectionConfig(BaseModel):
    model: str = "yolov8n.pt"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    device: str = "auto"


class PoseConfig(BaseModel):
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


class ClassifierConfig(BaseModel):
    elbow_angle_min: float = 30.0
    elbow_angle_max: float = 150.0
    phone_distance_threshold: float = 0.15
    min_pose_confidence: float = 0.6


class StateMachineConfig(BaseModel):
    absence_delay: float = 3.0
    pursuit_duration: float = 30.0
    photo_resume_delay: float = 1.5


class MotorConfig(BaseModel):
    type: str = "mock"
    pins: list[int] = Field(default_factory=list)
    serial_port: str = "/dev/ttyUSB0"
    serial_baud: int = 9600


class DashboardConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class Config(BaseModel):
    camera: CameraConfig = Field(default_factory=CameraConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    pose: PoseConfig = Field(default_factory=PoseConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)
    state_machine: StateMachineConfig = Field(default_factory=StateMachineConfig)
    motor: MotorConfig = Field(default_factory=MotorConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
