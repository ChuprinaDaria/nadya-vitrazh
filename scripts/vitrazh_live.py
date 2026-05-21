"""Vitrazh Live Demo — webcam + MediaPipe pose + 3D scene.

Run:
    pip install mediapipe opencv-python fastapi uvicorn
    python vitrazh_live.py

Open:
    http://localhost:8000
"""

import asyncio
import json
import math
import logging
import threading
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("vitrazh")

# ── MediaPipe Pose Landmarker ────────────────────────────

_tasks = mp.tasks
_vision = _tasks.vision

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/1/"
    "pose_landmarker_lite.task"
)
MODEL_PATH = Path(__file__).parent / "pose_landmarker_lite.task"

NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16


def ensure_model():
    if not MODEL_PATH.exists():
        logger.info("Downloading pose model...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        logger.info("Model ready.")


# ── State machine (simplified) ───────────────────────────

class StateMachine:
    def __init__(self):
        self.state = "spinning"
        self._absence_t = None
        self._pursuit_t = None
        self._photo_t = None
        self._assembled_t = None

    def update(self, n_persons, pose="idle"):
        now = time.monotonic()

        if n_persons == 0:
            if self._absence_t is None:
                self._absence_t = now
            if now - self._absence_t > 3.0:
                self.state = "spinning"
                self._pursuit_t = None
            return self.state

        self._absence_t = None

        if self.state == "spinning" and n_persons >= 1:
            self.state = "teasing"

        elif self.state == "teasing":
            if pose == "hands_up":
                self.state = "assembling"
            elif n_persons >= 2:
                self.state = "pursuit"
                self._pursuit_t = now

        elif self.state == "pursuit":
            if n_persons < 2:
                self.state = "teasing"
                self._pursuit_t = None
            elif pose == "hands_up":
                self.state = "assembling"
            elif self._pursuit_t and now - self._pursuit_t > 30.0:
                self.state = "assembling"

        elif self.state == "assembling":
            self.state = "assembled"
            self._assembled_t = now

        elif self.state == "assembled":
            if pose == "hands_up":
                self._assembled_t = now  # keep assembled while hands up
            elif n_persons >= 2:
                self._assembled_t = now  # keep assembled with 2+ people
                if pose == "photographing":
                    if self._photo_t is None:
                        self._photo_t = now
                    elif now - self._photo_t > 1.5:
                        self.state = "pursuit"
                        self._pursuit_t = now
                        self._photo_t = None
                else:
                    self._photo_t = None
            elif self._assembled_t and now - self._assembled_t > 5.0:
                self.state = "teasing"  # 5 sec after hands down → teasing

        return self.state


# ── Live detector ────────────────────────────────────────

class LiveDetector:
    def __init__(self):
        ensure_model()

        opts = _vision.PoseLandmarkerOptions(
            base_options=_tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=_vision.RunningMode.IMAGE,
            num_poses=2,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
        )
        self._landmarker = _vision.PoseLandmarker.create_from_options(opts)
        self._sm = StateMachine()
        self._running = True

        self.landmarks = None
        self.detections = []
        self.person_count = 0
        self.state = "spinning"
        self.pose = "idle"
        self.callbacks = []

    def _classify_pose(self, lms):
        if not lms or len(lms) < 17:
            return "idle"
        nose = lms[NOSE]
        # Hands up: both wrists above shoulders
        lw, rw = lms[L_WRIST], lms[R_WRIST]
        ls, rs = lms[L_SHOULDER], lms[R_SHOULDER]
        if (lw[2] > 0.3 and rw[2] > 0.3 and ls[2] > 0.3 and rs[2] > 0.3
                and lw[1] < ls[1] and rw[1] < rs[1]):
            return "hands_up"
        for wi in (L_WRIST, R_WRIST):
            w = lms[wi]
            if w[2] > 0.4:
                d = math.sqrt((nose[0] - w[0]) ** 2 + (nose[1] - w[1]) ** 2)
                if d < 0.15:
                    return "phone_viewing"
        for wi, ei in ((L_WRIST, L_ELBOW), (R_WRIST, R_ELBOW)):
            w, e = lms[wi], lms[ei]
            if w[2] > 0.4 and e[2] > 0.4 and w[1] < e[1]:
                if abs(w[1] - nose[1]) < 0.15:
                    return "photographing"
        return "idle"

    def _bbox(self, lms):
        xs = [l[0] for l in lms if l[2] > 0.3]
        ys = [l[1] for l in lms if l[2] > 0.3]
        if not xs:
            return None
        m = 0.05
        return {
            "x": max(0, min(xs) - m),
            "y": max(0, min(ys) - m),
            "w": min(1, max(xs) + m) - max(0, min(xs) - m),
            "h": min(1, max(ys) + m) - max(0, min(ys) - m),
        }

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Cannot open camera!")
            return

        logger.info("Camera opened — detection running")

        while self._running:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.01)
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._landmarker.detect(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            )

            dets = []
            primary_lms = None

            if result.pose_landmarks:
                for i, pose_lms in enumerate(result.pose_landmarks):
                    lms = [[lm.x, lm.y, lm.presence] for lm in pose_lms]
                    bb = self._bbox(lms)
                    if bb:
                        conf = sum(l[2] for l in lms[:17]) / 17
                        dets.append({
                            "bbox": bb,
                            "tracking_id": f"person_{i + 1}",
                            "confidence": round(conf, 2),
                        })
                    if i == 0:
                        primary_lms = lms

            self.person_count = len(dets)
            self.detections = dets
            self.landmarks = primary_lms
            self.pose = self._classify_pose(primary_lms) if primary_lms else "idle"
            self.state = self._sm.update(self.person_count, self.pose)

            for cb in self.callbacks:
                try:
                    cb()
                except Exception:
                    pass

            time.sleep(1 / 15)

        cap.release()
        self._landmarker.close()

    def stop(self):
        self._running = False


