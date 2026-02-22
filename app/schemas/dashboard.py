"""Dashboard schemas for role-based widgets."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import BaseSchema


# ==========================================
# Task Dashboard Stats
# ==========================================

class TaskStatusCount(BaseSchema):
    """Count of tasks by status."""

    pending: int = 0
    in_progress: int = 0
    done: int = 0
    overdue: int = 0
    cancelled: int = 0


class TaskDashboardStats(BaseSchema):
    """Task statistics for dashboard widget."""

    total_tasks: int = 0
    status_counts: TaskStatusCount
    completed_today: int = 0
    due_today: int = 0
    completion_rate: float = Field(
        default=0.0,
        description="Percentage of completed tasks (0-100)"
    )


# ==========================================
# Attendance Dashboard Stats
# ==========================================

class AttendanceDashboardStats(BaseSchema):
    """Attendance statistics for dashboard widget."""

    date: date
    total_students: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    present_rate: float = Field(
        default=0.0,
        description="Percentage of present students (0-100)"
    )
    attendance_captured: bool = Field(
        default=False,
        description="Whether attendance has been captured for today"
    )


class AttendanceByClassStat(BaseSchema):
    """Attendance stats per class for dashboard."""

    class_section: str
    total_students: int
    present_count: int
    present_rate: float


# ==========================================
# Exam Dashboard Stats
# ==========================================

class ExamDashboardStats(BaseSchema):
    """Exam statistics for dashboard widget."""

    recent_exam_name: str | None = None
    recent_exam_subject: str | None = None
    recent_exam_date: date | None = None
    total_students: int = 0
    average_marks: Decimal | None = None
    pass_rate: float = Field(
        default=0.0,
        description="Percentage of students who passed (0-100)"
    )
    highest_marks: Decimal | None = None
    lowest_marks: Decimal | None = None


# ==========================================
# Student Dashboard Stats
# ==========================================

class ClassStudentCount(BaseSchema):
    """Student count per class."""

    class_section: str
    student_count: int


class StudentDashboardStats(BaseSchema):
    """Student statistics for dashboard widget."""

    total_students: int = 0
    class_count: int = 0
    by_class: list[ClassStudentCount] = []


# ==========================================
# Evo Points Dashboard
# ==========================================

class EvoLeaderboardEntry(BaseSchema):
    """Entry in dashboard leaderboard."""

    rank: int
    user_id: int
    user_name: str
    points: int


class EvoDashboardStats(BaseSchema):
    """Evo points stats for dashboard."""

    current_user_balance: int = 0
    current_user_rank: int | None = None
    leaderboard: list[EvoLeaderboardEntry] = []


# ==========================================
# Combined Dashboard Response
# ==========================================

class DashboardWidgetConfig(BaseSchema):
    """Configuration for which widgets to show."""

    show_tasks: bool = False
    show_attendance: bool = False
    show_exams: bool = False
    show_students: bool = False
    show_evo_points: bool = False


class DashboardResponse(BaseSchema):
    """Combined dashboard response with all available stats."""

    widget_config: DashboardWidgetConfig
    tasks: TaskDashboardStats | None = None
    attendance: AttendanceDashboardStats | None = None
    attendance_by_class: list[AttendanceByClassStat] | None = None
    exams: ExamDashboardStats | None = None
    students: StudentDashboardStats | None = None
    evo_points: EvoDashboardStats | None = None


# ==========================================
# My Tasks Report (Section 1 — all users)
# ==========================================

class TaskListItem(BaseSchema):
    """Lightweight task reference for collapsible lists."""

    id: int
    title: str
    due_datetime: datetime | None = None
    status: str


class MyTasksReport(BaseSchema):
    """My tasks report data for dashboard Section 1."""

    total_active: int = Field(
        default=0,
        description="Total active tasks (pending + in_progress + done)",
    )
    total_completed: int = Field(
        default=0,
        description="Completed (done) tasks count",
    )
    today_total: int = Field(
        default=0,
        description="Tasks due today",
    )
    today_completed: int = Field(
        default=0,
        description="Today's tasks that are done",
    )
    pending_count: int = 0
    in_progress_count: int = 0
    completed_count: int = 0
    overdue_count: int = 0
    pending_tasks: list[TaskListItem] = Field(
        default=[],
        description="Pending and in-progress tasks for collapsible list",
    )


# ==========================================
# Project Task Stats (Section 2 — all users)
# ==========================================

class ProjectTaskStatsResponse(BaseSchema):
    """Project-level task statistics for dashboard Section 2."""

    pending_count: int = 0
    in_progress_count: int = 0
    overdue_count: int = 0
    completed_count: int = 0
    active_tasks: int = Field(
        default=0,
        description="Count of pending + in_progress tasks",
    )
    total_tasks: int = 0
    status_distribution: TaskStatusCount = Field(
        default_factory=TaskStatusCount,
    )
    evo_leaderboard: list[EvoLeaderboardEntry] = []


# ==========================================
# User Level Stats (Section 3 — admin only)
# ==========================================

class UserDailyTaskRow(BaseSchema):
    """Per-user task row for admin dashboard Section 3."""

    user_id: int
    user_name: str
    today_total: int = 0
    today_completed: int = 0
    completion_percentage: float = Field(
        default=0.0,
        description="Percentage of today's tasks completed (0-100)",
    )
    pending_count: int = 0
    in_progress_count: int = 0
    completed_count: int = 0
    overdue_count: int = 0
    pending_tasks: list[TaskListItem] = Field(
        default=[],
        description="Pending tasks due today for collapsible list",
    )


class UserLevelStatsResponse(BaseSchema):
    """User-level task statistics for admin dashboard Section 3."""

    today_total: int = Field(
        default=0,
        description="Total tasks due today across all users",
    )
    today_completed: int = Field(
        default=0,
        description="Completed today's tasks across all users",
    )
    overall_total: int = Field(
        default=0,
        description="Total non-closed tasks across all users",
    )
    overall_completed: int = Field(
        default=0,
        description="Completed tasks across all users",
    )
    user_rows: list[UserDailyTaskRow] = []
