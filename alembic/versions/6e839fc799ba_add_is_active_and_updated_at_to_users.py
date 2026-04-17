from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6e839fc799ba'
down_revision: Union[str, Sequence[str], None] = 'c38bcb845ae6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'is_active', sa.Boolean(), nullable=False, server_default=sa.true()
    ))
    op.alter_column('users', 'is_active', server_default=None)

    op.add_column('users', sa.Column(
        'updated_at', sa.DateTime(timezone=True),
        server_default=sa.text('now()'), nullable=False
    ))

    op.alter_column('users', 'verification_token',
        existing_type=sa.VARCHAR(length=255),
        type_=sa.String(length=6),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column('users', 'verification_token',
        existing_type=sa.String(length=6),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'is_active')