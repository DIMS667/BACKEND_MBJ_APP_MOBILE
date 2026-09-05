"""drop emotions and routines tables

Revision ID: 271f068c41d5
Revises: fabde132271c
Create Date: 2026-09-03 22:24:20.870722

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '271f068c41d5'
down_revision: Union[str, Sequence[str], None] = 'fabde132271c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_calming_feedback_child_activity_recorded'), table_name='calming_activity_feedback')
    op.drop_index(op.f('ix_calming_activity_feedback_id'), table_name='calming_activity_feedback')
    op.drop_table('calming_activity_feedback')

    op.drop_index(op.f('ix_emotion_records_child_recorded_at'), table_name='emotion_records')
    op.drop_index(op.f('ix_emotion_records_id'), table_name='emotion_records')
    op.drop_table('emotion_records')

    op.drop_index(op.f('ix_calming_activities_id'), table_name='calming_activities')
    op.drop_table('calming_activities')

    op.drop_index(op.f('ix_emotions_id'), table_name='emotions')
    op.drop_table('emotions')

    op.drop_index(op.f('ix_routine_sessions_id'), table_name='routine_sessions')
    op.drop_index(op.f('ix_routine_sessions_routine_id'), table_name='routine_sessions')
    op.drop_table('routine_sessions')

    op.drop_index(op.f('ix_routine_steps_id'), table_name='routine_steps')
    op.drop_index(op.f('ix_routine_steps_client_uuid'), table_name='routine_steps')
    op.drop_table('routine_steps')

    op.drop_index(op.f('ix_routines_id'), table_name='routines')
    op.drop_index(op.f('ix_routines_child_id'), table_name='routines')
    op.drop_table('routines')

    op.drop_column('children', 'photo_url')
    op.drop_column('children', 'age')


def downgrade() -> None:
    op.add_column('children', sa.Column('age', sa.INTEGER(), autoincrement=False, nullable=False))
    op.add_column('children', sa.Column('photo_url', sa.VARCHAR(), autoincrement=False, nullable=True))

    op.create_table(
        'routines',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('child_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('title', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('icon_url', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('type', sa.VARCHAR(), server_default=sa.text("'custom'::character varying"), autoincrement=False, nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('is_default', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['child_id'], ['children.id'], name=op.f('routines_child_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('routines_pkey')),
    )
    op.create_index(op.f('ix_routines_id'), 'routines', ['id'], unique=False)
    op.create_index(op.f('ix_routines_child_id'), 'routines', ['child_id'], unique=False)

    op.create_table(
        'routine_steps',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('routine_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('order', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('title', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('image_url', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('audio_url', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('is_completed', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('is_default', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
        sa.Column('client_uuid', sa.VARCHAR(length=64), autoincrement=False, nullable=True),
        sa.CheckConstraint('"order" >= 1', name=op.f('ck_routine_steps_order_positive')),
        sa.ForeignKeyConstraint(['routine_id'], ['routines.id'], name=op.f('routine_steps_routine_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('routine_steps_pkey')),
        sa.UniqueConstraint('routine_id', 'client_uuid', name=op.f('uq_routine_steps_routine_client')),
        sa.UniqueConstraint('routine_id', 'order', name=op.f('uq_routine_steps_routine_order')),
    )
    op.create_index(op.f('ix_routine_steps_id'), 'routine_steps', ['id'], unique=False)
    op.create_index(op.f('ix_routine_steps_client_uuid'), 'routine_steps', ['client_uuid'], unique=False)

    op.create_table(
        'routine_sessions',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('routine_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('started_at', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('completed_at', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('steps_completed', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=True),
        sa.Column('total_steps', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=True),
        sa.Column('is_completed', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['routine_id'], ['routines.id'], name=op.f('routine_sessions_routine_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('routine_sessions_pkey')),
    )
    op.create_index(op.f('ix_routine_sessions_routine_id'), 'routine_sessions', ['routine_id'], unique=False)
    op.create_index(op.f('ix_routine_sessions_id'), 'routine_sessions', ['id'], unique=False)

    op.create_table(
        'emotions',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('icon_url', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('color', sa.VARCHAR(), server_default=sa.text("'#4A90D9'::character varying"), autoincrement=False, nullable=False),
        sa.Column('is_positive', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('emotions_pkey')),
        sa.UniqueConstraint('name', name=op.f('emotions_name_key')),
    )
    op.create_index(op.f('ix_emotions_id'), 'emotions', ['id'], unique=False)

    op.create_table(
        'calming_activities',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('type', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('description', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('content_url', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('duration_seconds', sa.INTEGER(), server_default=sa.text('60'), autoincrement=False, nullable=True),
        sa.Column('icon_url', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('display_order', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('calming_activities_pkey')),
    )
    op.create_index(op.f('ix_calming_activities_id'), 'calming_activities', ['id'], unique=False)

    op.create_table(
        'emotion_records',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('child_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('emotion_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('context', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('client_uuid', sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column('context_key', sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column('intensity', sa.VARCHAR(length=16), autoincrement=False, nullable=True),
        sa.Column('recorded_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.CheckConstraint("intensity IS NULL OR (intensity::text = ANY (ARRAY['doux'::character varying, 'moyen'::character varying, 'fort'::character varying]::text[]))", name=op.f('ck_emotion_records_intensity')),
        sa.ForeignKeyConstraint(['child_id'], ['children.id'], name=op.f('emotion_records_child_id_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['emotion_id'], ['emotions.id'], name=op.f('emotion_records_emotion_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('emotion_records_pkey')),
        sa.UniqueConstraint('child_id', 'client_uuid', name=op.f('uq_emotion_records_child_client')),
    )
    op.create_index(op.f('ix_emotion_records_id'), 'emotion_records', ['id'], unique=False)
    op.create_index(op.f('ix_emotion_records_child_recorded_at'), 'emotion_records', ['child_id', 'recorded_at'], unique=False)

    op.create_table(
        'calming_activity_feedback',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('child_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('emotion_record_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('activity_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('client_uuid', sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column('helped', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column('recorded_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['activity_id'], ['calming_activities.id'], name=op.f('calming_activity_feedback_activity_id_fkey'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['child_id'], ['children.id'], name=op.f('calming_activity_feedback_child_id_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['emotion_record_id'], ['emotion_records.id'], name=op.f('calming_activity_feedback_emotion_record_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('calming_activity_feedback_pkey')),
        sa.UniqueConstraint('child_id', 'client_uuid', name=op.f('uq_calming_feedback_child_client')),
    )
    op.create_index(op.f('ix_calming_feedback_child_activity_recorded'), 'calming_activity_feedback', ['child_id', 'activity_id', 'recorded_at'], unique=False)
    op.create_index(op.f('ix_calming_activity_feedback_id'), 'calming_activity_feedback', ['id'], unique=False)
