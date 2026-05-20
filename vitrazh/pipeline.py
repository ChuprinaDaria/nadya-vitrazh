from __future__ import annotations

import logging
import time
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from vitrazh.camera.opencv_source import OpenCVSource
from vitrazh.detection.person_detector import PersonDetector
from vitrazh.detection.pose_classifier import PoseClassifier
from vitrazh.models import Config, InstallationState, PoseClass
from vitrazh.motor.mock import MockMotorController
from vitrazh.state_machine import VitrazStateMachine

logger = logging.getLogger(__name__)


class VitrazPipeline:
    """Main pipeline: camera -> person detection -> pose classification -> state machine -> motors."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._callbacks: list[Callable[[InstallationState, PoseClass, bool], None]] = []
        self._last_frame: NDArray[np.uint8] | None = None

        self._detector = PersonDetector(
            model_path=config.detection.model,
            confidence=config.detection.confidence,
            device=config.detection.device,
        )

        self._pose_classifier = PoseClassifier(
            config=config.classifier,
            min_detection_confidence=config.pose.min_detection_confidence,
            min_tracking_confidence=config.pose.min_tracking_confidence,
        )

        self._state_machine = VitrazStateMachine(config.state_machine)

        # Motor controller — mock by default
        self._motor = MockMotorController()

    @property
    def last_frame(self) -> NDArray[np.uint8] | None:
        return self._last_frame

    @property
    def state(self) -> InstallationState:
        return self._state_machine.state

    def on_update(self, callback: Callable[[InstallationState, PoseClass, bool], None]) -> None:
        """Register callback: (state, pose, person_present)."""
        self._callbacks.append(callback)

    def run(self, max_frames: int = 0) -> None:
        cam_cfg = self._config.camera
        camera = OpenCVSource(
            source=cam_cfg.source,
            camera_id=cam_cfg.camera_id,
            fps_limit=cam_cfg.fps_limit,
        )

        try:
            self._run_loop(camera, max_frames)
        finally:
            camera.release()
            self._pose_classifier.close()

    def _run_loop(self, camera: OpenCVSource, max_frames: int) -> None:
        frame_count = 0
        logger.info("Pipeline started for camera %s", camera.camera_id)

        while True:
            frame = camera.read_frame()
            if frame is None:
                if camera.is_file:
                    logger.info("End of video file")
                    break
                continue

            frame_count += 1
            self._last_frame = frame

            # Step 1: Detect persons
            detections, person_present = self._detector.detect_and_check(frame)

            # Step 2: Classify pose (only if person detected)
            pose = PoseClass.IDLE
            if person_present:
                pose, pose_conf = self._pose_classifier.classify(frame)
                if pose != PoseClass.IDLE:
                    logger.debug("Pose: %s (conf=%.2f)", pose.value, pose_conf)

            # Step 3: Update state machine
            prev_state = self._state_machine.state
            new_state = self._state_machine.update(person_present, pose)

            # Step 4: Command motors on state change
            if new_state != prev_state:
                self._motor.set_state(new_state)

            # Step 5: Notify callbacks
            for cb in self._callbacks:
                try:
                    cb(new_state, pose, person_present)
                except Exception:
                    logger.exception("Callback error")

            if max_frames and frame_count >= max_frames:
                break

        logger.info("Pipeline stopped after %d frames", frame_count)

    def shutdown(self) -> None:
        self._motor.shutdown()
