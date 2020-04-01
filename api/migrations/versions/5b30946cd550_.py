"""empty message

Revision ID: 5b30946cd550
Revises: 490cecca90fc
Create Date: 2020-03-31 18:19:52.601758

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5b30946cd550'
down_revision = '490cecca90fc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('nr_number',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nr_num', sa.String(length=10), nullable=True),
    sa.Column('last_update', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nr_num')
    )
        # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('nr_number')
    # ### end Alembic commands ###
