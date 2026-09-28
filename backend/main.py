import os
import sys
import traceback
import json

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

_cached_app = None
_import_error = None

def get_app():
    global _cached_app, _import_error
    if _cached_app is not None:
        return _cached_app
    if _import_error is not None:
        return None
    try:
        from app.main import app as fastapi_app
        _cached_app = fastapi_app
        return _cached_app
    except Exception as e:
        _import_error = traceback.format_exc()
        print("ERROR LOADING APP.MAIN:\n", _import_error)
        return None

async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                get_app()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["type"] == "http":
        path = scope.get("path", "")
        if path in ("/api/test-ping", "/test-ping"):
            real = get_app()
            res_data = {
                "status": "PONG" if real else "APP_IMPORT_FAILED",
                "routes": len(real.routes) if real else 0,
                "error": _import_error,
                "python": sys.version,
                "cwd": os.getcwd()
            }
            body = json.dumps(res_data).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 200 if real else 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

    real_app = get_app()
    if real_app is not None:
        try:
            await real_app(scope, receive, send)
        except Exception as e:
            err_data = {
                "status": "APPLICATION_EXECUTION_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            body = json.dumps(err_data).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            })
            await send({"type": "http.response.body", "body": body})
    else:
        err_data = {
            "status": "FATAL_IMPORT_ERROR",
            "error": "Failed to import app.main on serverless runtime",
            "traceback": _import_error
        }
        body = json.dumps(err_data).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        })
        await send({"type": "http.response.body", "body": body})
