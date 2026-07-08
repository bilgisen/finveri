import asyncio
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

_refreshed = False


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        global _refreshed
        try:
            from app.core.d1 import set_db
            set_db(self.env.DB)

            from app.core.workers_cache import init_cache, load_initial
            await init_cache(self.env.KV)
            await load_initial()

            if not _refreshed:
                try:
                    from app.worker.workers_refresh import refresh_all
                    await refresh_all()
                    _refreshed = True
                except Exception as e:
                    logger.warning("initial refresh failed: %s", e)

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
            return Response(bytes(resp_body), status=resp_status or 500,
                          headers={k.decode(): v.decode() for k, v in (resp_headers or [])})
        except Exception as e:
            import traceback
            return Response(f"Error: {e}\n{traceback.format_exc()}", status=500, headers={"Content-Type": "text/plain"})

    async def _flush(self):
        try:
            from app.core.workers_cache import flush_pending
            await flush_pending()
        except Exception:
            pass
