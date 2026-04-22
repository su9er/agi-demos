"""Goal contract value object for autonomous conversations (Track B, P2-3 phase-2).

The contract expresses what the user wants, how much budget is allowed, and
WHICH categories of side-effect MUST block for human approval. It intentionally
uses **prose** ``operator_guidance`` instead of a ``dict`` fallback-policy
lookup, because fallback policy is a subjective decision — per the Agent First
rule in AGENTS.md, such decisions must be made by an agent via a tool-call,
not by a dict lookup masquerading as a policy engine.

Deterministic fields (allowed by Agent First):
- ``primary_goal``      : user's literal goal text; no NLP.
- ``blocking_categories``: set-membership check against ``tool.side_effects``.
- ``budget``            : arithmetic counters.

Subjective guidance (consumed by the coordinator agent, not a lookup table):
- ``operator_guidance`` : free-form prose injected into coordinator system
                           prompt; the agent judges how to apply it per
                           situation via structured tool-calls.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoalBudget:
    """Hard budget counters checked by arithmetic (Agent First: deterministic).

    ``None`` means unbounded for that axis.
    """

    max_turns: int | None = None
    max_usd: float | None = None
    max_wall_seconds: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("max_turns", self.max_turns),
            ("max_wall_seconds", self.max_wall_seconds),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"GoalBudget.{name} must be positive, got {value}")
        if self.max_usd is not None and self.max_usd <= 0:
            raise ValueError(f"GoalBudget.max_usd must be positive, got {self.max_usd}")


@dataclass(frozen=True)
class GoalContract:
    """Contract describing an autonomous conversation's goal + guardrails.

    Invariants:
    - ``primary_goal`` is non-empty.
    - ``blocking_categories`` are lowercase slugs (e.g. ``{"payment", "delete"}``)
      matched by set intersection against ``tool.side_effects`` at runtime —
      this is a deterministic protocol upgrade, not a subjective decision.
    - ``operator_guidance`` is prose; it is NEVER pattern-matched / regex-parsed.
    """

    primary_goal: str
    blocking_categories: frozenset[str] = field(default_factory=frozenset)
    operator_guidance: str = ""
    budget: GoalBudget = field(default_factory=GoalBudget)
    supervisor_tick_seconds: int = 120

    def __post_init__(self) -> None:
        if not self.primary_goal or not self.primary_goal.strip():
            raise ValueError("GoalContract.primary_goal must be non-empty")
        if self.supervisor_tick_seconds <= 0:
            raise ValueError(
                "GoalContract.supervisor_tick_seconds must be positive, "
                f"got {self.supervisor_tick_seconds}"
            )
        # Normalize blocking_categories lazily without breaking frozen=True.
        normalized = frozenset(
            category.strip().lower()
            for category in self.blocking_categories
            if category and category.strip()
        )
        object.__setattr__(self, "blocking_categories", normalized)

    def is_side_effect_blocking(self, tool_side_effects: frozenset[str] | set[str]) -> bool:
        """Protocol check: do any of the tool's declared side-effects intersect
        ``blocking_categories``? Pure set-membership — Agent First compliant.
        """
        if not tool_side_effects:
            return False
        return bool(self.blocking_categories & frozenset(tool_side_effects))

    def to_dict(self) -> dict[str, object]:
        return {
            "primary_goal": self.primary_goal,
            "blocking_categories": sorted(self.blocking_categories),
            "operator_guidance": self.operator_guidance,
            "budget": {
                "max_turns": self.budget.max_turns,
                "max_usd": self.budget.max_usd,
                "max_wall_seconds": self.budget.max_wall_seconds,
            },
            "supervisor_tick_seconds": self.supervisor_tick_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "GoalContract":
        budget_raw = data.get("budget") or {}
        assert isinstance(budget_raw, dict)
        budget = GoalBudget(
            max_turns=budget_raw.get("max_turns"),  # type: ignore[arg-type]
            max_usd=budget_raw.get("max_usd"),  # type: ignore[arg-type]
            max_wall_seconds=budget_raw.get("max_wall_seconds"),  # type: ignore[arg-type]
        )
        categories_raw = data.get("blocking_categories") or []
        assert isinstance(categories_raw, list | tuple | set | frozenset)
        return cls(
            primary_goal=str(data["primary_goal"]),
            blocking_categories=frozenset(str(c) for c in categories_raw),
            operator_guidance=str(data.get("operator_guidance") or ""),
            budget=budget,
            supervisor_tick_seconds=int(data.get("supervisor_tick_seconds", 120)),  # type: ignore[arg-type]
        )
