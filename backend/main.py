import os
import sys
import traceback

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import_error = None
try:
    from app.main import app
except Exception as e:
    import_error = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()

    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
    def catch_all(path_name: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "FastAPI App Import Failed on Vercel",
                "detail": str(e),
                "traceback": import_error,
                "sys_path": sys.path,
                "cwd": os.getcwd(),
                "files": os.listdir(".") if os.path.exists(".") else []
            }
        )

@app.get("/api/test-debug")
def test_debug():
    return {
        "status": "OK",
        "python": sys.version,
        "cwd": os.getcwd(),
        "backend_dir": backend_dir,
        "import_error": import_error
    }

# Also ensure backend/api/index.py has identical capability
__all__ = ["app"]
