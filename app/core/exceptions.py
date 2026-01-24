"""Custom exception classes and error handling."""

from typing import Any

from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(
            status_code=status_code,
            detail={
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                },
            },
        )


class AuthenticationError(AppException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_FAILED",
            message=message,
        )


class PermissionDeniedError(AppException):
    """Permission denied for the requested action."""

    def __init__(
        self,
        message: str = "Permission denied",
        required_permission: str | None = None,
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PERMISSION_DENIED",
            message=message,
            details=details,
        )


class ForbiddenError(AppException):
    """Forbidden action - user is not allowed to perform this action."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=message,
        )


class ProjectSuspendedError(AppException):
    """Project is suspended and mutations are blocked."""

    def __init__(self, project_id: str | None = None):
        details = {}
        if project_id:
            details["project_id"] = project_id
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PROJECT_SUSPENDED",
            message="Project is suspended. All mutations are blocked.",
            details=details,
        )


class ValidationError(AppException):
    """Data validation failed."""

    def __init__(
        self,
        message: str = "Validation error",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class UploadError(AppException):
    """File upload failed."""

    def __init__(
        self,
        message: str = "Upload failed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="UPLOAD_FAILED",
            message=message,
            details=details,
        )


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(
        self,
        resource: str = "Resource",
        identifier: str | None = None,
    ):
        details = {}
        if identifier:
            details["identifier"] = identifier
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"{resource} not found",
            details=details,
        )


class InternalError(AppException):
    """Internal server error."""

    def __init__(
        self,
        message: str = "Internal server error",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message=message,
            details=details,
        )
