"""Dashboard endpoints for role-based widgets."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_project_admin
from app.schemas.dashboard import (
    DashboardResponse,
    MyTasksReport,
    ProjectTaskStatsResponse,
    UserLevelStatsResponse,
)
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


@router.get("/my-tasks", response_model=MyTasksReport)
def get_my_tasks_report(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get the current user's task report.

    Returns overall and today's completion stats, status counts,
    and a list of pending/in-progress tasks for the collapsible view.
    Accessible by all authenticated users with project access.
    """
    service = DashboardService(db)
    return service.get_my_tasks_report(
        project_id=context.project_id,
        user_id=context.user_id,
    )


@router.get("/project-stats", response_model=ProjectTaskStatsResponse)
def get_project_task_stats(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get project-level task statistics.

    Returns aggregate counts, status distribution for charts,
    and the evo points leaderboard. Accessible by all project members.
    """
    service = DashboardService(db)
    return service.get_project_task_stats(
        project_id=context.project_id,
    )


@router.get(
    "/user-stats",
    response_model=UserLevelStatsResponse,
    dependencies=[Depends(require_project_admin())],
)
def get_user_level_stats(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get per-user task statistics (admin only).

    Returns aggregated stats across all users and per-user breakdowns
    including today's tasks, status counts, and pending task lists.
    Requires project admin or super admin access.
    """
    service = DashboardService(db)
    return service.get_user_level_stats(
        project_id=context.project_id,
    )
