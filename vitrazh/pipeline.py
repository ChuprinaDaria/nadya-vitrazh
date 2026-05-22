from __future__ import annotations

import logging
import time
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from vitrazh.camera.opencv_source import OpenCVSource
from vitrazh.detection.person_detector import PersonDetector
from vitrazh.models import Config, InstallationState, PoseClass
from vitrazh.motor.mock import MockMotorController
from vitrazh.state_machine import VitrazStateMachine

logger = logging.getLogger(__name__)


class VitrazPipeline:
    """Main pipeline: camera -> person detection -> pose classification -> state machine -> motors."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._callbacks: list[Callable[[InstallationState, PoseClass, int], None]] = []
        self._last_frame: NDArray[np.uint8] | None = None
        self._last_detections: list = []
        self._last_landmarks: list | None = None

        self._detector = PersonDetector(
            model_path=config.detection.model,
            confidence=config.detection.confidence,
            device=config.detection.device,
        )

        self._pose_classifier = None
        if self._check_mediapipe():
            from vitrazh.detection.pose_classifier import PoseClassifier
            self._pose_classifier = PoseClassifier(
                config=config.classifier,
                min_detection_confidence=config.pose.min_detection_confidence,
                min_tracking_confidence=config.pose.min_tracking_confidence,
            )
        else:
            logger.warning("MediaPipe unavailable on this CPU — running without pose detection")

        self._state_machine = VitrazStateMachine(config.state_machine)

        # Motor controller — mock by default
        self._motor = MockMotorController()

    @staticmethod
    def _check_mediapipe() -> bool:
        """Test mediapipe landmarker in subprocess (crashes with SIGILL on old CPUs)."""
        import subprocess, sys
        test_code = (
            "from vitrazh.detection.pose_classifier import PoseClassifier; "
            "PoseClassifier()"
        )
        try:
            r = subprocess.run(
                [sys.executable, "-c", test_code],
                capture_output=True, timeout=30,
            )
            return r.returncode == 0
        except Exception:
            return False

    @property
    def last_frame(self) -> NDArray[np.uint8] | None:
        return self._last_frame

    @property
    def last_detections(self):
        return self._last_detections

    @property
    def last_landmarks(self):
        return self._last_landmarks

    @property
    def state(self) -> InstallationState:
        return self._state_machine.state

    def on_update(self, callback: Callable[[InstallationState, PoseClass, int], None]) -> None:
        """Register callback: (state, pose, person_count)."""
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
            if self._pose_classifier is not None:
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
            person_count = len(detections)
            self._last_detections = detections

            # Step 2: Classify pose (only if person detected and classifier available)
            pose = PoseClass.IDLE
            self._last_landmarks = None
            if person_present and self._pose_classifier is not None:
                pose, pose_conf = self._pose_classifier.classify(frame)
                self._last_landmarks = self._pose_classifier.last_landmarks
                if pose != PoseClass.IDLE:
                    logger.debug("Pose: %s (conf=%.2f)", pose.value, pose_conf)

            # Step 3: Update state machine
            prev_state = self._state_machine.state
            new_state = self._state_machine.update(person_count, pose)

            # Step 4: Command motors on state change
            if new_state != prev_state:
                self._motor.set_state(new_state)

            # Step 5: Notify callbacks
            for cb in self._callbacks:
                try:
                    cb(new_state, pose, person_count)
                except Exception:
                    logger.exception("Callback error")

            if max_frames and frame_count >= max_frames:
                break

        logger.info("Pipeline stopped after %d frames", frame_count)

    def shutdown(self) -> None:
        self._motor.shutdown()
