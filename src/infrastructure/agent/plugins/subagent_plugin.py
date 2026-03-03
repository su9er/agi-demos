"""Sub-agent plugin protocol and convenience base class.

This module defines the ``SubAgentPlugin`` protocol -- a specialised variant
of ``AgentPlugin`` that guides plugin authors toward sub-agent extension
points.

Usage example
-------------

.. code-block:: python

    from src.infrastructure.agent.plugins.subagent_plugin import SubAgentPluginBase
    from src.infrastructure.agent.plugins.runtime_api import PluginRuntimeApi
    from src.infrastructure.agent.plugins.registry import SubAgentResolverBuildContext
    from src.infrastructure.agent.core.resolver import Resolver, ResolverResult


    class MyResolver(Resolver):
        @property
        def name(self) -> str:
            return "my-resolver"

        def resolve(self, query: str, threshold: float = 0.5) -> ResolverResult:
            ...


    class MySubAgentPlugin(SubAgentPluginBase):
        name = "my-subagent-plugin"

        def setup(self, api: PluginRuntimeApi) -> None:
            # Register custom resolver
            api.register_subagent_resolver_factory(self._make_resolver)

            # Register lifecycle hooks
            api.register_hook("before_subagent_spawn", self._on_before_spawn)
            api.register_hook("after_subagent_complete", self._on_after_complete)

        def _make_resolver(self, ctx: SubAgentResolverBuildContext) -> Resolver:
            return MyResolver()

        async def _on_before_spawn(self, payload: ...) -> None:
            ...

        async def _on_after_complete(self, payload: ...) -> None:
            ...


Well-Known Sub-Agent Hooks
--------------------------

These hook names are invoked by the ``SubAgentSessionRunner`` at specific
lifecycle points.  Plugins register handlers via
``api.register_hook(hook_name, handler)``.

+----------------------------+----------------------------------------------+
| Hook name                  | When it fires                                |
+============================+==============================================+
| ``before_subagent_spawn``  | Before a SubAgent session is created.        |
|                            | Payload includes conversation_id, run_id,    |
|                            | subagent_name, spawn_mode, model_override.   |
+----------------------------+----------------------------------------------+
| ``after_subagent_spawn``   | After a SubAgent session is spawned or       |
|                            | started (both ``subagent_spawned`` and       |
|                            | ``subagent_started`` events map here).       |
+----------------------------+----------------------------------------------+
| ``before_subagent_complete``| (reserved) Before SubAgent result is         |
|                            | finalised. Not yet emitted by core.          |
+----------------------------+----------------------------------------------+
| ``after_subagent_complete``| After a SubAgent finishes (success, failure, |
|                            | or timeout). Payload includes status,        |
|                            | summary, error, execution_time_ms.           |
+----------------------------+----------------------------------------------+
| ``on_subagent_doom_loop``  | When doom-loop detection triggers for a      |
|                            | SubAgent. Payload includes reason,           |
|                            | threshold.                                   |
+----------------------------+----------------------------------------------+
| ``on_subagent_routed``     | After a query is matched to a SubAgent.      |
|                            | Payload includes subagent_name, confidence,  |
|                            | match_reason.                                |
+----------------------------+----------------------------------------------+

Resolver Factory Registration
-----------------------------

Plugins may register a ``SubAgentResolverFactory`` via
``api.register_subagent_resolver_factory(factory)``.  The factory is invoked
once during ``SubAgentRouter`` initialisation and must return a ``Resolver``
instance.  The resolver is appended to the ``ResolverChain`` so it runs after
built-in resolvers (keyword, description) but can still contribute matches.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from .runtime_api import PluginRuntimeApi


@runtime_checkable
class SubAgentPlugin(Protocol):
    """Protocol for plugins that extend the sub-agent subsystem.

    Identical to ``AgentPlugin`` in shape but serves as documentation
    and type guidance for sub-agent-focused extensions.
    """

    name: str

    def setup(self, api: PluginRuntimeApi) -> object:
        """Register sub-agent hooks, resolver factories, and other extensions."""
        ...


class SubAgentPluginBase:
    """Convenience base class implementing ``SubAgentPlugin``.

    Provides no-op defaults for common lifecycle hooks so subclasses
    only need to override what they care about.
    """

    name: str = ""

    def setup(self, api: PluginRuntimeApi) -> None:
        """Override to register hooks, resolver factories, etc."""

    async def on_before_spawn(self, payload: Mapping[str, object]) -> None:
        """Called before a SubAgent session is created."""

    async def on_after_spawn(self, payload: Mapping[str, object]) -> None:
        """Called after a SubAgent session is spawned / started."""

    async def on_after_complete(self, payload: Mapping[str, object]) -> None:
        """Called after a SubAgent finishes (success / failure / timeout)."""

    async def on_doom_loop(self, payload: Mapping[str, object]) -> None:
        """Called when doom-loop detection triggers for a SubAgent."""

    async def on_routed(self, payload: Mapping[str, object]) -> None:
        """Called after a query is matched to a SubAgent."""
