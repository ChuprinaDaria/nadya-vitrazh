from __future__ import annotations

from typing import Protocol

from vitrazh.models import InstallationState


class MotorController(Protocol):
    def set_state(self, state: InstallationState) -> None:
        """Command motors to transition to the given state."""
        ...

    def get_state(self) -> InstallationState:
        """Return current motor state."""
        ...

    def shutdown(self) -> None: ...
