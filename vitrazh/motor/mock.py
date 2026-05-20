from __future__ import annotations

import logging

from vitrazh.models import InstallationState

logger = logging.getLogger(__name__)


class MockMotorController:
    """Mock motor controller for development without hardware."""

    def __init__(self) -> None:
        self._state = InstallationState.ROTATING
        logger.info("MockMotorController initialized (no real hardware)")

    def set_state(self, state: InstallationState) -> None:
        if state != self._state:
            logger.info("Motor state: %s -> %s", self._state.value, state.value)
            self._state = state

    def get_state(self) -> InstallationState:
        return self._state

    def shutdown(self) -> None:
        logger.info("MockMotorController shutdown")
