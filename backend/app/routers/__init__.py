from app.routers.auth import router as auth_router
from app.routers.maintenance import router as maintenance_router
from app.routers.railway import router as railway_router
from app.routers.planning import router as planning_router
from app.routers.dynamic import router as dynamic_router
from app.routers.whatif import router as whatif_router
from app.routers.reports import router as reports_router
from app.routers.scenario import router as scenario_router
from app.routers.stations import router as stations_router
from app.routers.trains import router as trains_router
from app.routers.execution import router as execution_router
from app.routers.block_requests import router as block_requests_router, coordinated_router as coordinated_block_plans_router
from app.routers.notifications import router as notifications_router
from app.routers.live import router as live_router
from app.routers.availability import router as availability_router
from app.routers.standard_api import router as standard_api_router

