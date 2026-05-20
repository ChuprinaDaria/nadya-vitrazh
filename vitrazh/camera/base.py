from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class CameraSource(Protocol):
    @property
    def camera_id(self) -> str: ...

    def read_frame(self) -> NDArray[np.uint8] | None: ...

    def release(self) -> None: ...
