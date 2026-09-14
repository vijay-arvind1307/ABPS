from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.seed_data import seed_database

router = APIRouter(prefix="/scenario", tags=["Operational Planning Infrastructure"])


@router.post("/load-corridor-scenario")
@router.post("/reset-and-seed")
def load_corridor_scenario(db: Session = Depends(get_db)):
    """
    Initializes clean master railway infrastructure with ZERO fake operational records.
    """
    seed_database(db)

    return {
        "status": "SUCCESS",
        "message": "Railway master infrastructure initialized with zero fake operational records."
    }