# ── FastAPI ──────────────────────────────────────────────

STATIC = Path(__file__).parent / "static"


def create_app(detector: LiveDetector) -> FastAPI:
    app = FastAPI(title="Vitrazh Live")
    clients: list[WebSocket] = []
    loop = None

    def on_update():
        nonlocal loop
        msg = json.dumps({
            "state": detector.state,
            "pose": detector.pose,
            "person_count": detector.person_count,
            "person_present": detector.person_count > 0,
            "mode": "prototype",
            "detections": detector.detections,
            "landmarks": detector.landmarks,
        })
        if loop:
            asyncio.run_coroutine_threadsafe(_broadcast(msg), loop)

    async def _broadcast(msg):
        dead = []
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            clients.remove(ws)

    detector.callbacks.append(on_update)

    @app.on_event("startup")
    async def startup():
        nonlocal loop
        loop = asyncio.get_event_loop()
        threading.Thread(target=detector.run, daemon=True).start()

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "installation.html")

    @app.get("/installation")
    async def installation():
        return FileResponse(STATIC / "installation.html")

    @app.get("/api/state")
    async def api_state():
        return {"state": detector.state, "person_count": detector.person_count}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        clients.append(ws)
        try:
            await ws.send_text(json.dumps({
                "state": detector.state,
                "pose": detector.pose,
                "person_count": detector.person_count,
                "person_present": detector.person_count > 0,
                "mode": "prototype",
                "detections": detector.detections,
                "landmarks": detector.landmarks,
            }))
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            if ws in clients:
                clients.remove(ws)

    if STATIC.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    return app


if __name__ == "__main__":
    import uvicorn

    det = LiveDetector()
    app = create_app(det)
    logger.info("Starting on http://0.0.0.0:8000")
    logger.info("Open http://localhost:8000 in browser")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
