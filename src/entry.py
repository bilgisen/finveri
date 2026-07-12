import asyncio
import hashlib
import json as _json
import logging
import starlette.concurrency
from urllib.parse import urlparse

logger = logging.getLogger("entry")
from workers import WorkerEntrypoint
from workers.response import Response


async def _run_sync_inline(func, *args, **kwargs):
    return func(*args, **kwargs)

starlette.concurrency.run_in_threadpool = _run_sync_inline


ASGI_SPEC = {"spec_version": "2.0", "version": "3.0"}




def _compute_etag(data: dict) -> str:
    raw = _json.dumps(data, sort_keys=True, ensure_ascii=False)
    return '"' + hashlib.sha256(raw.encode()).hexdigest()[:16] + '"'


def _is_market_open() -> bool:
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=3))
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 17


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        try:
            from app.core.d1 import set_db
            set_db(self.env.DB)

            from app.core.workers_cache import init_cache, load_initial
            await init_cache(self.env.KV)
            await load_initial()

            from app.main import create_app
            app = create_app()

            req = request.js_object
            parsed = urlparse(req.url)
            scope = {
                "asgi": ASGI_SPEC,
                "type": "http",
                "method": req.method,
                "path": parsed.path or "/",
                "query_string": parsed.query.encode(),
                "headers": [(k.lower().encode(), v.encode()) for k, v in req.headers.entries()],
                "http_version": "1.1",
                "scheme": parsed.scheme,
            }

            resp_status = None
            resp_headers = None
            resp_body = bytearray()
            responded = False

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(msg):
                nonlocal resp_status, resp_headers, resp_body, responded
                if msg["type"] == "http.response.start":
                    resp_status = msg["status"]
                    resp_headers = msg["headers"]
                elif msg["type"] == "http.response.body":
                    resp_body.extend(msg["body"])
                    if not msg.get("more_body", False):
                        responded = True

            try:
                await app(scope, receive, send)
            except Exception:
                if not responded:
                    import traceback
                    return Response(traceback.format_exc(), status=500, headers={"Content-Type": "text/plain"})

            await self._flush()

            headers = {k.decode(): v.decode() for k, v in (resp_headers or [])}

            # ETag and 304 support for GET JSON responses
            is_304 = False
            if req.method == "GET" and resp_status and resp_status < 400 and resp_body:
                content_type = headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        body_data = _json.loads(bytes(resp_body))
                        if isinstance(body_data, dict):
                            etag = _compute_etag(body_data)
                            if_none_match = req.headers.get("if-none-match")
                            if if_none_match and if_none_match == etag:
                                is_304 = True
                                headers["ETag"] = etag
                            else:
                                headers["ETag"] = etag
                    except (_json.JSONDecodeError, TypeError, ValueError):
                        pass

            if is_304:
                return Response(None, status=304, headers=headers)
            return Response(bytes(resp_body), status=resp_status or 500, headers=headers)
        except Exception as e:
            import traceback
            return Response(f"Error: {e}\n{traceback.format_exc()}", status=500, headers={"Content-Type": "text/plain"})

    async def _flush(self):
        try:
            from app.core.workers_cache import flush_pending
            await flush_pending()
        except Exception:
            pass
