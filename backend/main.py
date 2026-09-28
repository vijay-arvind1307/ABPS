import os
import sys
import traceback

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/test-ping")
@app.get("/test-ping")
def test_ping():
    return {
        "status": "PONG",
        "message": "Vercel backend service is running successfully!",
        "python": sys.version,
        "cwd": os.getcwd()
    }

@app.get("/api/test-import-app")
@app.get("/test-import-app")
def test_import_app():
    try:
        from app.main import app as real_app
        return {
            "status": "SUCCESS",
            "message": "app.main imported cleanly with 0 errors!"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "IMPORT_FAILED",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
