"""Schemas for project export/import (data transfer between instances)."""

from datetime import date, datetime, time

from pydantic import Field

from app.schemas.common import BaseSchema


# ── Export sub-schemas ──────────────────────────────────────────────


class ExportUser(BaseSchema):
    export_id: int
    username: str
    email: str | None = None
    name: str
    phone: str | None = None
    password_hash: str | None = None
    is_active: bool = True
    evo_points: int = 0


class ExportRole(BaseSchema):
    export_id: int
    name: str
    description: str | None = None
    is_project_admin: bool = False
    is_role_admin: bool = False


class ExportRolePermission(BaseSchema):
    role_name: str
    permission_key: str


class ExportUserRoleAssignment(BaseSchema):
    user_email: str | None = None
    user_username: str
    role_name: str


class ExportTaskCategory(BaseSchema):
    export_id: int
    name: str
    description: str | None = None
    color: str | None = None


class ExportRecurringTaskTemplate(BaseSchema):
    export_id: int
    title: str
    description: str | None = None
    category_export_id: int | None = None
    recurrence_type: str
    days_of_week: str | None = None
    scheduled_date: date | None = None
    created_on_time: time | None = None
    start_time: time | None = None
    due_time: time | None = None
    assigned_to_email: str | None = None
    assigned_to_username: str | None = None
    is_active: bool = True
    last_generated_date: date | None = None
    created_by_email: str | None = None
    created_by_username: str | None = None
    evo_points: int | None = None
    evo_reduction_type: str = "NONE"
    evo_extension_time: time | None = None
    evo_fixed_reduction_points: int | None = None


class ExportTask(BaseSchema):
    export_id: int
    title: str
    description: str | None = None
    status: str = "pending"
    due_datetime: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    category_export_id: int | None = None
    assigned_to_email: str | None = None
    assigned_to_username: str | None = None
    assigned_to_role_name: str | None = None
    auto_rule_key: str | None = None
    recurring_template_export_id: int | None = None
    created_by_email: str | None = None
    created_by_username: str | None = None
    evo_points: int | None = None
    evo_reduction_type: str = "NONE"
    evo_extension_end: datetime | None = None
    evo_fixed_reduction_points: int | None = None
    created_at: datetime | None = None


class ExportTaskViewStyle(BaseSchema):
    export_id: int
    name: str
    description: str | None = None
    column_config: list[dict] = []
    is_system_default: bool = False
    created_by_email: str | None = None
    created_by_username: str | None = None


class ExportUserTaskViewPreference(BaseSchema):
    user_email: str | None = None
    user_username: str
    view_style_export_id: int


class ExportProjectMenuScreen(BaseSchema):
    menu_screen_name: str


# ── Top-level export wrapper ───────────────────────────────────────


class ExportProject(BaseSchema):
    name: str
    slug: str
    description: str | None = None
    theme_color: str | None = None
    logo_url: str | None = None
    status: str = "active"
    default_evo_points: int = 0


class ProjectExportFile(BaseSchema):
    format_version: str = "1.0"
    exported_at: datetime
    project: ExportProject
    users: list[ExportUser] = []
    roles: list[ExportRole] = []
    role_permissions: list[ExportRolePermission] = []
    user_role_assignments: list[ExportUserRoleAssignment] = []
    task_categories: list[ExportTaskCategory] = []
    recurring_task_templates: list[ExportRecurringTaskTemplate] = []
    tasks: list[ExportTask] = []
    task_view_styles: list[ExportTaskViewStyle] = []
    user_task_view_preferences: list[ExportUserTaskViewPreference] = []
    project_menu_screens: list[ExportProjectMenuScreen] = []


# ── Import result ──────────────────────────────────────────────────


class ImportEntitySummary(BaseSchema):
    created: int = 0
    matched: int = 0
    skipped: int = 0


class ProjectImportResult(BaseSchema):
    project_id: int
    project_name: str
    project_slug: str
    users: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    roles: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    role_permissions: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    user_role_assignments: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    task_categories: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    recurring_task_templates: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    tasks: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    task_view_styles: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    user_task_view_preferences: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    project_menu_screens: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    warnings: list[str] = []
