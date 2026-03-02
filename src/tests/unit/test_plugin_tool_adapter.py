"""Unit tests for plugin_tool_adapter: adapt_plugin_tool, helpers."""

from unittest.mock import MagicMock

import pytest

from src.infrastructure.agent.core.plugin_tool_adapter import (
    _find_callable,
    _introspect_callable_parameters,
    _normalize_result,
    adapt_plugin_tool,
)
from src.infrastructure.agent.tools.define import ToolInfo
from src.infrastructure.agent.tools.result import ToolResult

# ---------------------------------------------------------------------------
# _find_callable
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindCallable:
    """Tests for _find_callable helper."""

    def test_finds_execute_method(self) -> None:
        obj = MagicMock()
        obj.execute = lambda **kw: "ok"
        result = _find_callable(obj)
        assert result is obj.execute

    def test_finds_call_method(self) -> None:
        class CallableTool:
            def __call__(self, **kw):  # type: ignore[no-untyped-def]
                return "called"

        obj = CallableTool()
        result = _find_callable(obj)
        assert result is not None
        assert callable(result)

    def test_prefers_execute_over_run(self) -> None:
        """execute has higher priority than run in _CALLABLE_CANDIDATES."""

        class Tool:
            def execute(self, **kw):  # type: ignore[no-untyped-def]
                return "execute"

            def run(self, **kw):  # type: ignore[no-untyped-def]
                return "run"

        obj = Tool()
        result = _find_callable(obj)
        assert result() == "execute"  # preferred over run()

    def test_finds_ainvoke(self) -> None:
        obj = MagicMock()
        obj.execute = None  # not callable
        obj.ainvoke = lambda **kw: "async"
        # MagicMock auto-creates attributes; override execute to be None
        del obj.execute
        obj.execute = None  # set to non-callable
        result = _find_callable(obj)
        # Since execute is not None but also not callable (it's None which isn't callable),
        # it moves on to ainvoke
        assert result is not None

    def test_returns_none_when_no_callable(self) -> None:
        class Empty:
            pass

        obj = Empty()
        result = _find_callable(obj)
        assert result is None

    def test_returns_none_for_non_callable_attributes(self) -> None:
        """Attributes that exist but are not callable should be skipped."""

        class Tool:
            execute = "not callable"
            run = 42

        obj = Tool()
        result = _find_callable(obj)
        assert result is None


# ---------------------------------------------------------------------------
# _normalize_result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNormalizeResult:
    """Tests for _normalize_result helper."""

    def test_toolresult_passthrough(self) -> None:
        """ToolResult input is returned as-is."""
        original = ToolResult(output="already structured")
        result = _normalize_result(original, "t")
        assert result is original

    def test_dict_success(self) -> None:
        """Successful dict is JSON-serialized."""
        result = _normalize_result({"key": "value", "count": 42}, "t")
        assert '"key"' in result.output
        assert '"value"' in result.output
        assert result.is_error is False

    def test_dict_error_status(self) -> None:
        """Dict with status=error is flagged as error."""
        result = _normalize_result({"status": "error", "error": "boom"}, "t")
        assert result.is_error is True
        assert "boom" in result.output

    def test_dict_error_message_fallback(self) -> None:
        """Dict with status=error uses message if error key missing."""
        result = _normalize_result({"status": "error", "message": "oops"}, "t")
        assert result.is_error is True
        assert "oops" in result.output

    def test_dict_error_fallback_to_str(self) -> None:
        """Dict with status=error and no error/message keys uses str(dict)."""
        result = _normalize_result({"status": "error"}, "t")
        assert result.is_error is True

    def test_string_input(self) -> None:
        """String input is wrapped directly."""
        result = _normalize_result("plain text", "t")
        assert result.output == "plain text"
        assert result.is_error is False

    def test_other_type_stringified(self) -> None:
        """Non-str, non-dict, non-ToolResult is stringified."""
        result = _normalize_result(12345, "t")
        assert result.output == "12345"
        assert result.is_error is False

    def test_none_stringified(self) -> None:
        """None is stringified."""
        result = _normalize_result(None, "t")
        assert result.output == "None"

    def test_dict_non_serializable_falls_back_to_str(self) -> None:
        """Dict with non-JSON-serializable values falls back to str()."""

        class Custom:
            def __repr__(self) -> str:
                return "Custom()"

        result = _normalize_result({"obj": Custom()}, "t")
        assert isinstance(result.output, str)
        assert result.is_error is False


