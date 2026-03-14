"""Enhanced Feishu channels usage examples.

This module demonstrates the full capabilities of the Feishu channel integration.
"""

import asyncio
import contextlib
import os
from typing import Any

from src.application.services.channels import ChannelService
from src.domain.model.channels import ChannelConfig
from src.infrastructure.adapters.secondary.channels.channel_plugin_loader import (
    load_channel_module,
)

_adapter_mod = load_channel_module("feishu", "adapter")
_client_mod = load_channel_module("feishu", "client")
_cards_mod = load_channel_module("feishu", "cards")

CardBuilder = _cards_mod.CardBuilder
FeishuAdapter = _adapter_mod.FeishuAdapter
FeishuClient = _client_mod.FeishuClient
PostBuilder = _cards_mod.PostBuilder
send_feishu_card = _client_mod.send_feishu_card
send_feishu_text = _client_mod.send_feishu_text


async def basic_messaging_example() -> None:
    """Basic messaging example."""
    app_id = os.getenv("FEISHU_APP_ID", "cli_xxx")
    app_secret = os.getenv("FEISHU_APP_SECRET", "xxx")
    chat_id = "oc_xxx"  # Replace with actual chat ID

    client = FeishuClient(app_id, app_secret)

    # Send text message
    message_id = await client.send_text_message(chat_id, "Hello from AGI-Demos!")
    print(f"Sent message: {message_id}")

    # Send markdown card
    await client.send_markdown_card(
        to=chat_id,
        content="# 🎉 欢迎使用 AGI-Demos\n\n这是 **Markdown** 卡片消息。\n\n- 支持列表\n- 支持代码块\n- 支持表格",
        title="欢迎使用",
    )

    # Send rich text post
    post = PostBuilder(title="公告")
    post.add_text("大家好！").add_link("点击查看详情", "https://example.com")
    await client.send_card_message(chat_id, post.build())


async def media_example() -> None:
    """Media upload and send example."""
    app_id = os.getenv("FEISHU_APP_ID", "cli_xxx")
    app_secret = os.getenv("FEISHU_APP_SECRET", "xxx")
    _chat_id = "oc_xxx"

    _client = FeishuClient(app_id, app_secret)

    # Upload and send image
    # image_key = await client.media.upload_image("/path/to/image.png")
    # await client.send_image_message(chat_id, image_key)

    # Upload and send file
    # file_key = await client.media.upload_file(
    #     file=b"file content here",
    #     file_name="document.pdf"
    # )
    # await client.send_file_message(chat_id, file_key)

    print("Media example commented out - provide actual files to test")


async def document_example() -> None:
    """Document operations example."""
    app_id = os.getenv("FEISHU_APP_ID", "cli_xxx")
    app_secret = os.getenv("FEISHU_APP_SECRET", "xxx")

    client = FeishuClient(app_id, app_secret)

    # Create document
    doc = await client.docs.create_document("项目文档")
    doc_token = doc["document_token"]
    print(f"Created document: {doc_token}")

    # Create heading block
    await client.docs.create_block(
        doc_token,
        parent_block_id=doc_token,
        block_type=3,  # Heading 1
        content={"heading1": {"content": [{"text": "项目概述"}]}},
    )

    # Create text block
    await client.docs.create_block(
        doc_token,
        parent_block_id=doc_token,
        block_type=2,  # Text
        content={"text": {"content": "这是一个项目文档。"}},
    )

    # Get document content
    content = await client.docs.get_document_content(doc_token)
    print(f"Document content length: {len(content)}")


async def wiki_example() -> None:
    """Wiki operations example."""
    app_id = os.getenv("FEISHU_APP_ID", "cli_xxx")
    app_secret = os.getenv("FEISHU_APP_SECRET", "xxx")

    client = FeishuClient(app_id, app_secret)

    # List wiki spaces
    spaces = await client.wiki.list_spaces()
    print(f"Found {len(spaces)} wiki spaces")

    if spaces:
        space_id = spaces[0]["space_id"]

        # List nodes
        nodes = await client.wiki.list_nodes(space_id)
        print(f"Found {len(nodes)} nodes in space")

        # Create new node
        node = await client.wiki.create_node(
            space_id=space_id, title="新知识页面", node_type="docx"
        )
        print(f"Created node: {node['node_token']}")


async def drive_example() -> None:
    """Drive operations example."""
    app_id = os.getenv("FEISHU_APP_ID", "cli_xxx")
    app_secret = os.getenv("FEISHU_APP_SECRET", "xxx")

    client = FeishuClient(app_id, app_secret)

    # Create folder
    folder_token = await client.drive.create_folder("项目资料")
    print(f"Created folder: {folder_token}")

    # List files in folder
    files = await client.drive.list_files(folder_token)
    print(f"Found {len(files)} files in folder")

    # Search files
    results = await client.drive.search_files("合同")
    print(f"Found {len(results)} matching files")


