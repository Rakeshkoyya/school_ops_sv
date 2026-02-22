"""Dashboard service for role-based widgets."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Integer, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.models.exam import ExamRecord
from app.models.menu_screen import MenuScreen, ProjectMenuScreen
from app.models.project import Project
from app.models.rbac import Permission, RolePermission, UserRoleProject
from app.models.student import Student
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.schemas.dashboard import (
    AttendanceByClassStat,
    AttendanceDashboardStats,
    ClassStudentCount,
    DashboardResponse,
    DashboardWidgetConfig,
    EvoDashboardStats,
    EvoLeaderboardEntry,
    ExamDashboardStats,
    MyTasksReport,
    ProjectTaskStatsResponse,
    StudentDashboardStats,
    TaskDashboardStats,
    TaskListItem,
    TaskStatusCount,
    UserDailyTaskRow,
    UserLevelStatsResponse,
)

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


class DashboardService:
    """Dashboard data aggregation service."""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard(
        self,
        project_id: int,
        user_id: int,
    ) -> DashboardResponse:
        """
        Get dashboard data based on project's allocated menus and user permissions.
        
        This dynamically determines which widgets to show based on:
        1. Which menus are allocated to the project
        2. Which permissions the user has
        """
        # Get widget configuration based on allocated menus and user permissions
        widget_config = self._get_widget_config(project_id, user_id)
        
        # Build response with only relevant data
        response = DashboardResponse(widget_config=widget_config)
        
        if widget_config.show_tasks:
            response.tasks = self._get_task_stats(project_id, user_id)
        
        if widget_config.show_attendance:
            today = date.today()
            response.attendance = self._get_attendance_stats(project_id, today)
            response.attendance_by_class = self._get_attendance_by_class(project_id, today)
        
        if widget_config.show_exams:
            response.exams = self._get_exam_stats(project_id)
        
        if widget_config.show_students:
            response.students = self._get_student_stats(project_id)
        
        if widget_config.show_evo_points:
            response.evo_points = self._get_evo_stats(project_id, user_id)
        
        return response

    def _get_widget_config(
        self,
        project_id: int,
        user_id: int,
    ) -> DashboardWidgetConfig:
        """Determine which widgets to show based on menu allocations and permissions."""
        # Get allocated menu names for the project
        allocated_menus = self._get_allocated_menu_names(project_id)
        
        # Get user's permission keys for this project
        user_permissions = self._get_user_permissions(project_id, user_id)
        
        return DashboardWidgetConfig(
            show_tasks="Tasks" in allocated_menus and "task:view" in user_permissions,
            show_attendance="Attendance" in allocated_menus and "attendance:view" in user_permissions,
            show_exams="Exams" in allocated_menus and "exam:view" in user_permissions,
            show_students="Students" in allocated_menus and "student:view" in user_permissions,
            # Evo points is tied to Tasks
            show_evo_points="Tasks" in allocated_menus and "task:view" in user_permissions,
        )

    def _get_allocated_menu_names(self, project_id: int) -> set[str]:
        """Get set of allocated menu names for a project."""
        result = self.db.execute(
            select(MenuScreen.name)
            .join(ProjectMenuScreen, ProjectMenuScreen.menu_screen_id == MenuScreen.id)
            .where(ProjectMenuScreen.project_id == project_id)
        )
        return {row[0] for row in result.all()}

    def _get_user_permissions(self, project_id: int, user_id: int) -> set[str]:
        """Get user's permission keys for a project."""
        # First check if user is super admin (has all permissions)
        user = self.db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        if user and user.is_super_admin:
            # Return all permission keys
            result = self.db.execute(select(Permission.permission_key))
            return {row[0] for row in result.all()}
        
        # Get permissions through user's roles in this project
        result = self.db.execute(
            select(Permission.permission_key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRoleProject, UserRoleProject.role_id == RolePermission.role_id)
            .where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.project_id == project_id,
            )
        )
        return {row[0] for row in result.all()}

    def _get_task_stats(
        self,
        project_id: int,
        user_id: int,
    ) -> TaskDashboardStats:
        """Get task statistics for dashboard."""
        now = datetime.now(IST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get all tasks for the project
        query = select(Task).where(Task.project_id == project_id)
        result = self.db.execute(query)
        tasks = result.scalars().all()
        
        # Count by status
        pending = 0
        in_progress = 0
        done = 0
        overdue = 0
        cancelled = 0
        completed_today = 0
        due_today = 0
        
        for task in tasks:
            if task.status == TaskStatus.PENDING:
                pending += 1
            elif task.status == TaskStatus.IN_PROGRESS:
                in_progress += 1
            elif task.status == TaskStatus.DONE:
                done += 1
                # Check if completed today
                if task.end_time and task.end_time >= today_start:
                    completed_today += 1
            elif task.status == TaskStatus.CANCELLED:
                cancelled += 1
            
            # Check overdue (pending/in_progress tasks past due)
            if task.due_datetime and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                if task.due_datetime < now:
                    overdue += 1
            
            # Check due today
            if task.due_datetime:
                task_due_date = task.due_datetime.date() if task.due_datetime.tzinfo else task.due_datetime.date()
                if task_due_date == now.date():
                    due_today += 1
        
        total = len(tasks)
        completion_rate = (done / total * 100) if total > 0 else 0.0
        
        return TaskDashboardStats(
            total_tasks=total,
            status_counts=TaskStatusCount(
                pending=pending,
                in_progress=in_progress,
                done=done,
                overdue=overdue,
                cancelled=cancelled,
            ),
            completed_today=completed_today,
            due_today=due_today,
            completion_rate=round(completion_rate, 1),
        )

    def _get_attendance_stats(
        self,
        project_id: int,
        target_date: date,
    ) -> AttendanceDashboardStats:
        """Get attendance statistics for a specific date."""
        # Get total students in project
        total_students_result = self.db.execute(
            select(func.count()).where(Student.project_id == project_id)
        )
        total_students = total_students_result.scalar() or 0
        
        # Get attendance counts for the date
        query = select(
            func.count().label("total"),
            func.sum(func.cast(AttendanceRecord.status == AttendanceStatus.PRESENT, Integer)).label("present"),
            func.sum(func.cast(AttendanceRecord.status == AttendanceStatus.ABSENT, Integer)).label("absent"),
            func.sum(func.cast(AttendanceRecord.status == AttendanceStatus.LATE, Integer)).label("late"),
            func.sum(func.cast(AttendanceRecord.status == AttendanceStatus.EXCUSED, Integer)).label("excused"),
        ).where(
            AttendanceRecord.project_id == project_id,
            AttendanceRecord.attendance_date == target_date,
        )
        
        result = self.db.execute(query)
        row = result.one()
        
        total_records = row.total or 0
        present_count = row.present or 0
        absent_count = row.absent or 0
        late_count = row.late or 0
        excused_count = row.excused or 0
        
        # Calculate present rate (including late as present for rate calculation)
        attendance_captured = total_records > 0
        present_rate = 0.0
        if total_records > 0:
            present_rate = ((present_count + late_count) / total_records) * 100
        
        return AttendanceDashboardStats(
            date=target_date,
            total_students=total_students,
            present_count=present_count,
            absent_count=absent_count,
            late_count=late_count,
            excused_count=excused_count,
            present_rate=round(present_rate, 1),
            attendance_captured=attendance_captured,
        )

    def _get_attendance_by_class(
        self,
        project_id: int,
        target_date: date,
    ) -> list[AttendanceByClassStat]:
        """Get attendance stats per class for a specific date."""
        # Get all class-sections with student counts
        class_query = select(
            Student.class_name,
            Student.section,
            func.count().label("total"),
        ).where(
            Student.project_id == project_id
        ).group_by(
            Student.class_name,
            Student.section,
        ).order_by(
            Student.class_name,
            Student.section,
        )
        
        class_result = self.db.execute(class_query)
        classes = class_result.all()
        
        stats = []
        for class_row in classes:
            class_name = class_row.class_name
            section = class_row.section or ""
            class_section = f"{class_name}-{section}" if section else class_name
            total_students = class_row.total
            
            # Get present count for this class on this date
            present_query = select(func.count()).where(
                AttendanceRecord.project_id == project_id,
                AttendanceRecord.attendance_date == target_date,
                AttendanceRecord.class_name == class_name,
                or_(
                    AttendanceRecord.status == AttendanceStatus.PRESENT,
                    AttendanceRecord.status == AttendanceStatus.LATE,
                ),
            )
            if section:
                present_query = present_query.where(AttendanceRecord.section == section)
            
            present_result = self.db.execute(present_query)
            present_count = present_result.scalar() or 0
            
            present_rate = (present_count / total_students * 100) if total_students > 0 else 0.0
            
            stats.append(AttendanceByClassStat(
                class_section=class_section,
                total_students=total_students,
                present_count=present_count,
                present_rate=round(present_rate, 1),
            ))
        
        return stats

    def _get_exam_stats(self, project_id: int) -> ExamDashboardStats:
        """Get latest exam statistics."""
        # Find the most recent exam
        latest_exam_query = select(
            ExamRecord.exam_name,
            ExamRecord.subject,
            ExamRecord.exam_date,
        ).where(
            ExamRecord.project_id == project_id
        ).order_by(
            ExamRecord.exam_date.desc(),
            ExamRecord.created_at.desc(),
        ).limit(1)
        
        latest = self.db.execute(latest_exam_query).first()
        
        if not latest:
            return ExamDashboardStats()
        
        exam_name = latest.exam_name
        subject = latest.subject
        exam_date = latest.exam_date
        
        # Get statistics for this exam
        stats_query = select(
            func.count().label("total"),
            func.avg(ExamRecord.marks_obtained).label("avg"),
            func.max(ExamRecord.marks_obtained).label("highest"),
            func.min(ExamRecord.marks_obtained).label("lowest"),
        ).where(
            ExamRecord.project_id == project_id,
            ExamRecord.exam_name == exam_name,
            ExamRecord.subject == subject,
            ExamRecord.exam_date == exam_date,
        )
        
        result = self.db.execute(stats_query)
        row = result.one()
        
        total_students = row.total or 0
        
        # Count pass (40% of max marks)
        pass_percentage = Decimal("0.4")
        pass_query = select(func.count()).where(
            ExamRecord.project_id == project_id,
            ExamRecord.exam_name == exam_name,
            ExamRecord.subject == subject,
            ExamRecord.exam_date == exam_date,
            ExamRecord.marks_obtained >= ExamRecord.max_marks * pass_percentage,
        )
        pass_count = self.db.execute(pass_query).scalar() or 0
        
        pass_rate = (pass_count / total_students * 100) if total_students > 0 else 0.0
        
        return ExamDashboardStats(
            recent_exam_name=exam_name,
            recent_exam_subject=subject,
            recent_exam_date=exam_date,
            total_students=total_students,
            average_marks=Decimal(str(row.avg or 0)).quantize(Decimal("0.01")) if row.avg else None,
            pass_rate=round(pass_rate, 1),
            highest_marks=row.highest,
            lowest_marks=row.lowest,
        )

    def _get_student_stats(self, project_id: int) -> StudentDashboardStats:
        """Get student statistics."""
        # Get total count
        total_query = select(func.count()).where(Student.project_id == project_id)
        total_students = self.db.execute(total_query).scalar() or 0
        
        # Get count by class
        class_query = select(
            Student.class_name,
            Student.section,
            func.count().label("count"),
        ).where(
            Student.project_id == project_id
        ).group_by(
            Student.class_name,
            Student.section,
        ).order_by(
            Student.class_name,
            Student.section,
        )
        
        result = self.db.execute(class_query)
        classes = result.all()
        
        by_class = []
        for row in classes:
            class_section = f"{row.class_name}-{row.section}" if row.section else row.class_name
            by_class.append(ClassStudentCount(
                class_section=class_section,
                student_count=row.count,
            ))
        
        return StudentDashboardStats(
            total_students=total_students,
            class_count=len(by_class),
            by_class=by_class,
        )

    def _get_evo_stats(
        self,
        project_id: int,
        user_id: int,
    ) -> EvoDashboardStats:
        """Get evo points statistics for dashboard."""
        # Get current user's balance
        user = self.db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        current_balance = user.evo_points if user else 0
        
        # Get top 5 users by evo points
        # Only consider users who are part of this project
        leaderboard_query = (
            select(User)
            .join(UserRoleProject, UserRoleProject.user_id == User.id)
            .where(
                User.is_active == True,
                UserRoleProject.project_id == project_id,
            )
            .distinct()
            .order_by(User.evo_points.desc())
            .limit(5)
        )
        
        result = self.db.execute(leaderboard_query)
        users = result.scalars().all()
        
        leaderboard = [
            EvoLeaderboardEntry(
                rank=idx + 1,
                user_id=u.id,
                user_name=u.name,
                points=u.evo_points,
            )
            for idx, u in enumerate(users)
        ]
        
        # Calculate current user's rank within the project
        current_user_rank = None
        if user:
            rank_query = select(func.count()).where(
                User.is_active == True,
                User.id.in_(
                    select(UserRoleProject.user_id).where(
                        UserRoleProject.project_id == project_id
                    )
                ),
                User.evo_points > current_balance,
            )
            users_above = self.db.execute(rank_query).scalar() or 0
            current_user_rank = users_above + 1
        
        return EvoDashboardStats(
            current_user_balance=current_balance,
            current_user_rank=current_user_rank,
            leaderboard=leaderboard,
        )

    # ==========================================================
    # New dashboard sections
    # ==========================================================

    def get_my_tasks_report(
        self,
        project_id: int,
        user_id: int,
    ) -> MyTasksReport:
        """Get current user's task report (Section 1)."""
        now = datetime.now(IST)
        today_date = now.date()

        # Fetch tasks assigned to this user in this project
        query = select(Task).where(
            Task.project_id == project_id,
            Task.assigned_to_user_id == user_id,
        )
        tasks = list(self.db.execute(query).scalars().all())

        pending = 0
        in_progress = 0
        completed = 0
        overdue = 0
        today_total = 0
        today_completed = 0
        pending_task_items: list[TaskListItem] = []

        for task in tasks:
            # Skip cancelled
            if task.status == TaskStatus.CANCELLED:
                continue

            if task.status == TaskStatus.PENDING:
                pending += 1
            elif task.status == TaskStatus.IN_PROGRESS:
                in_progress += 1
            elif task.status == TaskStatus.DONE:
                completed += 1

            # Check overdue (pending/in_progress past due)
            is_overdue = False
            if task.due_datetime and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                if task.due_datetime < now:
                    overdue += 1
                    is_overdue = True

            # Due today
            if task.due_datetime:
                task_due_date = task.due_datetime.date()
                if task_due_date == today_date:
                    today_total += 1
                    if task.status == TaskStatus.DONE:
                        today_completed += 1

            # Pending/in-progress tasks for the collapsible list
            if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                pending_task_items.append(TaskListItem(
                    id=task.id,
                    title=task.title,
                    due_datetime=task.due_datetime,
                    status="overdue" if is_overdue else task.status.value,
                ))

        # Sort pending tasks by due_datetime ascending (None at end)
        pending_task_items.sort(
            key=lambda t: (t.due_datetime is None, t.due_datetime),
        )

        total_active = pending + in_progress + completed

        return MyTasksReport(
            total_active=total_active,
            total_completed=completed,
            today_total=today_total,
            today_completed=today_completed,
            pending_count=pending,
            in_progress_count=in_progress,
            completed_count=completed,
            overdue_count=overdue,
            pending_tasks=pending_task_items,
        )

    def get_project_task_stats(
        self,
        project_id: int,
    ) -> ProjectTaskStatsResponse:
        """Get project-level task statistics (Section 2)."""
        now = datetime.now(IST)

        query = select(Task).where(Task.project_id == project_id)
        tasks = list(self.db.execute(query).scalars().all())

        pending = 0
        in_progress = 0
        done = 0
        overdue = 0
        cancelled = 0

        for task in tasks:
            if task.status == TaskStatus.PENDING:
                pending += 1
            elif task.status == TaskStatus.IN_PROGRESS:
                in_progress += 1
            elif task.status == TaskStatus.DONE:
                done += 1
            elif task.status == TaskStatus.CANCELLED:
                cancelled += 1

            if task.due_datetime and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                if task.due_datetime < now:
                    overdue += 1

        active_tasks = pending + in_progress
        total_tasks = pending + in_progress + done + cancelled

        # Evo leaderboard (reuse logic)
        evo_stats = self._get_evo_stats(project_id, user_id=0)

        return ProjectTaskStatsResponse(
            pending_count=pending,
            in_progress_count=in_progress,
            overdue_count=overdue,
            completed_count=done,
            active_tasks=active_tasks,
            total_tasks=total_tasks,
            status_distribution=TaskStatusCount(
                pending=pending,
                in_progress=in_progress,
                done=done,
                overdue=overdue,
                cancelled=cancelled,
            ),
            evo_leaderboard=evo_stats.leaderboard,
        )

    def get_user_level_stats(
        self,
        project_id: int,
    ) -> UserLevelStatsResponse:
        """Get per-user task statistics for admin view (Section 3)."""
        now = datetime.now(IST)
        today_date = now.date()

        # Get all users in this project
        users_query = (
            select(User)
            .join(UserRoleProject, UserRoleProject.user_id == User.id)
            .where(
                UserRoleProject.project_id == project_id,
                User.is_active == True,
            )
            .distinct()
        )
        project_users = list(self.db.execute(users_query).scalars().all())

        # Get ALL tasks in this project in a single query
        all_tasks = list(
            self.db.execute(
                select(Task).where(Task.project_id == project_id)
            ).scalars().all()
        )

        # Group tasks by assigned user
        tasks_by_user: dict[int, list[Task]] = {}
        for task in all_tasks:
            if task.assigned_to_user_id:
                tasks_by_user.setdefault(task.assigned_to_user_id, []).append(task)

        overall_total = 0
        overall_completed = 0
        aggregate_today_total = 0
        aggregate_today_completed = 0
        user_rows: list[UserDailyTaskRow] = []

        for user in project_users:
            user_tasks = tasks_by_user.get(user.id, [])

            u_pending = 0
            u_in_progress = 0
            u_completed = 0
            u_overdue = 0
            u_today_total = 0
            u_today_completed = 0
            u_pending_items: list[TaskListItem] = []

            for task in user_tasks:
                if task.status == TaskStatus.CANCELLED:
                    continue

                if task.status == TaskStatus.PENDING:
                    u_pending += 1
                elif task.status == TaskStatus.IN_PROGRESS:
                    u_in_progress += 1
                elif task.status == TaskStatus.DONE:
                    u_completed += 1

                is_overdue = False
                if task.due_datetime and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                    if task.due_datetime < now:
                        u_overdue += 1
                        is_overdue = True

                if task.due_datetime:
                    task_due_date = task.due_datetime.date()
                    if task_due_date == today_date:
                        u_today_total += 1
                        if task.status == TaskStatus.DONE:
                            u_today_completed += 1

                # Pending/in-progress tasks due today for dropdown
                if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                    if task.due_datetime and task.due_datetime.date() == today_date:
                        u_pending_items.append(TaskListItem(
                            id=task.id,
                            title=task.title,
                            due_datetime=task.due_datetime,
                            status="overdue" if is_overdue else task.status.value,
                        ))

            u_pending_items.sort(
                key=lambda t: (t.due_datetime is None, t.due_datetime),
            )

            u_active = u_pending + u_in_progress + u_completed
            completion_pct = (
                (u_today_completed / u_today_total * 100) if u_today_total > 0 else 0.0
            )

            overall_total += u_active
            overall_completed += u_completed
            aggregate_today_total += u_today_total
            aggregate_today_completed += u_today_completed

            user_rows.append(UserDailyTaskRow(
                user_id=user.id,
                user_name=user.name,
                today_total=u_today_total,
                today_completed=u_today_completed,
                completion_percentage=round(completion_pct, 1),
                pending_count=u_pending,
                in_progress_count=u_in_progress,
                completed_count=u_completed,
                overdue_count=u_overdue,
                pending_tasks=u_pending_items,
            ))

        # Sort by completion percentage descending
        user_rows.sort(key=lambda r: r.completion_percentage, reverse=True)

        return UserLevelStatsResponse(
            today_total=aggregate_today_total,
            today_completed=aggregate_today_completed,
            overall_total=overall_total,
            overall_completed=overall_completed,
            user_rows=user_rows,
        )
