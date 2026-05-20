from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from vitrazh.models import Config, InstallationState, PoseClass
from vitrazh.pipeline import VitrazPipeline

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title="Vitrazh Dashboard")

    pipeline = VitrazPipeline(config)
    clients: list[WebSocket] = []
    loop: asyncio.AbstractEventLoop | None = None

    def on_update(state: InstallationState, pose: PoseClass, person_present: bool) -> None:
        msg = json.dumps({
            "state": state.value,
            "pose": pose.value,
            "person_present": person_present,
        })
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

    pipeline.on_update(on_update)

    @app.on_event("startup")
    async def startup() -> None:
        nonlocal loop
        loop = asyncio.get_event_loop()
        t = threading.Thread(target=pipeline.run, daemon=True)
        t.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        pipeline.shutdown()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/state")
    async def get_state() -> dict:
        return {"state": pipeline.state.value}

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        clients.append(ws)
        try:
            # Send current state immediately
            await ws.send_text(json.dumps({
                "state": pipeline.state.value,
                "pose": "idle",
                "person_present": False,
            }))
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            if ws in clients:
                clients.remove(ws)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


def run_dashboard(config: Config) -> None:
    import uvicorn
    app = create_app(config)
    uvicorn.run(
        app,
        host=config.dashboard.host,
        port=config.dashboard.port,
        log_level="info",
    )
