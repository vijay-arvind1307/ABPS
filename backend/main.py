import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

app = FastAPI(
    title="Railway Maintenance Block Planning API (IR-ABPS)",
    description="AI-Assisted Maintenance Block Planning and Constraint Optimization Platform for Indian Railways",
    version="1.0.0"
)

# Robust CORS Setup
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_import_error = None
_real_app = None

# Ping and diagnostic endpoints
@app.get("/api/test-ping")
@app.get("/test-ping")
def test_ping():
    return {
        "status": "PONG",
        "has_real_app": _real_app is not None,
        "total_routes": len(app.router.routes),
        "import_error": _import_error,
        "python": sys.version,
        "cwd": os.getcwd()
    }

try:
    from app.main import app as _real_app
    existing = {(r.path, tuple(sorted(getattr(r, "methods", None) or []))) for r in app.router.routes}
    for r in _real_app.router.routes:
        k = (r.path, tuple(sorted(getattr(r, "methods", None) or [])))
        if k not in existing:
            app.router.routes.append(r)
            existing.add(k)
    print(f"[INIT] Successfully registered {len(app.router.routes)} routes from app.main.")
except Exception as e:
    _import_error = traceback.format_exc()
    print("[INIT FATAL] Error importing app.main:\n", _import_error)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    def import_error_fallback(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "status": "BACKEND_INITIALIZATION_ERROR",
                "message": "FastAPI failed to import backend modules on Vercel serverless runtime.",
                "traceback": _import_error
            }
        )