async def bitable_example() -> None:
    """Bitable operations example."""
    app_id = os.getenv("FEISHU_APP_ID", "cli_xxx")
    app_secret = os.getenv("FEISHU_APP_SECRET", "xxx")

    client = FeishuClient(app_id, app_secret)

    # Create Bitable app
    app_token = await client.bitable.create_app("任务管理")
    print(f"Created Bitable: {app_token}")

    # Create table
    table_id = await client.bitable.create_table(app_token, "任务列表")
    print(f"Created table: {table_id}")

    # Create fields
    _bitable_mod = load_channel_module("feishu", "bitable")
    FIELD_TYPE_SINGLE_SELECT = _bitable_mod.FIELD_TYPE_SINGLE_SELECT
    FIELD_TYPE_TEXT = _bitable_mod.FIELD_TYPE_TEXT

    _name_field = await client.bitable.create_field(
        app_token, table_id, field_name="任务名称", field_type=FIELD_TYPE_TEXT
    )

    _status_field = await client.bitable.create_field(
        app_token,
        table_id,
        field_name="状态",
        field_type=FIELD_TYPE_SINGLE_SELECT,
        property={
            "options": [
                {"name": "待处理", "color": 0},
                {"name": "进行中", "color": 1},
                {"name": "已完成", "color": 2},
            ]
        },
    )

    # Create record
    record_id = await client.bitable.create_record(
        app_token,
        table_id,
        fields={
            "任务名称": "完成飞书集成",
            "状态": "已完成",
        },
    )
    print(f"Created record: {record_id}")

    # List records
    records = await client.bitable.list_records(app_token, table_id)
    print(f"Found {len(records)} records")


async def card_builder_example() -> None:
    """Card builder examples."""
    chat_id = "oc_xxx"
    app_id = os.getenv("FEISHU_APP_ID", "cli_xxx")
    app_secret = os.getenv("FEISHU_APP_SECRET", "xxx")

    client = FeishuClient(app_id, app_secret)

    # Simple markdown card
    card1 = CardBuilder.create_markdown_card(
        content="# 部署成功\n\n项目已部署到生产环境。", title="部署通知"
    )
    await client.send_card_message(chat_id, card1)

    # Info card with actions
    card2 = CardBuilder.create_info_card(
        title="系统状态",
        content=[
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "**状态**: ✅ 正常\n**版本**: v1.0.0"},
            },
            CardBuilder.create_divider(),
            {"tag": "div", "text": {"tag": "lark_md", "content": "**CPU**: 45%\n**内存**: 60%"}},
        ],
        actions=[
            CardBuilder.create_button(
                "查看详情", url="https://example.com/dashboard", button_type="primary"
            ),
            CardBuilder.create_button("设置", url="https://example.com/settings"),
        ],
    )
    await client.send_card_message(chat_id, card2)

    # Table card
    card3 = CardBuilder.create_table_card(
        title="销售报表",
        headers=["产品", "销量", "金额"],
        rows=[
            ["产品A", "100", "¥10,000"],
            ["产品B", "200", "¥20,000"],
            ["产品C", "150", "¥15,000"],
        ],
    )
    await client.send_card_message(chat_id, card3)

    # Note cards
    await client.send_card_message(
        chat_id, CardBuilder.create_note_card("提示", "这是一条提示信息", "info")
    )
    await client.send_card_message(
        chat_id, CardBuilder.create_note_card("警告", "这是一条警告信息", "warning")
    )
    await client.send_card_message(
        chat_id, CardBuilder.create_note_card("错误", "这是一条错误信息", "danger")
    )


async def channel_service_example() -> None:
    """Channel service integration example."""
    service = ChannelService()

    # Create Feishu adapter
    config = ChannelConfig(
        app_id=os.getenv("FEISHU_APP_ID", "cli_xxx"),
        app_secret=os.getenv("FEISHU_APP_SECRET", "xxx"),
        connection_mode="websocket",
    )
    feishu = FeishuAdapter(config)

    # Register adapter
    service.register_adapter(feishu)

    # Handle incoming messages
    async def on_message(message: Any) -> None:
        print(f"[{message.channel}] {message.sender.name}: {message.content.text}")

        # Auto-reply
        if message.content.text and "hello" in message.content.text.lower():
            await feishu.send_text(message.chat_id, "Hello! 👋")

    service.on_message(on_message)  # type: ignore[arg-type]

    # Connect
    await service.connect_all()

    # Send messages
    await service.send_text("feishu", "oc_xxx", "大家好！")

    # Get chat info
    members = await service.get_chat_members("feishu", "oc_xxx")
    print(f"Chat members: {len(members)}")

    # Keep running
    with contextlib.suppress(KeyboardInterrupt):
        await asyncio.sleep(300)  # Run for 5 minutes

    # Disconnect
    await service.disconnect_all()


async def convenience_functions_example() -> None:
    """Convenience functions example."""
    app_id = os.getenv("FEISHU_APP_ID", "cli_xxx")
    app_secret = os.getenv("FEISHU_APP_SECRET", "xxx")
    chat_id = "oc_xxx"

    # Send text (simplest way)
    await send_feishu_text(app_id, app_secret, chat_id, "Hello!")

    # Send card
    await send_feishu_card(
        app_id,
        app_secret,
        chat_id,
        {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "通知"}},
            "body": {"elements": [{"tag": "markdown", "content": "这是一条卡片消息"}]},
        },
    )


async def main() -> None:
    """Run all examples."""
    print("=" * 50)
    print("Feishu Channels Examples")
    print("=" * 50)

    examples = {
        "basic": basic_messaging_example,
        "media": media_example,
        "document": document_example,
        "wiki": wiki_example,
        "drive": drive_example,
        "bitable": bitable_example,
        "cards": card_builder_example,
        "convenience": convenience_functions_example,
        # "service": channel_service_example,  # Requires running WebSocket
    }

    # Run specific example or all
    import sys

    if len(sys.argv) > 1:
        example_name = sys.argv[1]
        if example_name in examples:
            print(f"\nRunning {example_name} example...")
            await examples[example_name]()
        else:
            print(f"Unknown example: {example_name}")
            print(f"Available: {', '.join(examples.keys())}")
    else:
        print("\nAvailable examples:")
        for name in examples:
            print(f"  - {name}")
        print("\nRun: python feishu_examples.py <example_name>")


if __name__ == "__main__":
    asyncio.run(main())
