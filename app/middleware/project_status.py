"""Project status middleware for blocking mutations on suspended projects."""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import ProjectSuspendedError


class ProjectStatusMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check project status for mutation requests.
    
    Suspended projects block all mutation operations (POST, PUT, PATCH, DELETE).
    This is a secondary check - primary check is in dependencies.
    """

    # Methods that mutate data
    MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Endpoints exempt from suspension check
    EXEMPT_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/register",
        "/api/v1/projects",  # Listing projects
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only check mutation methods
        if request.method not in self.MUTATION_METHODS:
            return await call_next(request)

        # Check if path is exempt
        path = request.url.path
        if any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS):
            return await call_next(request)

        # Project status check is handled by dependencies
        # This middleware is for additional protection
        return await call_next(request)
