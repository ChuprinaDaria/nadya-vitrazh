from __future__ import annotations

import logging
import time

from vitrazh.models import InstallationState, PoseClass, StateMachineConfig

logger = logging.getLogger(__name__)


class VitrazStateMachine:
    """Controls stained glass state based on person presence and pose.

    State transitions:
        ROTATING -> ASSEMBLING:     person detected for presence_delay seconds
        ASSEMBLING -> ASSEMBLED:    automatic (transition time)
        ASSEMBLED -> ROTATING:      person leaves for absence_delay seconds
        ASSEMBLED -> ROTATING:      person takes photo pose, after photo_resume_delay
        ROTATING:                   default state, glass pieces spinning
    """

    def __init__(self, config: StateMachineConfig | None = None) -> None:
        self._config = config or StateMachineConfig()
        self._state = InstallationState.ROTATING
        self._person_first_seen: float | None = None
        self._person_last_seen: float | None = None
        self._photo_pose_start: float | None = None

    @property
    def state(self) -> InstallationState:
        return self._state

    def update(self, person_present: bool, pose: PoseClass, now: float | None = None) -> InstallationState:
        """Update state machine with current detection results.

        Args:
            person_present: True if at least one person detected
            pose: Classified pose of the nearest person
            now: Current timestamp (defaults to time.monotonic())

        Returns:
            New installation state
        """
        if now is None:
            now = time.monotonic()

        cfg = self._config

        if person_present:
            self._person_last_seen = now
            if self._person_first_seen is None:
                self._person_first_seen = now

        if self._state == InstallationState.ROTATING:
            # Waiting for person to approach
            if person_present and self._person_first_seen is not None:
                if now - self._person_first_seen >= cfg.presence_delay:
                    self._transition(InstallationState.ASSEMBLING)

        elif self._state == InstallationState.ASSEMBLING:
            # Brief transition state — immediately go to assembled
            self._transition(InstallationState.ASSEMBLED)

        elif self._state == InstallationState.ASSEMBLED:
            # Check if person left
            if not person_present and self._person_last_seen is not None:
                if now - self._person_last_seen >= cfg.absence_delay:
                    self._reset()
                    self._transition(InstallationState.ROTATING)

            # Check if person is taking a photo
            elif person_present and pose in (PoseClass.PHOTOGRAPHING, PoseClass.PHONE_VIEWING):
                if self._photo_pose_start is None:
                    self._photo_pose_start = now
                elif now - self._photo_pose_start >= cfg.photo_resume_delay:
                    self._photo_pose_start = None
                    self._transition(InstallationState.DISASSEMBLING)

            else:
                self._photo_pose_start = None

        elif self._state == InstallationState.DISASSEMBLING:
            # Brief transition — back to rotating
            self._reset()
            self._transition(InstallationState.ROTATING)

        return self._state

    def _transition(self, new_state: InstallationState) -> None:
        if new_state != self._state:
            logger.info("State: %s -> %s", self._state.value, new_state.value)
            self._state = new_state

    def _reset(self) -> None:
        self._person_first_seen = None
        self._person_last_seen = None
        self._photo_pose_start = None
