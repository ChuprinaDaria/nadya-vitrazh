from __future__ import annotations

import logging
import time

from vitrazh.models import InstallationState, PoseClass, StateMachineConfig

logger = logging.getLogger(__name__)


class VitrazStateMachine:
    """Controls stained glass state based on person count and pose.

    Algorithm — "contra solitudinem":
        0 people  → SPINNING (panels rotate continuously)
        1 person  → TEASING (panels tease but never assemble — you need a friend)
        2+ people → PURSUIT (chaotic spin) → ASSEMBLING → ASSEMBLED after pursuit_duration

    The painting physically cannot assemble for one person.
    """

    def __init__(self, config: StateMachineConfig | None = None) -> None:
        self._config = config or StateMachineConfig()
        self._state = InstallationState.SPINNING
        self._person_last_seen: float | None = None
        self._pursuit_start: float | None = None
        self._photo_pose_start: float | None = None

    @property
    def state(self) -> InstallationState:
        return self._state

    @property
    def pursuit_elapsed(self) -> float:
        """Seconds since pursuit started (for UI timer)."""
        if self._pursuit_start is None:
            return 0.0
        return time.monotonic() - self._pursuit_start

    def update(
        self,
        person_count: int,
        pose: PoseClass,
        now: float | None = None,
    ) -> InstallationState:
        if now is None:
            now = time.monotonic()

        cfg = self._config

        if person_count > 0:
            self._person_last_seen = now

        # --- 0 people: return to SPINNING after grace period ---
        if person_count == 0:
            if self._person_last_seen is not None:
                if now - self._person_last_seen >= cfg.absence_delay:
                    self._reset()
                    self._transition(InstallationState.SPINNING)
            else:
                self._transition(InstallationState.SPINNING)
            return self._state

        # --- 1 person: TEASING (movement but no result) ---
        if person_count == 1:
            self._pursuit_start = None
            if self._state in (InstallationState.SPINNING, InstallationState.PURSUIT):
                self._transition(InstallationState.TEASING)
            elif self._state == InstallationState.ASSEMBLED:
                # Friend left — painting breaks
                self._transition(InstallationState.TEASING)
            elif self._state == InstallationState.ASSEMBLING:
                self._transition(InstallationState.TEASING)
            return self._state

        # --- 2+ people ---
        if self._state in (InstallationState.SPINNING, InstallationState.TEASING):
            self._pursuit_start = now
            self._transition(InstallationState.PURSUIT)

        elif self._state == InstallationState.PURSUIT:
            if self._pursuit_start is not None and now - self._pursuit_start >= cfg.pursuit_duration:
                self._transition(InstallationState.ASSEMBLING)

        elif self._state == InstallationState.ASSEMBLING:
            self._transition(InstallationState.ASSEMBLED)

        elif self._state == InstallationState.ASSEMBLED:
            # Photo pose → break apart and restart pursuit
            if pose in (PoseClass.PHOTOGRAPHING, PoseClass.PHONE_VIEWING):
                if self._photo_pose_start is None:
                    self._photo_pose_start = now
                elif now - self._photo_pose_start >= cfg.photo_resume_delay:
                    self._photo_pose_start = None
                    self._pursuit_start = now
                    self._transition(InstallationState.PURSUIT)
            else:
                self._photo_pose_start = None

        return self._state

    def _transition(self, new_state: InstallationState) -> None:
        if new_state != self._state:
            logger.info("State: %s -> %s", self._state.value, new_state.value)
            self._state = new_state

    def _reset(self) -> None:
        self._person_last_seen = None
        self._pursuit_start = None
        self._photo_pose_start = None
