"""Project export/import service for transferring projects between instances."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.menu_screen import MenuScreen, ProjectMenuScreen
from app.models.project import Project, ProjectStatus
from app.models.rbac import Permission, Role, RolePermission, UserRoleProject
from app.models.task import (
    EvoReductionType,
    RecurrenceType,
    RecurringTaskTemplate,
    Task,
    TaskCategory,
    TaskStatus,
)
from app.models.task_view import TaskViewStyle, UserTaskViewPreference
from app.models.user import User
from app.schemas.project_transfer import (
    ExportProject,
    ExportProjectMenuScreen,
    ExportRecurringTaskTemplate,
    ExportRole,
    ExportRolePermission,
    ExportTask,
    ExportTaskCategory,
    ExportTaskViewStyle,
    ExportUser,
    ExportUserRoleAssignment,
    ExportUserTaskViewPreference,
    ImportEntitySummary,
    ProjectExportFile,
    ProjectImportResult,
)

logger = logging.getLogger(__name__)


class ProjectTransferService:
    """Handles export and import of complete project data."""

    def __init__(self, db: Session):
        self.db = db

    # ── EXPORT ──────────────────────────────────────────────────────

    def export_project(self, project_id: int) -> dict:
        """Export all project-scoped data to a serialisable dict."""

        # 1. Project
        project = self.db.execute(
            select(Project).where(Project.id == project_id)
        ).scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", str(project_id))

        # 2. Collect user IDs involved in this project (via UserRoleProject)
        urp_rows = self.db.execute(
            select(UserRoleProject).where(UserRoleProject.project_id == project_id)
        ).scalars().all()
        user_ids = list({urp.user_id for urp in urp_rows})

        # Bulk-fetch users
        users: list[User] = []
        if user_ids:
            users = list(
                self.db.execute(
                    select(User).where(User.id.in_(user_ids))
                ).scalars().all()
            )
        user_map: dict[int, User] = {u.id: u for u in users}

        # 3. Roles
        roles = list(
            self.db.execute(
                select(Role).where(Role.project_id == project_id)
            ).scalars().all()
        )
        role_map: dict[int, Role] = {r.id: r for r in roles}

        # 4. RolePermissions (join permission for key)
        rp_rows = self.db.execute(
            select(RolePermission, Permission.permission_key)
            .join(Permission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.project_id == project_id)
        ).all()

        # 5. TaskCategories
        categories = list(
            self.db.execute(
                select(TaskCategory).where(TaskCategory.project_id == project_id)
            ).scalars().all()
        )

        # 6. RecurringTaskTemplates
        templates = list(
            self.db.execute(
                select(RecurringTaskTemplate)
                .where(RecurringTaskTemplate.project_id == project_id)
            ).scalars().all()
        )

        # 7. Tasks
        tasks = list(
            self.db.execute(
                select(Task).where(Task.project_id == project_id)
            ).scalars().all()
        )

        # 8. TaskViewStyles
        view_styles = list(
            self.db.execute(
                select(TaskViewStyle).where(TaskViewStyle.project_id == project_id)
            ).scalars().all()
        )

        # 9. UserTaskViewPreferences
        vs_ids = [vs.id for vs in view_styles]
        view_prefs: list[UserTaskViewPreference] = []
        if vs_ids:
            view_prefs = list(
                self.db.execute(
                    select(UserTaskViewPreference).where(
                        UserTaskViewPreference.project_id == project_id,
                    )
                ).scalars().all()
            )

        # 10. ProjectMenuScreens → join MenuScreen for name
        pms_rows = self.db.execute(
            select(ProjectMenuScreen, MenuScreen.name)
            .join(MenuScreen, ProjectMenuScreen.menu_screen_id == MenuScreen.id)
            .where(ProjectMenuScreen.project_id == project_id)
        ).all()

        # ── Serialise ──

        def _user_email(uid: int | None) -> str | None:
            if uid and uid in user_map:
                return user_map[uid].email
            return None

        def _user_username(uid: int | None) -> str | None:
            if uid and uid in user_map:
                return user_map[uid].username
            return None

        def _role_name(rid: int | None) -> str | None:
            if rid and rid in role_map:
                return role_map[rid].name
            return None

        export = ProjectExportFile(
            exported_at=datetime.now(timezone.utc),
            project=ExportProject(
                name=project.name,
                slug=project.slug,
                description=project.description,
                theme_color=project.theme_color,
                logo_url=project.logo_url,
                status=project.status.value if isinstance(project.status, ProjectStatus) else project.status,
                default_evo_points=project.default_evo_points,
            ),
            users=[
                ExportUser(
                    export_id=u.id,
                    username=u.username,
                    email=u.email,
                    name=u.name,
                    phone=u.phone,
                    password_hash=u.password_hash,
                    is_active=u.is_active,
                    evo_points=u.evo_points,
                )
                for u in users
            ],
            roles=[
                ExportRole(
                    export_id=r.id,
                    name=r.name,
                    description=r.description,
                    is_project_admin=r.is_project_admin,
                    is_role_admin=r.is_role_admin,
                )
                for r in roles
            ],
            role_permissions=[
                ExportRolePermission(
                    role_name=_role_name(rp.role_id) or "",
                    permission_key=perm_key,
                )
                for rp, perm_key in rp_rows
                if _role_name(rp.role_id)
            ],
            user_role_assignments=[
                ExportUserRoleAssignment(
                    user_email=_user_email(urp.user_id),
                    user_username=_user_username(urp.user_id) or "",
                    role_name=_role_name(urp.role_id) or "",
                )
                for urp in urp_rows
                if _user_username(urp.user_id) and _role_name(urp.role_id)
            ],
            task_categories=[
                ExportTaskCategory(
                    export_id=c.id,
                    name=c.name,
                    description=c.description,
                    color=c.color,
                )
                for c in categories
            ],
            recurring_task_templates=[
                ExportRecurringTaskTemplate(
                    export_id=t.id,
                    title=t.title,
                    description=t.description,
                    category_export_id=t.category_id,
                    recurrence_type=t.recurrence_type.value if isinstance(t.recurrence_type, RecurrenceType) else t.recurrence_type,
                    days_of_week=t.days_of_week,
                    scheduled_date=t.scheduled_date,
                    created_on_time=t.created_on_time,
                    start_time=t.start_time,
                    due_time=t.due_time,
                    assigned_to_email=_user_email(t.assigned_to_user_id),
                    assigned_to_username=_user_username(t.assigned_to_user_id),
                    is_active=t.is_active,
                    last_generated_date=t.last_generated_date,
                    created_by_email=_user_email(t.created_by_id),
                    created_by_username=_user_username(t.created_by_id),
                    evo_points=t.evo_points,
                    evo_reduction_type=t.evo_reduction_type.value if isinstance(t.evo_reduction_type, EvoReductionType) else t.evo_reduction_type,
                    evo_extension_time=t.evo_extension_time,
                    evo_fixed_reduction_points=t.evo_fixed_reduction_points,
                )
                for t in templates
            ],
            tasks=[
                ExportTask(
                    export_id=t.id,
                    title=t.title,
                    description=t.description,
                    status=t.status.value if isinstance(t.status, TaskStatus) else t.status,
                    due_datetime=t.due_datetime,
                    start_time=t.start_time,
                    end_time=t.end_time,
                    category_export_id=t.category_id,
                    assigned_to_email=_user_email(t.assigned_to_user_id),
                    assigned_to_username=_user_username(t.assigned_to_user_id),
                    assigned_to_role_name=_role_name(t.assigned_to_role_id),
                    auto_rule_key=t.auto_rule_key,
                    recurring_template_export_id=t.recurring_template_id,
                    created_by_email=_user_email(t.created_by_id),
                    created_by_username=_user_username(t.created_by_id),
                    evo_points=t.evo_points,
                    evo_reduction_type=t.evo_reduction_type.value if isinstance(t.evo_reduction_type, EvoReductionType) else t.evo_reduction_type,
                    evo_extension_end=t.evo_extension_end,
                    evo_fixed_reduction_points=t.evo_fixed_reduction_points,
                    created_at=t.created_at,
                )
                for t in tasks
            ],
            task_view_styles=[
                ExportTaskViewStyle(
                    export_id=vs.id,
                    name=vs.name,
                    description=vs.description,
                    column_config=vs.column_config or [],
                    is_system_default=vs.is_system_default,
                    created_by_email=_user_email(vs.created_by_id),
                    created_by_username=_user_username(vs.created_by_id),
                )
                for vs in view_styles
            ],
            user_task_view_preferences=[
                ExportUserTaskViewPreference(
                    user_email=_user_email(vp.user_id),
                    user_username=_user_username(vp.user_id) or "",
                    view_style_export_id=vp.view_style_id,
                )
                for vp in view_prefs
                if _user_username(vp.user_id)
            ],
            project_menu_screens=[
                ExportProjectMenuScreen(menu_screen_name=name)
                for _, name in pms_rows
            ],
        )

        return export.model_dump(mode="json")

    # ── IMPORT ──────────────────────────────────────────────────────

    def import_project(self, data: dict) -> ProjectImportResult:
        """Import a full project from an export dict. Atomic — rolls back on error."""

        # Validate format version
        version = data.get("format_version")
        if version != "1.0":
            raise ValidationError(f"Unsupported export format version: {version}")

        proj_data = data.get("project")
        if not proj_data:
            raise ValidationError("Export file missing 'project' section")

        slug = proj_data.get("slug", "")
        existing = self.db.execute(
            select(Project).where(Project.slug == slug)
        ).scalar_one_or_none()
        if existing:
            raise ValidationError(f"A project with slug '{slug}' already exists")

        warnings: list[str] = []

        # ── 1. Create project ──
        project = Project(
            name=proj_data["name"],
            slug=slug,
            description=proj_data.get("description"),
            theme_color=proj_data.get("theme_color"),
            logo_url=proj_data.get("logo_url"),
            status=ProjectStatus.ACTIVE,
            default_evo_points=proj_data.get("default_evo_points", 0),
        )
        self.db.add(project)
        self.db.flush()
        project_id = project.id

        # ── 2. Resolve / create users ──
        user_summary = ImportEntitySummary()
        # Map: old_export_id → new db id
        user_id_map: dict[int, int] = {}
        # Map: email → new db id  AND  username → new db id (for lookup)
        email_to_id: dict[str, int] = {}
        username_to_id: dict[str, int] = {}

        for u in data.get("users", []):
            export_id = u.get("export_id")
            email = u.get("email")
            username = u.get("username", "")

            # Try to match existing user by email first, then username
            existing_user: User | None = None
            if email:
                existing_user = self.db.execute(
                    select(User).where(User.email == email)
                ).scalar_one_or_none()
            if not existing_user and username:
                existing_user = self.db.execute(
                    select(User).where(User.username == username)
                ).scalar_one_or_none()

            if existing_user:
                if export_id is not None:
                    user_id_map[export_id] = existing_user.id
                if email:
                    email_to_id[email] = existing_user.id
                username_to_id[username] = existing_user.id
                user_summary.matched += 1
            else:
                # Ensure username uniqueness — append suffix if taken
                final_username = username
                suffix = 1
                while True:
                    taken = self.db.execute(
                        select(User.id).where(User.username == final_username)
                    ).scalar_one_or_none()
                    if not taken:
                        break
                    final_username = f"{username}_{suffix}"
                    suffix += 1

                if final_username != username:
                    warnings.append(
                        f"User '{username}' renamed to '{final_username}' (username conflict)"
                    )

                new_user = User(
                    username=final_username,
                    email=email,
                    name=u.get("name", username),
                    phone=u.get("phone"),
                    password_hash=u.get("password_hash"),
                    is_active=u.get("is_active", True),
                    is_super_admin=False,  # Security: never import super admin
                    evo_points=u.get("evo_points", 0),
                )
                self.db.add(new_user)
                self.db.flush()

                if export_id is not None:
                    user_id_map[export_id] = new_user.id
                if email:
                    email_to_id[email] = new_user.id
                username_to_id[final_username] = new_user.id
                user_summary.created += 1

        # Helper to resolve a user from export data (email/username)
        def _resolve_user(email: str | None, username: str | None) -> int | None:
            if email and email in email_to_id:
                return email_to_id[email]
            if username and username in username_to_id:
                return username_to_id[username]
            # Try DB lookup as fallback
            if email:
                row = self.db.execute(
                    select(User.id).where(User.email == email)
                ).scalar_one_or_none()
                if row:
                    email_to_id[email] = row
                    return row
            if username:
                row = self.db.execute(
                    select(User.id).where(User.username == username)
                ).scalar_one_or_none()
                if row:
                    username_to_id[username] = row
                    return row
            return None

        # ── 3. Create roles ──
        role_summary = ImportEntitySummary()
        role_name_to_id: dict[str, int] = {}

        for r in data.get("roles", []):
            role = Role(
                project_id=project_id,
                name=r["name"],
                description=r.get("description"),
                is_project_admin=r.get("is_project_admin", False),
                is_role_admin=r.get("is_role_admin", False),
            )
            self.db.add(role)
            self.db.flush()
            role_name_to_id[r["name"]] = role.id
            role_summary.created += 1

        # ── 4. Create role permissions ──
        rp_summary = ImportEntitySummary()
        # Pre-fetch all permissions on this instance
        all_perms = {
            p.permission_key: p.id
            for p in self.db.execute(select(Permission)).scalars().all()
        }

        for rp in data.get("role_permissions", []):
            role_name = rp.get("role_name", "")
            perm_key = rp.get("permission_key", "")
            role_id = role_name_to_id.get(role_name)
            perm_id = all_perms.get(perm_key)

            if not role_id:
                rp_summary.skipped += 1
                warnings.append(f"Role permission skipped: role '{role_name}' not found")
                continue
            if not perm_id:
                rp_summary.skipped += 1
                warnings.append(f"Role permission skipped: permission '{perm_key}' not found on target")
                continue

            self.db.add(RolePermission(
                project_id=project_id,
                role_id=role_id,
                permission_id=perm_id,
            ))
            rp_summary.created += 1

        self.db.flush()

        # ── 5. Create user role assignments ──
        ura_summary = ImportEntitySummary()

        for ura in data.get("user_role_assignments", []):
            user_id = _resolve_user(ura.get("user_email"), ura.get("user_username"))
            role_id = role_name_to_id.get(ura.get("role_name", ""))

            if not user_id:
                ura_summary.skipped += 1
                warnings.append(
                    f"User role assignment skipped: user '{ura.get('user_email') or ura.get('user_username')}' not found"
                )
                continue
            if not role_id:
                ura_summary.skipped += 1
                continue

            self.db.add(UserRoleProject(
                user_id=user_id,
                role_id=role_id,
                project_id=project_id,
            ))
            ura_summary.created += 1

        self.db.flush()

        # ── 6. Create task categories ──
        cat_summary = ImportEntitySummary()
        cat_id_map: dict[int, int] = {}  # old_export_id → new id

        for c in data.get("task_categories", []):
            cat = TaskCategory(
                project_id=project_id,
                name=c["name"],
                description=c.get("description"),
                color=c.get("color"),
            )
            self.db.add(cat)
            self.db.flush()
            old_id = c.get("export_id")
            if old_id is not None:
                cat_id_map[old_id] = cat.id
            cat_summary.created += 1

        # ── 7. Create recurring task templates ──
        tmpl_summary = ImportEntitySummary()
        tmpl_id_map: dict[int, int] = {}

        for t in data.get("recurring_task_templates", []):
            assigned_uid = _resolve_user(t.get("assigned_to_email"), t.get("assigned_to_username"))
            created_uid = _resolve_user(t.get("created_by_email"), t.get("created_by_username"))

            if not created_uid:
                # Fallback: use the first imported user as creator
                created_uid = next(iter(user_id_map.values()), None)
                if not created_uid:
                    tmpl_summary.skipped += 1
                    warnings.append(f"Recurring template '{t.get('title')}' skipped: no creator found")
                    continue

            tmpl = RecurringTaskTemplate(
                project_id=project_id,
                title=t["title"],
                description=t.get("description"),
                category_id=cat_id_map.get(t.get("category_export_id")) if t.get("category_export_id") else None,
                recurrence_type=t["recurrence_type"],
                days_of_week=t.get("days_of_week"),
                scheduled_date=t.get("scheduled_date"),
                created_on_time=t.get("created_on_time"),
                start_time=t.get("start_time"),
                due_time=t.get("due_time"),
                assigned_to_user_id=assigned_uid,
                is_active=t.get("is_active", True),
                last_generated_date=t.get("last_generated_date"),
                created_by_id=created_uid,
                evo_points=t.get("evo_points"),
                evo_reduction_type=t.get("evo_reduction_type", "NONE"),
                evo_extension_time=t.get("evo_extension_time"),
                evo_fixed_reduction_points=t.get("evo_fixed_reduction_points"),
            )
            self.db.add(tmpl)
            self.db.flush()
            old_id = t.get("export_id")
            if old_id is not None:
                tmpl_id_map[old_id] = tmpl.id
            tmpl_summary.created += 1

        # ── 8. Create tasks ──
        task_summary = ImportEntitySummary()

        for t in data.get("tasks", []):
            assigned_uid = _resolve_user(t.get("assigned_to_email"), t.get("assigned_to_username"))
            created_uid = _resolve_user(t.get("created_by_email"), t.get("created_by_username"))
            assigned_role_id = role_name_to_id.get(t.get("assigned_to_role_name", "")) if t.get("assigned_to_role_name") else None

            if not created_uid:
                created_uid = next(iter(user_id_map.values()), None)
                if not created_uid:
                    task_summary.skipped += 1
                    warnings.append(f"Task '{t.get('title')}' skipped: no creator found")
                    continue

            task = Task(
                project_id=project_id,
                title=t["title"],
                description=t.get("description"),
                status=t.get("status", "pending"),
                due_datetime=t.get("due_datetime"),
                start_time=t.get("start_time"),
                end_time=t.get("end_time"),
                category_id=cat_id_map.get(t.get("category_export_id")) if t.get("category_export_id") else None,
                assigned_to_user_id=assigned_uid,
                assigned_to_role_id=assigned_role_id,
                auto_rule_key=t.get("auto_rule_key"),
                recurring_template_id=tmpl_id_map.get(t.get("recurring_template_export_id")) if t.get("recurring_template_export_id") else None,
                created_by_id=created_uid,
                evo_points=t.get("evo_points"),
                evo_reduction_type=t.get("evo_reduction_type", "NONE"),
                evo_extension_end=t.get("evo_extension_end"),
                evo_fixed_reduction_points=t.get("evo_fixed_reduction_points"),
            )
            self.db.add(task)
            task_summary.created += 1

        self.db.flush()

        # ── 9. Create task view styles ──
        tvs_summary = ImportEntitySummary()
        tvs_id_map: dict[int, int] = {}

        for vs in data.get("task_view_styles", []):
            created_uid = _resolve_user(vs.get("created_by_email"), vs.get("created_by_username"))

            view_style = TaskViewStyle(
                project_id=project_id,
                name=vs["name"],
                description=vs.get("description"),
                column_config=vs.get("column_config", []),
                is_system_default=vs.get("is_system_default", False),
                created_by_id=created_uid,
            )
            self.db.add(view_style)
            self.db.flush()
            old_id = vs.get("export_id")
            if old_id is not None:
                tvs_id_map[old_id] = view_style.id
            tvs_summary.created += 1

        # ── 10. Create user task view preferences ──
        utvp_summary = ImportEntitySummary()

        for vp in data.get("user_task_view_preferences", []):
            user_id = _resolve_user(vp.get("user_email"), vp.get("user_username"))
            vs_id = tvs_id_map.get(vp.get("view_style_export_id"))

            if not user_id or not vs_id:
                utvp_summary.skipped += 1
                continue

            self.db.add(UserTaskViewPreference(
                user_id=user_id,
                project_id=project_id,
                view_style_id=vs_id,
            ))
            utvp_summary.created += 1

        self.db.flush()

        # ── 11. Create project menu screens ──
        pms_summary = ImportEntitySummary()
        # Pre-fetch menu screens by name
        menu_screens = {
            m.name: m.id
            for m in self.db.execute(select(MenuScreen)).scalars().all()
        }

        exported_menus = data.get("project_menu_screens", [])
        if exported_menus:
            for pm in exported_menus:
                ms_name = pm.get("menu_screen_name", "")
                ms_id = menu_screens.get(ms_name)
                if not ms_id:
                    pms_summary.skipped += 1
                    warnings.append(f"Menu screen '{ms_name}' not found on target, skipped")
                    continue
                self.db.add(ProjectMenuScreen(
                    project_id=project_id,
                    menu_screen_id=ms_id,
                ))
                pms_summary.created += 1
        else:
            # Allocate all menus by default (same as create_project)
            for ms_id in menu_screens.values():
                self.db.add(ProjectMenuScreen(
                    project_id=project_id,
                    menu_screen_id=ms_id,
                ))
                pms_summary.created += 1

        self.db.flush()

        return ProjectImportResult(
            project_id=project_id,
            project_name=project.name,
            project_slug=project.slug,
            users=user_summary,
            roles=role_summary,
            role_permissions=rp_summary,
            user_role_assignments=ura_summary,
            task_categories=cat_summary,
            recurring_task_templates=tmpl_summary,
            tasks=task_summary,
            task_view_styles=tvs_summary,
            user_task_view_preferences=utvp_summary,
            project_menu_screens=pms_summary,
            warnings=warnings,
        )
