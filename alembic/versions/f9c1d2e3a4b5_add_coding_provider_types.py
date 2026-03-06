"""add_provider_role_types

Revision ID: f9c1d2e3a4b5
Revises: ef799f3b2564
Create Date: 2026-03-06 08:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9c1d2e3a4b5"
down_revision: str | Sequence[str] | None = "ef799f3b2564"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "llm_providers" not in inspector.get_table_names():
        return

    op.execute("ALTER TABLE llm_providers DROP CONSTRAINT IF EXISTS llm_providers_valid_type")
    op.execute(
        """
        ALTER TABLE llm_providers
        ADD CONSTRAINT llm_providers_valid_type
        CHECK (
            provider_type IN (
                'openai', 'dashscope', 'dashscope_coding', 'gemini', 'anthropic', 'groq',
                'dashscope_embedding', 'dashscope_reranker', 'azure_openai', 'cohere',
                'mistral', 'bedrock', 'vertex', 'deepseek', 'minimax', 'minimax_coding',
                'minimax_embedding', 'minimax_reranker', 'zai', 'zai_coding',
                'zai_embedding', 'zai_reranker', 'kimi', 'kimi_coding', 'kimi_embedding',
                'kimi_reranker', 'ollama', 'lmstudio'
            )
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "llm_providers" not in inspector.get_table_names():
        return

    op.execute("ALTER TABLE llm_providers DROP CONSTRAINT IF EXISTS llm_providers_valid_type")
    op.execute(
        """
        ALTER TABLE llm_providers
        ADD CONSTRAINT llm_providers_valid_type
        CHECK (
            provider_type IN (
                'openai', 'dashscope', 'gemini', 'anthropic', 'groq',
                'azure_openai', 'cohere', 'mistral', 'bedrock', 'vertex',
                'deepseek', 'minimax', 'zai', 'kimi', 'ollama', 'lmstudio'
            )
        )
        """
    )