# ---------------------------------------------------------------------------
# _introspect_callable_parameters
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntrospectCallableParameters:
    """Tests for _introspect_callable_parameters."""

    def test_no_callable_returns_empty_schema(self) -> None:
        class Empty:
            pass

        result = _introspect_callable_parameters(Empty(), "t")
        assert result["type"] == "object"
        assert result["properties"] == {}
        assert result["required"] == []

    def test_typed_parameters(self) -> None:
        """Typed parameters are mapped to JSON Schema types."""

        class Tool:
            def execute(self, name: str, count: int, flag: bool) -> str:
                return ""

        result = _introspect_callable_parameters(Tool(), "t")
        assert result["properties"]["name"]["type"] == "string"
        assert result["properties"]["count"]["type"] == "integer"
        assert result["properties"]["flag"]["type"] == "boolean"
        assert "name" in result["required"]
        assert "count" in result["required"]
        assert "flag" in result["required"]

    def test_skips_self_and_ctx(self) -> None:
        """self, ctx, context, kwargs, args are skipped."""

        class Tool:
            def execute(self, ctx: str, query: str) -> str:
                return ""

        result = _introspect_callable_parameters(Tool(), "t")
        assert "self" not in result["properties"]
        assert "ctx" not in result["properties"]
        assert "query" in result["properties"]

    def test_default_values_not_required(self) -> None:
        """Parameters with defaults are not in required list."""

        class Tool:
            def execute(self, query: str, limit: int = 10) -> str:
                return ""

        result = _introspect_callable_parameters(Tool(), "t")
        assert "query" in result["required"]
        assert "limit" not in result["required"]
        assert result["properties"]["limit"]["default"] == 10

    def test_unannotated_defaults_to_string(self) -> None:
        """Parameters without type annotation default to string."""

        class Tool:
            def execute(self, data) -> str:  # type: ignore[no-untyped-def]
                return ""

        result = _introspect_callable_parameters(Tool(), "t")
        assert result["properties"]["data"]["type"] == "string"

    def test_float_and_list_types(self) -> None:
        """float maps to number, list maps to array."""

        class Tool:
            def execute(self, score: float, items: list) -> str:  # type: ignore[type-arg]
                return ""

        result = _introspect_callable_parameters(Tool(), "t")
        assert result["properties"]["score"]["type"] == "number"
        assert result["properties"]["items"]["type"] == "array"

    def test_dict_type(self) -> None:
        """dict maps to object."""

        class Tool:
            def execute(self, config: dict) -> str:  # type: ignore[type-arg]
                return ""

        result = _introspect_callable_parameters(Tool(), "t")
        assert result["properties"]["config"]["type"] == "object"

    def test_var_positional_and_keyword_skipped(self) -> None:
        """*args and **kwargs are skipped."""

        class Tool:
            def execute(self, query: str, *args: str, **kwargs: str) -> str:
                return ""

        result = _introspect_callable_parameters(Tool(), "t")
        assert "query" in result["properties"]
        assert "args" not in result["properties"]
        assert "kwargs" not in result["properties"]

    def test_none_default_not_added(self) -> None:
        """Parameters with None default don't get a default entry."""

        class Tool:
            def execute(self, data: str | None = None) -> str:  # type: ignore[assignment]
                return ""

        result = _introspect_callable_parameters(Tool(), "t")
        assert "default" not in result["properties"]["data"]
        assert "data" not in result["required"]


