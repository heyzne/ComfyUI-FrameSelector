"""HTTP routes + in-memory session registry used by the FrameSelector node.

The selector node blocks the prompt-worker thread on a threading.Event.
The frontend opens a dialog, fetches JPEG previews through the routes below
and releases the event via /frame_selector/select or /frame_selector/cancel.
"""

import threading

from aiohttp import web
from server import PromptServer

CANCEL = "__cancel__"


class _Session:
    def __init__(self):
        self.event = threading.Event()
        self.previews = []      # list[bytes] JPEG previews, one per frame
        self.count = 0
        self.ready = False
        self.result = None      # list[int] | CANCEL


_SESSIONS = {}
_LOCK = threading.Lock()


def begin_session(node_id):
    with _LOCK:
        s = _Session()
        _SESSIONS[str(node_id)] = s
        return s


def end_session(node_id):
    with _LOCK:
        _SESSIONS.pop(str(node_id), None)


def get_session(node_id):
    with _LOCK:
        return _SESSIONS.get(str(node_id))


if PromptServer.instance is not None:
    routes = PromptServer.instance.routes

    @routes.get("/frame_selector/status")
    async def fs_status(request):
        s = get_session(request.query.get("node_id", ""))
        ready = bool(s and s.ready)
        return web.json_response({"ready": ready, "count": s.count if ready else 0})

    @routes.get("/frame_selector/img")
    async def fs_img(request):
        s = get_session(request.query.get("node_id", ""))
        try:
            i = int(request.query.get("i", "-1"))
        except ValueError:
            i = -1
        if not s or not (0 <= i < len(s.previews)):
            return web.Response(status=404)
        return web.Response(
            body=s.previews[i],
            content_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @routes.post("/frame_selector/select")
    async def fs_select(request):
        data = await request.json()
        s = get_session(data.get("node_id", ""))
        if not s or not s.ready:
            return web.json_response({"ok": False, "error": "no active session"})
        try:
            s.result = [int(i) for i in data.get("indices", [])]
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "bad indices"})
        s.event.set()
        return web.json_response({"ok": True})

    @routes.post("/frame_selector/cancel")
    async def fs_cancel(request):
        data = await request.json()
        s = get_session(data.get("node_id", ""))
        if s is not None:
            s.result = CANCEL
            s.event.set()
        return web.json_response({"ok": True})