"""LearnX full-stack schema — auth, courses & roster, file vault, calendar, notifications

Revision ID: b7c9d1e2f3a4
Revises: fa94e7c3c032
Create Date: 2026-08-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7c9d1e2f3a4'
down_revision: Union[str, Sequence[str], None] = 'fa94e7c3c032'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── Enum types ────────────────────────────────────────────────────
    coursetype = postgresql.ENUM('university', 'public', 'premium', name='coursetype')
    coursestatus = postgresql.ENUM('draft', 'pending_review', 'published', 'archived', name='coursestatus')
    lessontype = postgresql.ENUM('video', 'pdf', 'notes', 'quiz', 'assignment', name='lessontype')
    calendareventtype = postgresql.ENUM(
        'exam', 'assignment', 'quiz', 'study_session', 'personal',
        'course_deadline', 'meeting', 'custom', name='calendareventtype',
    )
    notificationkind = postgresql.ENUM(
        'announcement', 'assignment', 'quiz', 'message', 'reminder', 'system',
        name='notificationkind',
    )
    for enum in (coursetype, coursestatus, lessontype, calendareventtype, notificationkind):
        enum.create(bind, checkfirst=True)

    # ── users: auth state columns ─────────────────────────────────────
    op.add_column('users', sa.Column('role', sa.String(length=32), nullable=False, server_default='student'))
    op.add_column('users', sa.Column('auth_provider', sa.String(length=32), nullable=False, server_default='email'))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    # Google-only accounts have no password
    op.alter_column('users', 'hashed_password', existing_type=sa.String(length=255), nullable=True)
    # relax NOT NULL so new (pre-onboarding) users can register with just email+name
    op.alter_column('users', 'full_name', existing_type=sa.String(length=255), nullable=True, server_default='')
    op.alter_column('users', 'preferred_language', existing_type=sa.String(length=8), server_default='en')

    # ── courses: expand the existing table ────────────────────────────
    op.add_column('courses', sa.Column('doctor_id', postgresql.UUID(as_uuid=False), nullable=True))
    op.create_index('ix_courses_doctor_id', 'courses', ['doctor_id'])
    op.create_foreign_key('fk_courses_doctor_id_users', 'courses', 'users', ['doctor_id'], ['id'])
    op.add_column('courses', sa.Column('description', sa.Text(), nullable=False, server_default=''))
    op.add_column('courses', sa.Column('category', sa.String(length=128), nullable=False, server_default=''))
    op.add_column('courses', sa.Column('faculty', sa.String(length=255), nullable=False, server_default=''))
    op.add_column('courses', sa.Column('department', sa.String(length=255), nullable=False, server_default=''))
    op.add_column('courses', sa.Column('academic_level', sa.String(length=64), nullable=False, server_default=''))
    op.add_column('courses', sa.Column('course_type', coursetype, nullable=False, server_default='university'))
    op.add_column('courses', sa.Column('status', coursestatus, nullable=False, server_default='draft'))
    op.add_column('courses', sa.Column('color', sa.String(length=16), nullable=False, server_default='#2DD4BF'))
    op.add_column('courses', sa.Column('icon', sa.String(length=8), nullable=False, server_default='📘'))
    op.add_column('courses', sa.Column('rating', sa.Float(), nullable=False, server_default='4.5'))
    op.add_column('courses', sa.Column('price_usd', sa.Float(), nullable=True))
    op.add_column('courses', sa.Column('allow_xp_redemption', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('courses', sa.Column('xp_price', sa.Integer(), nullable=True))
    op.add_column('courses', sa.Column('students_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('courses', sa.Column('completion_rate', sa.Float(), nullable=False, server_default='0'))
    op.add_column('courses', sa.Column('last_updated', sa.DateTime(), nullable=True))

    # ── course_modules ────────────────────────────────────────────────
    op.create_table('course_modules',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('course_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_course_modules_course_id', 'course_modules', ['course_id'])

    # ── course_lessons ────────────────────────────────────────────────
    op.create_table('course_lessons',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('module_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('type', lessontype, nullable=False, server_default='video'),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('resources', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.ForeignKeyConstraint(['module_id'], ['course_modules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_course_lessons_module_id', 'course_lessons', ['module_id'])

    # ── enrollments ───────────────────────────────────────────────────
    op.create_table('enrollments',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('course_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('purchased_via_reward', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('saved', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('enrolled_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_viewed_at', sa.DateTime(), nullable=True),
        sa.Column('last_lesson_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_enrollments_course_id', 'enrollments', ['course_id'])
    op.create_index('ix_enrollments_student_id', 'enrollments', ['student_id'])

    # ── lesson_progress ───────────────────────────────────────────────
    op.create_table('lesson_progress',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('course_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('lesson_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lesson_id'], ['course_lessons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lesson_progress_course_id', 'lesson_progress', ['course_id'])
    op.create_index('ix_lesson_progress_lesson_id', 'lesson_progress', ['lesson_id'])
    op.create_index('ix_lesson_progress_student_id', 'lesson_progress', ['student_id'])

    # ── vault_files ───────────────────────────────────────────────────
    op.create_table('vault_files',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=512), nullable=False, server_default=''),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mime_type', sa.String(length=128), nullable=False, server_default='application/octet-stream'),
        sa.Column('storage_key', sa.String(length=1024), nullable=False, server_default=''),
        sa.Column('course', sa.String(length=255), nullable=True),
        sa.Column('doctor_name', sa.String(length=255), nullable=True),
        sa.Column('favorite', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('collections', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('exam_date', sa.String(length=32), nullable=True),
        sa.Column('reading_progress_pct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('learning_status', sa.String(length=32), nullable=False, server_default='not-started'),
        sa.Column('last_page', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_pages', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('analysis', postgresql.JSONB(), nullable=True),
        sa.Column('metadata_payload', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_vault_files_owner_id', 'vault_files', ['owner_id'])

    # ── student_notes ─────────────────────────────────────────────────
    op.create_table('student_notes',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('page', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('color', sa.String(length=16), nullable=False, server_default='#f59e0b'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['vault_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_student_notes_file_id', 'student_notes', ['file_id'])
    op.create_index('ix_student_notes_owner_id', 'student_notes', ['owner_id'])

    # ── file_bookmarks ────────────────────────────────────────────────
    op.create_table('file_bookmarks',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('page', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('label', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['vault_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_file_bookmarks_file_id', 'file_bookmarks', ['file_id'])
    op.create_index('ix_file_bookmarks_owner_id', 'file_bookmarks', ['owner_id'])

    # ── calendar_events ───────────────────────────────────────────────
    op.create_table('calendar_events',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('date', sa.String(length=16), nullable=False, server_default=''),
        sa.Column('time', sa.String(length=8), nullable=True),
        sa.Column('color', sa.String(length=16), nullable=False, server_default='#2DD4BF'),
        sa.Column('type', calendareventtype, nullable=False, server_default='custom'),
        sa.Column('course_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('reminder_minutes_before', sa.Integer(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_calendar_events_owner_id', 'calendar_events', ['owner_id'])
    op.create_index('ix_calendar_events_date', 'calendar_events', ['date'])

    # ── notifications ─────────────────────────────────────────────────
    op.create_table('notifications',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('recipient_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('kind', notificationkind, nullable=False, server_default='system'),
        sa.Column('title', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('icon', sa.String(length=16), nullable=False, server_default='🔔'),
        sa.Column('link', sa.String(length=512), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_recipient_id', 'notifications', ['recipient_id'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])

    # ── email_verification_tokens ─────────────────────────────────────
    op.create_table('email_verification_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_verification_tokens_token_hash', 'email_verification_tokens', ['token_hash'], unique=True)
    op.create_index('ix_email_verification_tokens_user_id', 'email_verification_tokens', ['user_id'])

    # ── password_reset_tokens ─────────────────────────────────────────
    op.create_table('password_reset_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])


def downgrade() -> None:
    op.drop_table('password_reset_tokens')
    op.drop_table('email_verification_tokens')
    op.drop_table('notifications')
    op.drop_table('calendar_events')
    op.drop_table('file_bookmarks')
    op.drop_table('student_notes')
    op.drop_table('vault_files')
    op.drop_table('lesson_progress')
    op.drop_table('enrollments')
    op.drop_table('course_lessons')
    op.drop_table('course_modules')

    op.drop_constraint('fk_courses_doctor_id_users', 'courses', type_='foreignkey')
    op.drop_index('ix_courses_doctor_id', table_name='courses')
    op.drop_column('courses', 'last_updated')
    op.drop_column('courses', 'completion_rate')
    op.drop_column('courses', 'students_count')
    op.drop_column('courses', 'xp_price')
    op.drop_column('courses', 'allow_xp_redemption')
    op.drop_column('courses', 'price_usd')
    op.drop_column('courses', 'rating')
    op.drop_column('courses', 'icon')
    op.drop_column('courses', 'color')
    op.drop_column('courses', 'status')
    op.drop_column('courses', 'course_type')
    op.drop_column('courses', 'academic_level')
    op.drop_column('courses', 'department')
    op.drop_column('courses', 'faculty')
    op.drop_column('courses', 'category')
    op.drop_column('courses', 'description')
    op.drop_column('courses', 'doctor_id')

    op.alter_column('users', 'hashed_password', existing_type=sa.String(length=255), nullable=False)
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'auth_provider')
    op.drop_column('users', 'role')

    for enum in (
        postgresql.ENUM(name='notificationkind'),
        postgresql.ENUM(name='calendareventtype'),
        postgresql.ENUM(name='lessontype'),
        postgresql.ENUM(name='coursestatus'),
        postgresql.ENUM(name='coursetype'),
    ):
        enum.drop(op.get_bind(), checkfirst=True)
