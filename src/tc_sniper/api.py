from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from tc_sniper.models import DiscoverCourseRequest, LoginStartRequest, SessionStatus, WatchRunState, WatchStartRequest
from tc_sniper.services import AppServices
from tc_sniper.settings import read_recent_event_items


services = AppServices()
app = FastAPI(title="tc-sniper local API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:1420",
        "http://localhost:1420",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/session/status", response_model=SessionStatus)
def session_status(revalidate: bool = Query(False)) -> SessionStatus:
    return services.session.get_status(revalidate=revalidate)


@app.post("/session/login/start")
def start_login(request: LoginStartRequest) -> dict:
    try:
        state = services.login_flow.start(request.host)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return state.model_dump(mode="json")


@app.post("/session/login/confirm")
def confirm_login() -> dict:
    try:
        state = services.login_flow.confirm()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return state.model_dump(mode="json")


@app.post("/session/logout", response_model=SessionStatus)
def logout() -> SessionStatus:
    return services.session.logout()


@app.post("/courses/discover")
def discover_course(request: DiscoverCourseRequest) -> dict:
    try:
        course = services.courses.discover(request.tcb_url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return course.model_dump(mode="json")


@app.get("/watch/status", response_model=WatchRunState)
def watch_status() -> WatchRunState:
    return services.watch.get_state()


@app.post("/watch/start", response_model=WatchRunState)
def watch_start(request: WatchStartRequest) -> WatchRunState:
    try:
        return services.watch.start(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/watch/stop", response_model=WatchRunState)
def watch_stop() -> WatchRunState:
    return services.watch.stop()


@app.get("/events/recent")
def recent_events(limit: int = Query(20, ge=1, le=200)) -> dict[str, list[dict]]:
    return {"items": [item.model_dump(mode="json") for item in read_recent_event_items(limit)]}


@app.get("/watch/events")
async def watch_events() -> StreamingResponse:
    event_queue, unsubscribe = services.watch.subscribe()

    async def stream() -> AsyncIterator[str]:
        initial = services.watch.get_state()
        yield f"data: {json.dumps({'type': 'state', 'payload': initial.model_dump(mode='json')})}\n\n"
        try:
            while True:
                event = await asyncio.to_thread(event_queue.get)
                yield f"data: {json.dumps({'type': 'log', 'payload': event.model_dump(mode='json')})}\n\n"
        finally:
            unsubscribe()

    return StreamingResponse(stream(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    uvicorn.run("tc_sniper.api:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
