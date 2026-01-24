"""seed_default_data

Revision ID: 113e87aef32d
Revises: 334b10a3d68a
Create Date: 2026-01-24 00:51:19.478983

This migration seeds the required default data:
- All permissions for RBAC
- Core project (default system project)
- Admin user (username: admin, password: admin) with super admin privileges
- Super Admin, School Admin, and Staff roles with appropriate permissions
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from passlib.context import CryptContext


# revision identifiers, used by Alembic.
revision: str = '113e87aef32d'
down_revision: Union[str, None] = '334b10a3d68a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Password hashing for seeding
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Define all permissions
PERMISSIONS = [
    # Attendance permissions
    ("attendance:view", "View attendance records"),
    ("attendance:create", "Create attendance records"),
    ("attendance:update", "Update attendance records"),
    ("attendance:delete", "Delete attendance records"),
    ("attendance:upload", "Upload attendance via Excel"),
    
    # Exam permissions
    ("exam:view", "View exam records"),
    ("exam:create", "Create exam records"),
    ("exam:update", "Update exam records"),
    ("exam:delete", "Delete exam records"),
    ("exam:upload", "Upload exams via Excel"),
    
    # Student permissions
    ("student:view", "View student records"),
    ("student:create", "Create student records"),
    ("student:update", "Update student records"),
    ("student:delete", "Delete student records"),
    ("student:upload", "Upload students via Excel"),
    
    # Task permissions
    ("task:view", "View tasks"),
    ("task:create", "Create tasks"),
    ("task:update", "Update tasks"),
    ("task:delete", "Delete tasks"),
    ("task:assign", "Assign tasks to users"),
    
    # Task category permissions
    ("task_category:view", "View task categories"),
    ("task_category:create", "Create task categories"),
    ("task_category:update", "Update task categories"),
    ("task_category:delete", "Delete task categories"),
    
    # User management permissions
    ("user:view", "View users in project"),
    ("user:invite", "Invite users to project"),
    ("user:remove", "Remove users from project"),
    
    # Role management permissions
    ("role:view", "View roles"),
    ("role:create", "Create roles"),
    ("role:update", "Update roles"),
    ("role:delete", "Delete roles"),
    ("role:assign", "Assign roles to users"),
    
    # Project permissions
    ("project:view", "View project details"),
    ("project:update", "Update project settings"),
    ("project:create", "Create new projects"),
    ("project:delete", "Delete projects"),
    
    # Upload permissions
    ("upload:view", "View upload history"),
    ("upload:create", "Upload files"),
    
    # Notification permissions
    ("notification:view", "View notifications"),
    ("notification:create", "Create notifications"),
    
    # Audit permissions
    ("audit:view", "View audit logs"),
]


def upgrade() -> None:
    """Seed default data: permissions, core project, admin user, and roles."""
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    
    print("🌱 Seeding default data...")
    
    # 1. Create all permissions
    print("   Creating permissions...")
    for perm_key, perm_desc in PERMISSIONS:
        conn.execute(text(
            "INSERT INTO permissions (permission_key, description) VALUES (:key, :desc)"
        ), {"key": perm_key, "desc": perm_desc})
    
    # Get all permission IDs
    perm_result = conn.execute(text("SELECT id, permission_key FROM permissions"))
    permission_map = {row[1]: row[0] for row in perm_result}
    
    # 2. Create Core project
    print("   Creating Core project...")
    conn.execute(text("""
        INSERT INTO projects (name, slug, description, status, created_at, updated_at)
        VALUES ('Core', 'core', 'System administration project for managing schools and users', 'ACTIVE', :now, :now)
    """), {"now": now})
    
    # Get Core project ID
    project_result = conn.execute(text("SELECT id FROM projects WHERE slug = 'core'"))
    core_project_id = project_result.fetchone()[0]
    
    # 3. Create Admin user (username: admin, password: admin)
    print("   Creating Admin user (username: admin, password: admin)...")
    password_hash = pwd_context.hash("Admin@123", rounds=12)
    conn.execute(text("""
        INSERT INTO users (name, username, password_hash, is_active, is_super_admin, evo_points, default_project_id, created_at, updated_at)
        VALUES ('System Administrator', 'admin', :password_hash, true, true, 0, :project_id, :now, :now)
    """), {"password_hash": password_hash, "project_id": core_project_id, "now": now})
    
    # Get Admin user ID
    user_result = conn.execute(text("SELECT id FROM users WHERE username = 'admin'"))
    admin_user_id = user_result.fetchone()[0]
    
    # 4. Create Super Admin role in Core project
    print("   Creating Super Admin role...")
    conn.execute(text("""
        INSERT INTO roles (project_id, name, description, is_project_admin, is_role_admin, created_at, updated_at)
        VALUES (:project_id, 'Super Admin', 'Full system access with all permissions', true, true, :now, :now)
    """), {"project_id": core_project_id, "now": now})
    
    # Get Super Admin role ID
    role_result = conn.execute(text("SELECT id FROM roles WHERE name = 'Super Admin' AND project_id = :project_id"), {"project_id": core_project_id})
    super_admin_role_id = role_result.fetchone()[0]
    
    # 5. Assign ALL permissions to Super Admin role
    print("   Assigning all permissions to Super Admin role...")
    for perm_key, perm_id in permission_map.items():
        conn.execute(text("""
            INSERT INTO role_permissions (project_id, role_id, permission_id, created_at)
            VALUES (:project_id, :role_id, :perm_id, :now)
        """), {"project_id": core_project_id, "role_id": super_admin_role_id, "perm_id": perm_id, "now": now})
    
    # 6. Assign Admin user to Super Admin role in Core project
    print("   Assigning Admin user to Super Admin role...")
    conn.execute(text("""
        INSERT INTO user_role_projects (user_id, role_id, project_id, created_at)
        VALUES (:user_id, :role_id, :project_id, :now)
    """), {"user_id": admin_user_id, "role_id": super_admin_role_id, "project_id": core_project_id, "now": now})
    
    # 7. Create default roles for Core project (School Admin and Staff)
    print("   Creating default School Admin and Staff roles...")
    
    # School Admin role
    conn.execute(text("""
        INSERT INTO roles (project_id, name, description, is_project_admin, is_role_admin, created_at, updated_at)
        VALUES (:project_id, 'School Admin', 'School administrator with management permissions', true, false, :now, :now)
    """), {"project_id": core_project_id, "now": now})
    
    # Staff role
    conn.execute(text("""
        INSERT INTO roles (project_id, name, description, is_project_admin, is_role_admin, created_at, updated_at)
        VALUES (:project_id, 'Staff', 'Regular staff with basic permissions', false, false, :now, :now)
    """), {"project_id": core_project_id, "now": now})
    
    # Get role IDs
    school_admin_result = conn.execute(text("SELECT id FROM roles WHERE name = 'School Admin' AND project_id = :project_id"), {"project_id": core_project_id})
    school_admin_role_id = school_admin_result.fetchone()[0]
    
    staff_result = conn.execute(text("SELECT id FROM roles WHERE name = 'Staff' AND project_id = :project_id"), {"project_id": core_project_id})
    staff_role_id = staff_result.fetchone()[0]
    
    # Assign permissions to School Admin (all except project:delete)
    school_admin_perms = [p for p in permission_map.keys() if p not in ['project:delete']]
    for perm_key in school_admin_perms:
        perm_id = permission_map[perm_key]
        conn.execute(text("""
            INSERT INTO role_permissions (project_id, role_id, permission_id, created_at)
            VALUES (:project_id, :role_id, :perm_id, :now)
        """), {"project_id": core_project_id, "role_id": school_admin_role_id, "perm_id": perm_id, "now": now})
    
    # Assign basic permissions to Staff
    staff_perms = [
        'attendance:view', 'attendance:create', 'attendance:update',
        'exam:view', 'exam:create', 'exam:update',
        'student:view',
        'task:view', 'task:create', 'task:update',
        'task_category:view',
        'upload:view', 'upload:create',
        'notification:view',
    ]
    for perm_key in staff_perms:
        if perm_key in permission_map:
            perm_id = permission_map[perm_key]
            conn.execute(text("""
                INSERT INTO role_permissions (project_id, role_id, permission_id, created_at)
                VALUES (:project_id, :role_id, :perm_id, :now)
            """), {"project_id": core_project_id, "role_id": staff_role_id, "perm_id": perm_id, "now": now})
    
    print("✅ Default data seeded successfully!")
    print("")
    print("=" * 50)
    print("🔐 LOGIN CREDENTIALS")
    print("=" * 50)
    print("   Username: admin")
    print("   Password: admin")
    print("   Project:  Core")
    print("   Role:     Super Admin")
    print("=" * 50)


def downgrade() -> None:
    """Remove all seeded data."""
    conn = op.get_bind()
    
    # Delete in reverse order to respect foreign keys
    conn.execute(text("DELETE FROM user_role_projects"))
    conn.execute(text("DELETE FROM role_permissions"))
    conn.execute(text("DELETE FROM roles"))
    conn.execute(text("DELETE FROM users"))
    conn.execute(text("DELETE FROM projects"))
    conn.execute(text("DELETE FROM permissions"))
