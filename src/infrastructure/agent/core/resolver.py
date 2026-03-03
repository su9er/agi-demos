"""
Resolver chain for SubAgent routing.

Provides a modular, pluggable resolution pipeline that replaces the
monolithic match logic in SubAgentRouter.  Each Resolver in the chain
attempts to find the best SubAgent for a query; the chain stops at the
first resolver that produces a result above the confidence threshold.

Architecture (inspired by oh-my-opencode resolver chain):

    ResolverChain
      -> KeywordResolver   (fast, exact)
      -> DescriptionResolver  (word-overlap fallback)
      -> [future: SemanticResolver, EmbeddingResolver, ...]

Usage::

    chain = ResolverChain([
        KeywordResolver(keyword_index, subagents),
        DescriptionResolver(subagents),
    ])
    match = chain.resolve(query, threshold=0.5)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from src.domain.model.agent.subagent import SubAgent

logger = logging.getLogger(__name__)


@dataclass
class ResolverResult:
    """Output of a single resolver attempt."""

    subagent: SubAgent | None
    confidence: float
    match_reason: str


class Resolver(ABC):
    """Protocol for a single resolution strategy.

    Implementations MUST be stateless with respect to individual queries
    (state such as keyword indexes built at construction time is fine).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable resolver name (used in logging / match_reason)."""

    @abstractmethod
    def resolve(
        self,
        query: str,
        threshold: float,
    ) -> ResolverResult:
        """Attempt to match *query* to a SubAgent.

        Args:
            query: User query or task description.
            threshold: Minimum confidence for a successful match.

        Returns:
            ResolverResult.  ``subagent`` is ``None`` when no match meets
            the threshold.
        """


class KeywordResolver(Resolver):
    """Matches queries against pre-indexed trigger keywords.

    Confidence is based on the fraction of a subagent's keywords that
    appear in the query, with a small boost for multi-keyword matches.
    """

    def __init__(
        self,
        keyword_index: dict[str, list[str]],
        subagents: dict[str, SubAgent],
    ) -> None:
        self._keyword_index = keyword_index
        self._subagents = subagents

    @property
    @override
    def name(self) -> str:
        return "keyword"

    @override
    def resolve(self, query: str, threshold: float) -> ResolverResult:
        query_lower = query.lower()
        query_words = set(query_lower.split())

        keyword_matches: dict[str, int] = {}
        for word in query_words:
            if word in self._keyword_index:
                for subagent_name in self._keyword_index[word]:
                    keyword_matches[subagent_name] = keyword_matches.get(subagent_name, 0) + 1

        if not keyword_matches:
            return ResolverResult(subagent=None, confidence=0.0, match_reason="no keyword hit")

        best_name = max(keyword_matches, key=lambda k: keyword_matches[k])
        best_count = keyword_matches[best_name]
        subagent = self._subagents.get(best_name)
        if subagent is None:
            return ResolverResult(subagent=None, confidence=0.0, match_reason="subagent removed")

        total_keywords = len(subagent.trigger.keywords)
        if total_keywords > 0:
            confidence = min(best_count / max(total_keywords, 3), 1.0)
            confidence = min(confidence + 0.1 * (best_count - 1), 0.95)
        else:
            confidence = 0.6

        if confidence < threshold:
            return ResolverResult(
                subagent=None,
                confidence=confidence,
                match_reason=f"Keyword below threshold ({confidence:.2f} < {threshold:.2f})",
            )

        return ResolverResult(
            subagent=subagent,
            confidence=confidence,
            match_reason=f"Keyword match: {best_count} keywords",
        )


class DescriptionResolver(Resolver):
    """Matches by word overlap between query and subagent trigger descriptions.

    Confidence is capped at 0.6 — intentionally lower than keyword matches
    so keyword-based routing always takes priority when both would match.
    """

    def __init__(self, subagents: dict[str, SubAgent]) -> None:
        self._subagents = subagents

    @property
    @override
    def name(self) -> str:
        return "description"

    @override
    def resolve(self, query: str, threshold: float) -> ResolverResult:
        query_words = set(query.lower().split())

        best_subagent: SubAgent | None = None
        best_overlap = 0
        best_confidence = 0.0

        for subagent in self._subagents.values():
            desc_words = set(subagent.trigger.description.lower().split())
            overlap = len(query_words & desc_words)
            if overlap >= 2:
                confidence = min(overlap / 5, 0.6)
                if confidence >= threshold and overlap > best_overlap:
                    best_subagent = subagent
                    best_overlap = overlap
                    best_confidence = confidence

        if best_subagent is None:
            return ResolverResult(
                subagent=None,
                confidence=0.0,
                match_reason="No description overlap",
            )

        return ResolverResult(
            subagent=best_subagent,
            confidence=best_confidence,
            match_reason=f"Description match: {best_overlap} words",
        )


class ResolverChain:
    """Ordered chain of :class:`Resolver` instances.

    The chain iterates resolvers in order and returns the first result
    whose confidence meets the threshold.  If no resolver produces a
    match, a *no match* result is returned.

    Args:
        resolvers: Ordered list of resolvers (first = highest priority).
    """

    def __init__(self, resolvers: list[Resolver]) -> None:
        if not resolvers:
            raise ValueError("ResolverChain requires at least one resolver")
        self._resolvers = list(resolvers)

    @property
    def resolvers(self) -> list[Resolver]:
        """Immutable view of the resolver list (for testing/inspection)."""
        return list(self._resolvers)

    def resolve(self, query: str, threshold: float) -> ResolverResult:
        """Run resolvers in order; return first match above *threshold*.

        Args:
            query: User query or task description.
            threshold: Minimum confidence for a successful match.

        Returns:
            ResolverResult from the first successful resolver, or a
            *no match* result.
        """
        for resolver in self._resolvers:
            result = resolver.resolve(query, threshold)
            if result.subagent is not None:
                logger.debug(
                    "ResolverChain: '%s' matched subagent '%s' (confidence=%.2f)",
                    resolver.name,
                    result.subagent.name,
                    result.confidence,
                )
                return result
            logger.debug(
                "ResolverChain: '%s' no match (%s)",
                resolver.name,
                result.match_reason,
            )

        return ResolverResult(
            subagent=None,
            confidence=0.0,
            match_reason="No match found",
        )

    def append(self, resolver: Resolver) -> None:
        """Append a resolver to the end of the chain.

        Useful for plugins or extensions that want to register custom
        resolution strategies at runtime.
        """
        self._resolvers.append(resolver)

    def prepend(self, resolver: Resolver) -> None:
        """Prepend a resolver to the start of the chain.

        This gives the new resolver highest priority.
        """
        self._resolvers.insert(0, resolver)
