"""Database models package."""

from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.models.audit import AuditAction, AuditLog
from app.models.exam import ExamRecord
from app.models.notification import Notification
from app.models.project import Project, ProjectStatus
from app.models.rbac import Permission, Role, RolePermission, UserRoleProject
from app.models.student import Student
from app.models.task import Task, TaskCategory, TaskStatus
from app.models.upload import Upload, UploadError, UploadStatus, UploadType
from app.models.user import User

__all__ = [
    # User
    "User",
    # Project
    "Project",
    "ProjectStatus",
    # RBAC
    "Role",
    "Permission",
    "RolePermission",
    "UserRoleProject",
    # Student
    "Student",
    # Task
    "Task",
    "TaskCategory",
    "TaskStatus",
    # Attendance
    "AttendanceRecord",
    "AttendanceStatus",
    # Exam
    "ExamRecord",
    # Upload
    "Upload",
    "UploadError",
    "UploadStatus",
    "UploadType",
    # Audit
    "AuditLog",
    "AuditAction",
    # Notification
    "Notification",
]
