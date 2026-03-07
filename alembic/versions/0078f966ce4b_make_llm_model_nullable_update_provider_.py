"""make_llm_model_nullable_update_provider_type_check

Revision ID: 0078f966ce4b
Revises: 9e4339213e4d
Create Date: 2026-03-07 10:00:14.201205

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0078f966ce4b"
down_revision: Union[str, Sequence[str], None] = "9e4339213e4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All 28 provider types (16 base + 12 split types)
ALL_PROVIDER_TYPES = (
    "'openai', 'dashscope', 'gemini', 'anthropic', 'groq', 'azure_openai', "
    "'cohere', 'mistral', 'bedrock', 'vertex', 'deepseek', 'minimax', "
    "'zai', 'kimi', 'ollama', 'lmstudio', "
    "'dashscope_coding', 'dashscope_embedding', 'dashscope_reranker', "
    "'kimi_coding', 'kimi_embedding', 'kimi_reranker', "
    "'minimax_coding', 'minimax_embedding', 'minimax_reranker', "
    "'zai_coding', 'zai_embedding', 'zai_reranker'"
)

# Original 16 base types only
OLD_PROVIDER_TYPES = (
    "'openai', 'dashscope', 'gemini', 'anthropic', 'groq', 'azure_openai', "
    "'cohere', 'mistral', 'bedrock', 'vertex', 'deepseek', 'minimax', "
    "'zai', 'kimi', 'ollama', 'lmstudio'"
)


def upgrade() -> None:
    """Make llm_model nullable and update provider_type CHECK constraint."""
    # 1. Make llm_model nullable (embedding/reranker providers don't need it)
    op.alter_column(
        "llm_providers",
        "llm_model",
        existing_type=sa.String(length=100),
        nullable=True,
    )

    # 2. Drop old CHECK constraint and add new one with all 28 provider types
    op.drop_constraint("llm_providers_valid_type", "llm_providers", type_="check")
    op.create_check_constraint(
        "llm_providers_valid_type",
        "llm_providers",
        f"provider_type IN ({ALL_PROVIDER_TYPES})",
    )


def downgrade() -> None:
    """Revert llm_model to NOT NULL and restore original CHECK constraint."""
    # 1. Revert CHECK constraint to original 16 types
    op.drop_constraint("llm_providers_valid_type", "llm_providers", type_="check")
    op.create_check_constraint(
        "llm_providers_valid_type",
        "llm_providers",
        f"provider_type IN ({OLD_PROVIDER_TYPES})",
    )

    # 2. Revert llm_model to NOT NULL (may fail if NULL values exist)
    op.alter_column(
        "llm_providers",
        "llm_model",
        existing_type=sa.String(length=100),
        nullable=False,
    )
