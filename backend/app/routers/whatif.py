from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import WhatIfRequest
from app.services.whatif_service import WhatIfService
from app.routers.auth import get_current_user, require_role

router = APIRouter(prefix="/whatif", tags=["What-If Scenario Simulation"])


@router.post("/simulate")
def simulate_whatif(
    req: WhatIfRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """
    Runs sandboxed What-If simulation with specified perturbation factors and returns side-by-side KPI deltas.
    """
    return WhatIfService.simulate_scenario(db, req, current_user)
