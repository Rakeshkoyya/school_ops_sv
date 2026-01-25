"""Add exam_date to exam unique constraint

Revision ID: add_exam_date_unique
Revises: add_project_deleted_audit_action
Create Date: 2026-01-25

This migration updates the exam_records unique constraint to include exam_date,
allowing the same exam type to be recorded on different dates for the same student.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "add_exam_date_unique"
down_revision = "add_project_deleted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old constraint that doesn't include exam_date
    op.drop_constraint("uq_exam_student_subject", "exam_records", type_="unique")
    
    # Create new constraint that includes exam_date
    op.create_unique_constraint(
        "uq_exam_student_subject_date",
        "exam_records",
        ["project_id", "student_id", "exam_name", "subject", "exam_date"],
    )


def downgrade() -> None:
    # Drop the new constraint
    op.drop_constraint("uq_exam_student_subject_date", "exam_records", type_="unique")
    
    # Recreate the old constraint (note: this may fail if duplicate data exists)
    op.create_unique_constraint(
        "uq_exam_student_subject",
        "exam_records",
        ["project_id", "student_id", "exam_name", "subject"],
    )
