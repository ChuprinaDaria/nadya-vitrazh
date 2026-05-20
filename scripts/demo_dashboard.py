"""Standalone demo dashboard — no ML dependencies needed.

Simulates person detection and pose changes so you can preview the UI.

Usage:
    python scripts/demo_dashboard.py [--port 8000]
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "vitrazh" / "dashboard" / "static"

STATES = ["rotating", "assembling", "assembled", "disassembling"]
POSES = ["idle", "photographing", "phone_viewing"]


def create_app() -> FastAPI:
    app = FastAPI(title="Vitrazh Demo Dashboard")

    clients: list[WebSocket] = []
    loop: asyncio.AbstractEventLoop | None = None

    current = {
        "state": "rotating",
        "pose": "idle",
        "person_present": False,
        "mode": "prototype",
    }

    def simulation_loop() -> None:
        """Simulate state changes every few seconds."""
        while True:
            time.sleep(random.uniform(3, 6))

            # Random scenario
            roll = random.random()
            if current["state"] == "rotating":
                if roll < 0.5:
                    # Person approaches
                    current["person_present"] = True
                    current["pose"] = "idle"
                    broadcast(current)
                    time.sleep(2.0)
                    current["state"] = "assembling"
                    broadcast(current)
                    time.sleep(0.3)
                    current["state"] = "assembled"
                    broadcast(current)
            elif current["state"] == "assembled":
                if roll < 0.3:
                    # Person leaves
                    current["person_present"] = False
                    current["pose"] = "idle"
                    broadcast(current)
                    time.sleep(3.0)
                    current["state"] = "disassembling"
                    broadcast(current)
                    time.sleep(0.3)
                    current["state"] = "rotating"
                    broadcast(current)
                elif roll < 0.6:
                    # Person takes photo
                    current["pose"] = random.choice(["photographing", "phone_viewing"])
                    broadcast(current)
                    time.sleep(2.0)
                    current["state"] = "disassembling"
                    broadcast(current)
                    time.sleep(0.3)
                    current["state"] = "rotating"
                    current["person_present"] = True
                    current["pose"] = "idle"
                    broadcast(current)
                else:
                    # Person just stands
                    current["pose"] = "idle"
                    broadcast(current)

    def broadcast(data: dict) -> None:
        msg = json.dumps(data)
        if loop is not None:
            asyncio.run_coroutine_threadsafe(_broadcast(msg), loop)

    async def _broadcast(msg: str) -> None:
        disconnected = []
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            clients.remove(ws)

    @app.on_event("startup")
    async def startup() -> None:
        nonlocal loop
        loop = asyncio.get_event_loop()
        t = threading.Thread(target=simulation_loop, daemon=True)
        t.start()
        logger.info("Demo simulation started")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/state")
    async def get_state() -> dict:
        return current

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        clients.append(ws)
        try:
            await ws.send_text(json.dumps(current))
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            if ws in clients:
                clients.remove(ws)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
