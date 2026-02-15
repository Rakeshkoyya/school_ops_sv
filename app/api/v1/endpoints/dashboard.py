"""Dashboard endpoints for role-based widgets."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import ProjectContext
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get dashboard data based on project's allocated menus and user permissions.
    
    Returns widgets dynamically based on:
    - Which features (menu screens) are allocated to the project
    - Which permissions the current user has
    
    Each widget section will only be included if the user has access to that feature.
    """
    service = DashboardService(db)
    return service.get_dashboard(
        project_id=context.project_id,
        user_id=context.user_id,
    )
