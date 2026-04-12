"""Screen capture using dxcam (preferred) or mss (fallback)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Captures the screen as a numpy array (RGB)."""

    def __init__(self, config: Config) -> None:
        self._backend = config.capture_backend
        self._dxcam_camera = None
        self._init_backend()

    def _init_backend(self) -> None:
        if self._backend == "dxcam":
            try:
                import dxcam

                self._dxcam_camera = dxcam.create()
                logger.info("Using dxcam capture backend")
            except Exception:
                logger.warning("dxcam unavailable, falling back to mss")
                self._backend = "mss"

        if self._backend == "mss":
            logger.info("Using mss capture backend")

    def grab(self) -> np.ndarray:
        """Capture the full screen and return an RGB numpy array."""
        if self._backend == "dxcam" and self._dxcam_camera is not None:
            return self._grab_dxcam()
        return self._grab_mss()

    def _grab_dxcam(self) -> np.ndarray:
        frame = self._dxcam_camera.grab()
        if frame is None:
            # dxcam returns None if no new frame; retry once with a fresh grab
            import time

            time.sleep(0.05)
            frame = self._dxcam_camera.grab()
        if frame is None:
            logger.warning("dxcam returned no frame, falling back to mss")
            return self._grab_mss()
        return np.asarray(frame)

    def _grab_mss(self) -> np.ndarray:
        import mss

        with mss.mss() as sct:
            monitor = sct.monitors[0]  # full virtual screen
            shot = sct.grab(monitor)
            # mss returns BGRA; convert to RGB
            img = np.frombuffer(shot.raw, dtype=np.uint8).reshape(
                shot.height, shot.width, 4
            )
            return img[:, :, 2::-1].copy()  # BGRA → RGB
