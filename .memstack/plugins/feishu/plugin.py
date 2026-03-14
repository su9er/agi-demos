from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from src.infrastructure.agent.plugins.registry import ChannelAdapterBuildContext
from src.infrastructure.agent.plugins.runtime_api import PluginRuntimeApi

_PLUGIN_DIR = Path(__file__).resolve().parent


def _load_sibling(module_file: str) -> ModuleType:
    file_path = _PLUGIN_DIR / module_file
    module_name = f"feishu_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load sibling module: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FeishuChannelPlugin:
    name = "feishu-channel-plugin"

    def setup(self, api: PluginRuntimeApi) -> None:

        _adapter_mod = _load_sibling("adapter.py")
        FeishuAdapter = _adapter_mod.FeishuAdapter  # noqa: N806

        def _factory(context: ChannelAdapterBuildContext) -> object:
            return FeishuAdapter(context.channel_config)

        api.register_channel_type(
            "feishu",
            _factory,
            config_schema={
                "type": "object",
                "properties": {
                    "app_id": {"type": "string", "title": "App ID", "minLength": 1},
                    "app_secret": {"type": "string", "title": "App Secret", "minLength": 1},
                    "encrypt_key": {"type": "string", "title": "Encrypt Key"},
                    "verification_token": {"type": "string", "title": "Verification Token"},
                    "domain": {"type": "string", "title": "Domain", "default": "feishu"},
                    "connection_mode": {
                        "type": "string",
                        "title": "Connection Mode",
                        "enum": ["websocket", "webhook"],
                        "default": "websocket",
                    },
                    "webhook_url": {"type": "string", "title": "Webhook URL"},
                    "webhook_port": {
                        "type": "integer",
                        "title": "Webhook Port",
                        "minimum": 1,
                        "maximum": 65535,
                    },
                    "webhook_path": {"type": "string", "title": "Webhook Path"},
                },
                "required": ["app_id", "app_secret"],
                "additionalProperties": False,
            },
            config_ui_hints={
                "app_secret": {"sensitive": True},
                "encrypt_key": {"sensitive": True, "advanced": True},
                "verification_token": {"sensitive": True, "advanced": True},
                "webhook_port": {"advanced": True},
                "webhook_path": {"advanced": True},
            },
            defaults={
                "domain": "feishu",
                "connection_mode": "websocket",
                "webhook_path": "/api/v1/channels/events/feishu",
                "webhook_port": 8000,
            },
            secret_paths=["app_secret", "encrypt_key", "verification_token"],
        )


plugin = FeishuChannelPlugin()
