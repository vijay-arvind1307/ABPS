import os
import sys
import traceback

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from app.main import app
    print("Successfully imported app.main FastAPI app.")
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    err_tb = traceback.format_exc()
    print("FATAL: Failed to import app.main:", err_tb)
    app = FastAPI(title="Fallback Error Handler")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    def fallback(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "status": "FATAL_IMPORT_ERROR",
                "error": str(e),
                "traceback": err_tb
            }
        )

# Ensure ping/health endpoints are always reachable
@app.get("/api/test-ping")
@app.get("/test-ping")
def test_ping():
    return {
        "status": "PONG",
        "message": "Vercel backend service is running successfully!",
        "python": sys.version,
        "routes": len(app.routes)
    }

@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "routes": len(app.routes)
    }

