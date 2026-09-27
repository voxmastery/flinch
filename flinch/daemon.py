"""HTTP daemon receiving Claude Code hooks. Must never crash or hang Claude Code."""

import asyncio
import json
import logging
import os
import signal
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from flinch import __version__
from flinch.circuit import TextEmbedder
from flinch.decide import Engine, NoActionToBlame
from flinch.events import EventBus
from flinch.hooks import (
    PostToolUseFailureInput,
    PostToolUseInput,
    PreToolUseInput,
    SessionStartInput,
    UserPromptSubmitInput,
)
from flinch.locate import data_home
from flinch.registry import Registry
from flinch.scars import Scar

log = logging.getLogger("flinch")

UI_DIST = Path(__file__).parent / "ui" / "dist"
SSE_KEEPALIVE_S = 15
HOUSEKEEPING_S = 60
ENGINE_IDLE_S = 30 * 60

_ROUTES: dict[str, tuple[str, type[BaseModel], str]] = {
    "/hook/pre": ("PreToolUse", PreToolUseInput, "pre"),
    "/hook/post": ("PostToolUse", PostToolUseInput, "post"),
    "/hook/post-failure": ("PostToolUseFailure", PostToolUseFailureInput, "post_failure"),
    "/hook/prompt": ("UserPromptSubmit", UserPromptSubmitInput, "prompt"),
    "/hook/session-start": ("SessionStart", SessionStartInput, "session_start"),
}


class HurtRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    severity: float = 1.0
    session_id: str | None = None
    project: str | None = Field(default=None, max_length=4096)
    action: str | None = Field(default=None, max_length=4000)


class ResetRequest(BaseModel):
    project: str = Field(min_length=1, max_length=4096)


class ForgiveRequest(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    project: str | None = Field(default=None, max_length=4096)


def _record_error(where: str) -> None:
    try:
        d = data_home()
        d.mkdir(parents=True, exist_ok=True)
        with (d / "errors.log").open("a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {where}\n{traceback.format_exc()}\n")
    except Exception:
        log.exception("could not write error log")


def _scar_json(scar: Scar) -> dict[str, Any]:
    return {"fingerprint": scar.fingerprint, **scar.record()}


def _require_json(request: Request) -> None:
    # Forces a CORS preflight for browser-originated requests, which we never answer.
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(415, "application/json required")


def _fixed_home(home: Path | None) -> Path | None:
    if home:
        return home
    env = os.environ.get("FLINCH_HOME")
    return Path(env) if env else None


def create_app(home: Path | None = None, embedder: TextEmbedder | None = None,
               idle_exit_s: float | None = None) -> FastAPI:
    bus = EventBus()
    fixed = _fixed_home(home)
    registry = Registry(bus.publish, embedder=embedder, fixed_home=fixed)

    async def housekeeping() -> None:
        while True:
            await asyncio.sleep(HOUSEKEEPING_S)
            try:
                await run_in_threadpool(registry.evict_idle, ENGINE_IDLE_S)
                await run_in_threadpool(registry.unload_idle_model)
                if idle_exit_s and time.time() - registry.last_hook_at > idle_exit_s:
                    log.info("flinch: idle for %.0fs, exiting", idle_exit_s)
                    os.kill(os.getpid(), signal.SIGTERM)
            except Exception:
                _record_error("housekeeping")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = asyncio.create_task(housekeeping())
        yield
        task.cancel()
        registry.close_all()  # release the memory stores' locks

    app = FastAPI(title="flinch", version=__version__, docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    app.state.registry = registry
    app.state.bus = bus
    if fixed:
        app.state.engine = registry.for_cwd(str(fixed.parent))

    def engine_for(project: str | None) -> Engine:
        if project:
            return registry.for_cwd(project)
        engine = registry.active()
        if engine is None:
            raise HTTPException(409, "no active project yet; pass a project path")
        return engine

    async def dispatch(request: Request, event: str, model: type[BaseModel], method: str) -> Response:
        try:
            inp = model.model_validate(json.loads(await request.body()))

            def run() -> dict[str, Any] | None:  # engine does blocking I/O: keep it off the event loop
                engine = getattr(app.state, "engine", None) if fixed else None
                return getattr(engine or registry.for_cwd(inp.cwd), method)(inp)

            result = await run_in_threadpool(run)
            if result:
                return JSONResponse(result)
        except Exception:
            log.exception("hook %s failed", event)
            _record_error(event)
        return Response(status_code=200)

    for route, (event, model, method) in _ROUTES.items():
        async def endpoint(request: Request, _e=event, _m=model, _h=method) -> Response:
            return await dispatch(request, _e, _m, _h)

        app.add_api_route(route, endpoint, methods=["POST"], name=event)

    @app.get("/health")
    def health() -> dict[str, Any]:
        engine = registry.active()
        return {"ok": True, "version": __version__, "pid": os.getpid(),
                "project": engine.root if engine else None,
                "home": str(engine.home) if engine else None,
                "scars": len(engine.scars.all()) if engine else 0,
                "judgment": engine.judgment_status() if engine else None}

    @app.get("/api/scars")
    def list_scars(project: str | None = None) -> list[dict[str, Any]]:
        return [_scar_json(s) for s in engine_for(project).scars.all()]

    @app.post("/api/hurt", dependencies=[Depends(_require_json)])
    def hurt(body: HurtRequest) -> dict[str, Any]:
        engine = engine_for(body.project)
        try:
            return _scar_json(engine.hurt(body.reason, body.severity, body.session_id, action=body.action))
        except NoActionToBlame as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.post("/api/forgive", dependencies=[Depends(_require_json)])
    def forgive(body: ForgiveRequest) -> dict[str, Any]:
        scar = engine_for(body.project).forgive(body.id)
        if scar is None:
            raise HTTPException(404, f"no unique scar matches {body.id!r}")
        return _scar_json(scar)

    @app.post("/api/reset", dependencies=[Depends(_require_json)])
    def reset(body: ResetRequest) -> dict[str, Any]:
        home = registry.reset(body.project)
        if fixed:  # single-project mode keeps a direct engine reference
            app.state.engine = registry.for_cwd(body.project)
        bus.publish("forgive", {"ts": time.time(), "pain_id": "*", "action": "reset", "weights": [0.0] * 4000,
                                "project": Path(body.project).name})
        return {"reset": str(home)}

    @app.get("/api/state")
    def state(project: str | None = None) -> dict[str, Any]:
        engine = registry.for_cwd(project) if project else registry.active()
        if engine is None:
            return {"project": None, "thresholds": {"flinch": 0.55, "wary": 0.25}, "cells": 4000,
                    "grid": {"cols": 80, "rows": 50}, "weights": [0.0] * 4000, "scars": [], "decisions": [],
                    "judgment": "disabled"}
        cfg = engine.config
        return {
            "project": engine.name,
            "thresholds": {"flinch": cfg.flinch_threshold, "wary": cfg.wary_threshold},
            "cells": engine.circuit.params.cells, "grid": {"cols": 80, "rows": 50},
            "weights": engine.weights(),
            "scars": [_scar_json(s) for s in engine.scars.all()],
            "decisions": list(engine.decisions),
            "judgment": engine.judgment_status(),
        }

    @app.get("/events")
    async def events(request: Request) -> StreamingResponse:
        queue = bus.subscribe()

        async def stream():
            try:
                yield ": connected\n\n"
                while not await request.is_disconnected():
                    try:
                        yield await asyncio.wait_for(queue.get(), SSE_KEEPALIVE_S)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                bus.unsubscribe(queue)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    if UI_DIST.is_dir():
        app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")

    return app