# ---------------------------------------------------------------------------
# adapt_plugin_tool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAdaptPluginTool:
    """Tests for adapt_plugin_tool main function."""

    def test_toolinfo_passthrough(self) -> None:
        """ToolInfo input is returned as-is."""

        async def noop(**kw):  # type: ignore[no-untyped-def]
            return ToolResult(output="x")

        original = ToolInfo(
            name="existing",
            description="Already a ToolInfo",
            parameters={},
            execute=noop,
        )
        result = adapt_plugin_tool("existing", original, "test-plugin")
        assert result is original

    def test_with_execute_method(self) -> None:
        """Object with execute method is adapted into ToolInfo."""

        class Tool:
            description = "My tool"

            def execute(self, query: str) -> str:
                return f"result: {query}"

        result = adapt_plugin_tool("my_tool", Tool(), "test-plugin")
        assert result is not None
        assert isinstance(result, ToolInfo)
        assert result.name == "my_tool"
        assert result.description == "My tool"
        assert result.category == "plugin"
        assert "plugin" in result.tags
        assert "test-plugin" in result.tags

    def test_with_call_method(self) -> None:
        """Object with __call__ is adapted."""

        class Tool:
            def __call__(self, **kw):  # type: ignore[no-untyped-def]
                return "called"

        result = adapt_plugin_tool("call_tool", Tool(), "test-plugin")
        assert result is not None
        assert result.name == "call_tool"

    def test_no_callable_returns_none(self) -> None:
        """Object with no callable method returns None."""

        class Empty:
            pass

        result = adapt_plugin_tool("empty", Empty(), "test-plugin")
        assert result is None

    def test_default_description(self) -> None:
        """When no description attribute, uses default."""

        class Tool:
            def execute(self) -> str:
                return ""

        result = adapt_plugin_tool("nodesc", Tool(), "test-plugin")
        assert result is not None
        assert "nodesc" in result.description

    def test_uses_get_parameters_schema(self) -> None:
        """Parameters schema from get_parameters_schema() is preferred."""
        schema = {"type": "object", "properties": {"q": {"type": "string"}}}

        class Tool:
            def get_parameters_schema(self):  # type: ignore[no-untyped-def]
                return schema

            def execute(self, q: str) -> str:
                return q

        result = adapt_plugin_tool("schema_tool", Tool(), "test-plugin")
        assert result is not None
        assert result.parameters == schema

    def test_uses_parameters_attribute(self) -> None:
        """Falls back to parameters attribute if no get_parameters_schema."""
        params = {"type": "object", "properties": {"x": {"type": "integer"}}}

        class Tool:
            parameters = params

            def execute(self, x: int) -> str:
                return str(x)

        result = adapt_plugin_tool("param_tool", Tool(), "test-plugin")
        assert result is not None
        assert result.parameters == params

    def test_introspects_parameters_when_none_provided(self) -> None:
        """When no explicit schema, introspects callable signature."""

        class Tool:
            def execute(self, query: str, limit: int = 5) -> str:
                return ""

        result = adapt_plugin_tool("intro_tool", Tool(), "test-plugin")
        assert result is not None
        assert "query" in result.parameters.get("properties", {})

    def test_permission_attribute_carried_over(self) -> None:
        """Permission from tool object is carried to ToolInfo."""

        class Tool:
            permission = "write"

            def execute(self) -> str:
                return ""

        result = adapt_plugin_tool("perm_tool", Tool(), "test-plugin")
        assert result is not None
        assert result.permission == "write"

    async def test_adapted_execute_returns_toolresult(self) -> None:
        """Adapted execute wraps return value in ToolResult."""

        class Tool:
            def execute(self, query: str = "default") -> str:
                return f"answer: {query}"

        adapted = adapt_plugin_tool("exec_tool", Tool(), "test-plugin")
        assert adapted is not None
        result = await adapted.execute(query="hello")
        assert isinstance(result, ToolResult)
        assert "answer: hello" in result.output
        assert result.is_error is False

    async def test_adapted_execute_normalizes_dict(self) -> None:
        """Dict return from callable is normalized to ToolResult."""

        class Tool:
            def execute(self, **kw):  # type: ignore[no-untyped-def]
                return {"status": "ok", "data": 42}

        adapted = adapt_plugin_tool("dict_tool", Tool(), "test-plugin")
        assert adapted is not None
        result = await adapted.execute()
        assert isinstance(result, ToolResult)
        assert result.is_error is False
        assert "42" in result.output

    async def test_adapted_execute_handles_exception(self) -> None:
        """Exception from callable is caught and returned as error ToolResult."""

        class Tool:
            def execute(self, **kw):  # type: ignore[no-untyped-def]
                raise ValueError("broken")

        adapted = adapt_plugin_tool("err_tool", Tool(), "test-plugin")
        assert adapted is not None
        result = await adapted.execute()
        assert isinstance(result, ToolResult)
        assert result.is_error is True
        assert "broken" in result.output

    async def test_adapted_execute_handles_async_callable(self) -> None:
        """Async callable is awaited properly."""

        class Tool:
            async def execute(self, msg: str = "hi") -> str:
                return f"async: {msg}"

        adapted = adapt_plugin_tool("async_tool", Tool(), "test-plugin")
        assert adapted is not None
        result = await adapted.execute(msg="world")
        assert isinstance(result, ToolResult)
        assert "async: world" in result.output

    async def test_adapted_execute_ignores_ctx_parameter(self) -> None:
        """The adapted execute doesn't forward ctx to the plugin callable."""

        class Tool:
            def execute(self, query: str = "test") -> str:
                return query

        adapted = adapt_plugin_tool("ctx_tool", Tool(), "test-plugin")
        assert adapted is not None
        # The adapted execute accepts ctx as first arg but ignores it
        result = await adapted.execute(ctx=None, query="hello")
        assert isinstance(result, ToolResult)
        assert result.output == "hello"
