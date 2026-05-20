from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray
from ultralytics import YOLO

from vitrazh.models import BBox, Detection

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0


class PersonDetector:
    """YOLOv8 person detector with ByteTrack tracking."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.5,
        device: str = "auto",
    ) -> None:
        import torch

        if device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"

        if device == "cpu":
            torch.backends.mkldnn.enabled = False

        self._model = YOLO(model_path)
        self._confidence = confidence
        self._device = device
        logger.info("YOLO loaded: %s on %s", model_path, device)

    def detect(self, frame: NDArray[np.uint8]) -> list[Detection]:
        h, w = frame.shape[:2]
        try:
            results = self._model.track(
                frame,
                persist=True,
                conf=self._confidence,
                classes=[PERSON_CLASS_ID],
                device=self._device,
                verbose=False,
            )
        except Exception:
            logger.exception("YOLO inference error")
            return []

        detections: list[Detection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                track_id = int(box.id[0]) if box.id is not None else None

                bx = round(max(0.0, min(1.0, x1 / w)), 4)
                by = round(max(0.0, min(1.0, y1 / h)), 4)
                bw = round(max(0.0, min(1.0, (x2 - x1) / w)), 4)
                bh = round(max(0.0, min(1.0, (y2 - y1) / h)), 4)

                detections.append(Detection(
                    object_type="person",
                    confidence=round(conf, 3),
                    bbox=BBox(x=bx, y=by, w=bw, h=bh),
                    tracking_id=f"track_{track_id}" if track_id is not None else None,
                ))

        return detections

    @property
    def person_detected(self) -> bool:
        """Shortcut used by pipeline — True if last detect() found anyone."""
        return bool(self._last_detections)

    def detect_and_check(self, frame: NDArray[np.uint8]) -> tuple[list[Detection], bool]:
        dets = self.detect(frame)
        self._last_detections = dets
        return dets, len(dets) > 0

    _last_detections: list[Detection] = []
