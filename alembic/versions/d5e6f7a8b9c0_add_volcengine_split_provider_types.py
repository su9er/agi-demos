"""add_volcengine_split_provider_types

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-10 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALL_PROVIDER_TYPES_WITH_VOLCENGINE_SPLIT = (
    "'openai', 'openrouter', 'dashscope', 'gemini', 'anthropic', 'groq', 'azure_openai', "
    "'cohere', 'mistral', 'bedrock', 'vertex', 'deepseek', 'minimax', "
    "'zai', 'kimi', 'volcengine', 'ollama', 'lmstudio', "
    "'dashscope_coding', 'dashscope_embedding', 'dashscope_reranker', "
    "'kimi_coding', 'kimi_embedding', 'kimi_reranker', "
    "'minimax_coding', 'minimax_embedding', 'minimax_reranker', "
    "'zai_coding', 'zai_embedding', 'zai_reranker', "
    "'volcengine_coding', 'volcengine_embedding', 'volcengine_reranker'"
)

PREVIOUS_PROVIDER_TYPES = (
    "'openai', 'openrouter', 'dashscope', 'gemini', 'anthropic', 'groq', 'azure_openai', "
    "'cohere', 'mistral', 'bedrock', 'vertex', 'deepseek', 'minimax', "
    "'zai', 'kimi', 'volcengine', 'ollama', 'lmstudio', "
    "'dashscope_coding', 'dashscope_embedding', 'dashscope_reranker', "
    "'kimi_coding', 'kimi_embedding', 'kimi_reranker', "
    "'minimax_coding', 'minimax_embedding', 'minimax_reranker', "
    "'zai_coding', 'zai_embedding', 'zai_reranker'"
)


def upgrade() -> None:
    op.drop_constraint("llm_providers_valid_type", "llm_providers", type_="check")
    op.create_check_constraint(
        "llm_providers_valid_type",
        "llm_providers",
        f"provider_type IN ({ALL_PROVIDER_TYPES_WITH_VOLCENGINE_SPLIT})",
    )


def downgrade() -> None:
    op.drop_constraint("llm_providers_valid_type", "llm_providers", type_="check")
    op.create_check_constraint(
        "llm_providers_valid_type",
        "llm_providers",
        f"provider_type IN ({PREVIOUS_PROVIDER_TYPES})",
    )
