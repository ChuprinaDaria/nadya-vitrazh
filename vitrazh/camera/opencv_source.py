from __future__ import annotations

import logging
import time

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class OpenCVSource:
    """Camera source with FPS limiting and auto-reconnect for RTSP streams."""

    def __init__(
        self,
        source: str | int,
        camera_id: str,
        fps_limit: int = 15,
    ) -> None:
        self._source = source
        self._camera_id = camera_id
        self._fps_limit = fps_limit
        self._cap: cv2.VideoCapture | None = None
        self._backoff = 1.0
        self._max_backoff = 30.0
        self._last_frame_time = 0.0
        self._frame_interval = 1.0 / fps_limit
        self._connect()

    @property
    def camera_id(self) -> str:
        return self._camera_id

    def _connect(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = cv2.VideoCapture(self._source)
        if self._cap.isOpened():
            logger.info("Camera %s connected: %s", self._camera_id, self._source)
            self._backoff = 1.0
        else:
            logger.warning("Camera %s failed to open: %s", self._camera_id, self._source)

    def read_frame(self) -> NDArray[np.uint8] | None:
        now = time.monotonic()
        elapsed = now - self._last_frame_time
        if elapsed < self._frame_interval:
            time.sleep(self._frame_interval - elapsed)

        if self._cap is None or not self._cap.isOpened():
            logger.info("Camera %s reconnecting in %.1fs...", self._camera_id, self._backoff)
            time.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, self._max_backoff)
            self._connect()
            return None

        ret, frame = self._cap.read()
        if not ret:
            if isinstance(self._source, str) and not self._source.startswith("rtsp"):
                return None
            logger.warning("Camera %s: frame read failed, reconnecting", self._camera_id)
            self._cap.release()
            self._cap = None
            return None

        self._last_frame_time = time.monotonic()
        return frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_file(self) -> bool:
        return isinstance(self._source, str) and not self._source.startswith("rtsp")
