"""create conversation history

Revision ID: 0001
Revises: 
Create Date: 2026-08-14 11:07:03.337056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
# 建立 Conversation History Database 結構

    # 建立 conversation history schema
    op.execute(sa.schema.CreateSchema("conversation_history"))

    # 建立 conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False), # sa.Column("column name", 資料型別, 是否允許沒有值)
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"), # PrimaryKeyConstraint() 確保 conversations Table 中的 id 不可 null 不重複
        schema="conversation_history"
    )

    # 建立 messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("turn_id", sa.UUID(),nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb") # 無提供 metadata 時預設填入 {} JSON 空物件
            ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.ForeignKeyConstraint( 
            # 建立 messages Table 和 conversations Table 之間的 Foreign Key 關係
            # 僅檢查及聯動刪除
            ["conversation_id"],
            ["conversation_history.conversations.id"],
            name="fk_messages_conversation_id",
            ondelete="CASCADE" # 聯動刪除
            ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"), # 檢查輸入值
        sa.UniqueConstraint("conversation_id", "turn_id", "role", name="uq_messages_conversation_turn_id"), # 建立組合唯一限制, 三個 column 完全相同才阻擋輸入
        schema="conversation_history"
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
