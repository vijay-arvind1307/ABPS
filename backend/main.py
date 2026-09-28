import os
import sys

# Ensure backend directory is in sys.path so 'app' can always be imported regardless of current working directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app

# Export FastAPI instance for Vercel Serverless Function
__all__ = ["app"]
