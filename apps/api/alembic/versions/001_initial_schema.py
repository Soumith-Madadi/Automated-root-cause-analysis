"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create deployments table
    op.create_table(
        'deployments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('service', sa.Text(), nullable=False),
        sa.Column('commit_sha', sa.Text(), nullable=False),
        sa.Column('version', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('diff_summary', sa.Text(), nullable=True),
        sa.Column('links', postgresql.JSONB(), nullable=True),
    )
    op.create_index('idx_deployments_service_ts', 'deployments', ['service', 'ts'])
    op.create_index('idx_deployments_ts', 'deployments', ['ts'])

    # Create config_changes table
    op.create_table(
        'config_changes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('service', sa.Text(), nullable=False),
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('old_value_hash', sa.Text(), nullable=True),
        sa.Column('new_value_hash', sa.Text(), nullable=True),
        sa.Column('diff_summary', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
    )
    op.create_index('idx_config_changes_service_ts', 'config_changes', ['service', 'ts'])
    op.create_index('idx_config_changes_ts', 'config_changes', ['ts'])

    # Create feature_flag_changes table
    op.create_table(
        'feature_flag_changes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('flag_name', sa.Text(), nullable=False),
        sa.Column('service', sa.Text(), nullable=True),
        sa.Column('old_state', postgresql.JSONB(), nullable=True),
        sa.Column('new_state', postgresql.JSONB(), nullable=True),
    )
    op.create_index('idx_flag_changes_flag_ts', 'feature_flag_changes', ['flag_name', 'ts'])
    op.create_index('idx_flag_changes_ts', 'feature_flag_changes', ['ts'])

    # Create anomalies table
    op.create_table(
        'anomalies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('start_ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('service', sa.Text(), nullable=False),
        sa.Column('metric', sa.Text(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('detector', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
    )
    op.create_index('idx_anomalies_service_ts', 'anomalies', ['service', 'start_ts'])
    op.create_index('idx_anomalies_ts', 'anomalies', ['start_ts', 'end_ts'])

    # Create incidents table
    op.create_table(
        'incidents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('start_ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_ts', sa.DateTime(timezone=True), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='OPEN'),
        sa.Column('summary', sa.Text(), nullable=True),
    )
    op.create_index('idx_incidents_status_ts', 'incidents', ['status', 'start_ts'])
    op.create_index('idx_incidents_ts', 'incidents', ['start_ts'])

    # Create incident_anomalies junction table
    op.create_table(
        'incident_anomalies',
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('anomaly_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['anomaly_id'], ['anomalies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('incident_id', 'anomaly_id'),
    )

    # Create suspects table
    op.create_table(
        'suspects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('suspect_type', sa.Text(), nullable=False),
        sa.Column('suspect_key', sa.Text(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('evidence', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_suspects_incident_rank', 'suspects', ['incident_id', 'rank'])

    # Create labels table
    op.create_table(
        'labels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('suspect_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('label', sa.Integer(), nullable=False),
        sa.Column('labeler', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['suspect_id'], ['suspects.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_labels_incident_suspect', 'labels', ['incident_id', 'suspect_id'])


def downgrade() -> None:
    op.drop_table('labels')
    op.drop_table('suspects')
    op.drop_table('incident_anomalies')
    op.drop_table('incidents')
    op.drop_table('anomalies')
    op.drop_table('feature_flag_changes')
    op.drop_table('config_changes')
    op.drop_table('deployments')


