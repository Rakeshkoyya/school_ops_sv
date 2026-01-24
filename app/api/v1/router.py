"""Main API router aggregating all module routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    attendance,
    audit,
    auth,
    exams,
    notifications,
    projects,
    roles,
    students,
    tasks,
    uploads,
)

api_router = APIRouter()

# Authentication (no project context required)
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

# Projects (partial project context - user can list their projects)
api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["Projects"],
)

# RBAC - Roles and Permissions (project-scoped)
api_router.include_router(
    roles.router,
    prefix="/roles",
    tags=["Roles & Permissions"],
)

# Students (project-scoped)
api_router.include_router(
    students.router,
    prefix="/students",
    tags=["Students"],
)

# Tasks (project-scoped)
api_router.include_router(
    tasks.router,
    prefix="/tasks",
    tags=["Tasks"],
)

# Attendance (project-scoped)
api_router.include_router(
    attendance.router,
    prefix="/attendance",
    tags=["Attendance"],
)

# Exams (project-scoped)
api_router.include_router(
    exams.router,
    prefix="/exams",
    tags=["Exams"],
)

# Uploads (project-scoped)
api_router.include_router(
    uploads.router,
    prefix="/uploads",
    tags=["Uploads"],
)

# Audit Logs (project-scoped)
api_router.include_router(
    audit.router,
    prefix="/audit-logs",
    tags=["Audit Logs"],
)

# Notifications (project-scoped)
api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
)
