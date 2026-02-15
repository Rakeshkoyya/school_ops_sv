"""Database models package."""

from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.models.audit import AuditAction, AuditLog
from app.models.evo_point import EvoPointTransaction, EvoTransactionType
from app.models.exam import ExamRecord
from app.models.menu_screen import MenuScreen, MenuScreenPermission, ProjectMenuScreen
from app.models.notification import Notification
from app.models.project import Project, ProjectStatus
from app.models.rbac import Permission, Role, RolePermission, UserRoleProject
from app.models.student import Student
from app.models.task import EvoReductionType, RecurrenceType, RecurringTaskTemplate, Task, TaskCategory, TaskStatus
from app.models.task_view import TaskViewStyle, UserTaskViewPreference, TASK_COLUMNS, get_default_column_config
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
    "RecurringTaskTemplate",
    "RecurrenceType",
    "EvoReductionType",
    # Evo Points
    "EvoPointTransaction",
    "EvoTransactionType",
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
    # Task View
    "TaskViewStyle",
    "UserTaskViewPreference",
    "TASK_COLUMNS",
    "get_default_column_config",
    # Menu Screens
    "MenuScreen",
    "MenuScreenPermission",
    "ProjectMenuScreen",
]
