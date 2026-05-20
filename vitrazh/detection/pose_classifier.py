from __future__ import annotations

import logging
import math
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from numpy.typing import NDArray

from vitrazh.models import ClassifierConfig, Landmark, PoseClass

logger = logging.getLogger(__name__)

_mp_tasks = mp.tasks
_vision = _mp_tasks.vision

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)
_MODEL_PATH = Path(__file__).parent / "pose_landmarker_lite.task"

# MediaPipe Pose landmark indices
_NOSE = 0
_LEFT_EAR = 7
_RIGHT_EAR = 8
_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_ELBOW = 13
_RIGHT_ELBOW = 14
_LEFT_WRIST = 15
_RIGHT_WRIST = 16
_LEFT_HIP = 23
_RIGHT_HIP = 24


def _ensure_model() -> None:
    if not _MODEL_PATH.exists():
        logger.info("Downloading pose model to %s ...", _MODEL_PATH)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        logger.info("Download complete.")


def _angle(a: Landmark, b: Landmark, c: Landmark) -> float:
    """Angle at point b in degrees (a-b-c)."""
    ba = (a.x - b.x, a.y - b.y)
    bc = (c.x - b.x, c.y - b.y)
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag_ba = math.sqrt(ba[0] ** 2 + ba[1] ** 2)
    mag_bc = math.sqrt(bc[0] ** 2 + bc[1] ** 2)
    if mag_ba * mag_bc < 1e-6:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_angle))


def _distance(a: Landmark, b: Landmark) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


class PoseClassifier:
    """Classifies person pose from MediaPipe landmarks.

    Categories:
    - PHOTOGRAPHING: arms raised, holding something (camera/phone at eye level)
    - PHONE_VIEWING: wrist near face, head tilted down (looking at phone screen)
    - IDLE: anything else
    """

    def __init__(
        self,
        config: ClassifierConfig | None = None,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        _ensure_model()
        self._config = config or ClassifierConfig()

        options = _vision.PoseLandmarkerOptions(
            base_options=_mp_tasks.BaseOptions(model_asset_path=str(_MODEL_PATH)),
            running_mode=_vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = _vision.PoseLandmarker.create_from_options(options)

    def _get_landmarks(self, frame: NDArray[np.uint8]) -> list[Landmark] | None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if frame.shape[2] == 3 else frame
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(mp_image)
        if not result.pose_landmarks:
            return None
        return [
            Landmark(x=lm.x, y=lm.y, z=lm.z, visibility=lm.presence)
            for lm in result.pose_landmarks[0]
        ]

    def classify(self, frame: NDArray[np.uint8]) -> tuple[PoseClass, float]:
        """Classify the pose of the nearest person in the frame.

        Returns:
            (pose_class, confidence) where confidence is 0.0-1.0
        """
        landmarks = self._get_landmarks(frame)
        if landmarks is None:
            return PoseClass.IDLE, 0.0

        return self._classify_from_landmarks(landmarks)

    def _classify_from_landmarks(self, lm: list[Landmark]) -> tuple[PoseClass, float]:
        cfg = self._config

        # Check visibility of key points
        key_indices = [_NOSE, _LEFT_SHOULDER, _RIGHT_SHOULDER,
                       _LEFT_ELBOW, _RIGHT_ELBOW, _LEFT_WRIST, _RIGHT_WRIST]
        avg_vis = sum(lm[i].visibility for i in key_indices) / len(key_indices)
        if avg_vis < cfg.min_pose_confidence:
            return PoseClass.IDLE, avg_vis

        # --- Phone viewing: wrist close to face, head tilted ---
        nose = lm[_NOSE]
        l_wrist = lm[_LEFT_WRIST]
        r_wrist = lm[_RIGHT_WRIST]

        l_dist = _distance(nose, l_wrist)
        r_dist = _distance(nose, r_wrist)
        min_wrist_dist = min(l_dist, r_dist)

        if min_wrist_dist < cfg.phone_distance_threshold:
            # Wrist very close to face — likely holding phone to face
            conf = 1.0 - (min_wrist_dist / cfg.phone_distance_threshold)
            return PoseClass.PHONE_VIEWING, min(1.0, conf)

        # --- Photographing: arms raised, elbows bent ---
        l_shoulder = lm[_LEFT_SHOULDER]
        r_shoulder = lm[_RIGHT_SHOULDER]
        l_elbow = lm[_LEFT_ELBOW]
        r_elbow = lm[_RIGHT_ELBOW]

        l_angle = _angle(l_shoulder, l_elbow, l_wrist)
        r_angle = _angle(r_shoulder, r_elbow, r_wrist)

        # At least one arm raised with bent elbow
        l_photo = cfg.elbow_angle_min <= l_angle <= cfg.elbow_angle_max
        r_photo = cfg.elbow_angle_min <= r_angle <= cfg.elbow_angle_max

        # Wrists should be above elbows (raised arms)
        l_raised = l_wrist.y < l_elbow.y
        r_raised = r_wrist.y < r_elbow.y

        if (l_photo and l_raised) or (r_photo and r_raised):
            # Check if wrists are roughly at face level (photographing)
            face_y = nose.y
            l_at_face = abs(l_wrist.y - face_y) < 0.15
            r_at_face = abs(r_wrist.y - face_y) < 0.15

            if l_at_face or r_at_face:
                conf = avg_vis
                return PoseClass.PHOTOGRAPHING, conf

        return PoseClass.IDLE, avg_vis

    def close(self) -> None:
        self._landmarker.close()
