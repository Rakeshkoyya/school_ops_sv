"""Dashboard schemas for role-based widgets."""

from datetime import date
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
