"""Unit tests for the A2UI JSONL message builder.

Validates that component helpers emit the correct v0.8 ComponentInstance
format and that envelope constructors produce valid A2UI message shapes.
"""

from __future__ import annotations

import json

from src.infrastructure.agent.canvas.a2ui_builder import (
    badge_component,
    begin_rendering,
    button_component,
    card_component,
    checkbox_component,
    column_component,
    data_model_update,
    delete_surface,
    divider_component,
    extract_actionable_actions,
    extract_surface_id,
    image_component,
    merge_a2ui_message_stream,
    modal_component,
    pack_messages,
    progress_component,
    radio_component,
    row_component,
    select_component,
    surface_update,
    table_component,
    tabs_component,
    text_component,
    text_field_component,
    validate_a2ui_incremental_surface_id,
    validate_a2ui_messages,
)

# ---------------------------------------------------------------------------
# Component helpers — v0.8 format: {id, component: {TypeName: {props}}}
# ---------------------------------------------------------------------------


class TestTextComponent:
    """Tests for text_component()."""

    def test_basic_text(self) -> None:
        comp = text_component("hello")
        assert isinstance(comp["id"], str)
        assert len(comp["id"]) == 12
        assert "component" in comp
        assert "Text" in comp["component"]
        assert comp["component"]["Text"]["text"] == {"literalString": "hello"}

    def test_text_with_style(self) -> None:
        comp = text_component("styled", style={"color": "red", "fontSize": "16px"})
        text_props = comp["component"]["Text"]
        assert text_props["text"] == {"literalString": "styled"}
        assert text_props["style"] == {"color": "red", "fontSize": "16px"}

    def test_no_legacy_type_field(self) -> None:
        comp = text_component("test")
        assert "type" not in comp
        assert "props" not in comp


class TestButtonComponent:
    """Tests for button_component()."""

    def test_basic_button(self) -> None:
        btn, label_text = button_component("Click me", "btn_action")
        assert "component" in btn
        assert "Button" in btn["component"]
        btn_props = btn["component"]["Button"]
        assert btn_props["child"] == label_text["id"]
        assert btn_props["action"] == {"name": "btn_action"}
        # Label text is a valid Text component
        assert label_text["component"]["Text"]["text"] == {"literalString": "Click me"}

    def test_button_with_style(self) -> None:
        btn, _label = button_component("OK", "ok_action", style={"width": "100px"})
        btn_props = btn["component"]["Button"]
        assert btn_props["style"] == {"width": "100px"}

    def test_button_returns_tuple(self) -> None:
        result = button_component("X", "x")
        assert isinstance(result, tuple)
        assert len(result) == 2
        btn, label_text = result
        assert "id" in btn
        assert "id" in label_text


class TestValidateA2UIMessages:
    """Tests for validate_a2ui_messages()."""

    def test_rejects_flat_surface_object(self) -> None:
        payload = json.dumps(
            {
                "surfaceId": "surface-1",
                "components": [
                    {
                        "id": "root-1",
                        "component": {"Text": {"text": {"literal": "hello"}}},
                    }
                ],
            }
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is not None
        assert 'plain {"surfaceId":"...","components":[...]}' in error
        assert "beginRendering/surfaceUpdate envelopes" in error

    def test_rejects_malformed_json_between_valid_envelopes(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":[{"id":"root-1","component":{"Text":{"text":{"literalString":"hello"}}}}]}}',
                '{"broken":',
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is not None
        assert "malformed JSON" in error

    def test_rejects_incremental_payload_without_surface_id_for_existing_surface(self) -> None:
        payload = json.dumps(
            {
                "surfaceUpdate": {
                    "components": [
                        {
                            "id": "root-1",
                            "component": {"Text": {"text": {"literalString": "hello"}}},
                        }
                    ]
                }
            }
        )

        error = validate_a2ui_incremental_surface_id(
            payload,
            expected_surface_id="surface-1",
        )

        assert error is not None
        assert "must include surfaceId on every envelope" in error

    def test_rejects_incremental_payload_with_mismatched_surface_id(self) -> None:
        payload = json.dumps(
            {
                "surfaceUpdate": {
                    "surfaceId": "surface-2",
                    "components": [
                        {
                            "id": "root-1",
                            "component": {"Text": {"text": {"literalString": "hello"}}},
                        }
                    ],
                }
            }
        )

        error = validate_a2ui_incremental_surface_id(
            payload,
            expected_surface_id="surface-1",
        )

        assert error is not None
        assert "must use surfaceId 'surface-1'" in error

    def test_accepts_incremental_surface_update_for_existing_block(self) -> None:
        payload = json.dumps(
            {
                "surfaceUpdate": {
                    "components": [
                        {
                            "id": "root-1",
                            "component": {"Text": {"text": {"literalString": "hello"}}},
                        }
                    ]
                }
            }
        )

        error = validate_a2ui_messages(payload, require_initial_render=False)

        assert error is None

    def test_accepts_phase1_atomic_components(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"layout-1"}}',
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "layout-1",
                                    "component": {
                                        "Column": {
                                            "children": {
                                                "explicitList": [
                                                    "image-1",
                                                    "checkbox-1",
                                                    "select-1",
                                                    "radio-1",
                                                    "badge-1",
                                                ]
                                            }
                                        }
                                    },
                                },
                                {
                                    "id": "image-1",
                                    "component": {
                                        "Image": {
                                            "url": {
                                                "literalString": "https://example.com/avatar.png"
                                            },
                                            "fit": "cover",
                                        }
                                    },
                                },
                                {
                                    "id": "checkbox-1",
                                    "component": {
                                        "Checkbox": {
                                            "label": {"literalString": "Email updates"},
                                            "value": {"path": "/form/updates"},
                                        }
                                    },
                                },
                                {
                                    "id": "select-1",
                                    "component": {
                                        "Select": {
                                            "description": {"literalString": "Priority"},
                                            "options": [
                                                {
                                                    "label": {"literalString": "High"},
                                                    "value": "high",
                                                }
                                            ],
                                            "selections": {"path": "/form/priority"},
                                        }
                                    },
                                },
                                {
                                    "id": "radio-1",
                                    "component": {
                                        "Radio": {
                                            "description": {"literalString": "Plan"},
                                            "options": [
                                                {
                                                    "label": {"literalString": "Starter"},
                                                    "value": "starter",
                                                }
                                            ],
                                            "value": {"path": "/form/plan"},
                                        }
                                    },
                                },
                                {
                                    "id": "badge-1",
                                    "component": {
                                        "Badge": {
                                            "text": {"literalString": "Active"},
                                            "tone": "success",
                                        }
                                    },
                                },
                            ],
                        }
                    }
                ),
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is None

    def test_accepts_phase3_authoring_sugar(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "root-1",
                                    "component": {
                                        "Column": {
                                            "gap": 16,
                                            "children": {"explicitList": ["card-1", "button-1"]},
                                        }
                                    },
                                },
                                {
                                    "id": "card-1",
                                    "component": {
                                        "Card": {
                                            "title": {
                                                "Text": {
                                                    "text": {"literalString": "Card title"},
                                                    "style": {"fontWeight": "700"},
                                                }
                                            },
                                            "children": {"explicitList": ["body-1"]},
                                        }
                                    },
                                },
                                {
                                    "id": "body-1",
                                    "component": {"Text": {"text": {"literalString": "Body copy"}}},
                                },
                                {
                                    "id": "button-1",
                                    "component": {
                                        "Button": {
                                            "label": {"literalString": "Submit"},
                                            "action": {"name": "submit"},
                                        }
                                    },
                                },
                            ],
                        }
                    }
                ),
            ]
        )

        error = validate_a2ui_messages(
            payload,
            require_initial_render=True,
            require_user_action=True,
        )

        assert error is None

    def test_accepts_empty_children_lists(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "root-1",
                                    "component": {
                                        "Column": {
                                            "children": [],
                                        }
                                    },
                                }
                            ],
                        }
                    }
                ),
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is None

    def test_accepts_phase2_container_components(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"layout-1"}}',
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "layout-1",
                                    "component": {
                                        "Column": {
                                            "children": {
                                                "explicitList": [
                                                    "tabs-1",
                                                    "modal-1",
                                                    "table-1",
                                                    "progress-1",
                                                ]
                                            }
                                        }
                                    },
                                },
                                {
                                    "id": "tabs-1",
                                    "component": {
                                        "Tabs": {
                                            "tabItems": [
                                                {
                                                    "title": {"literalString": "Overview"},
                                                    "child": "tab-body-1",
                                                }
                                            ]
                                        }
                                    },
                                },
                                {
                                    "id": "tab-body-1",
                                    "component": {
                                        "Text": {
                                            "text": {"literalString": "Tab content"},
                                        }
                                    },
                                },
                                {
                                    "id": "modal-1",
                                    "component": {
                                        "Modal": {
                                            "entryPointChild": "modal-trigger-1",
                                            "contentChild": "modal-content-1",
                                        }
                                    },
                                },
                                {
                                    "id": "modal-trigger-1",
                                    "component": {
                                        "Text": {
                                            "text": {"literalString": "Open details"},
                                        }
                                    },
                                },
                                {
                                    "id": "modal-content-1",
                                    "component": {
                                        "Text": {
                                            "text": {"literalString": "Modal content"},
                                        }
                                    },
                                },
                                {
                                    "id": "table-1",
                                    "component": {
                                        "Table": {
                                            "columns": [{"header": {"literalString": "Name"}}],
                                            "rows": [{"cells": [{"literalString": "Alice"}]}],
                                        }
                                    },
                                },
                                {
                                    "id": "progress-1",
                                    "component": {
                                        "Progress": {
                                            "label": {"literalString": "Completion"},
                                            "value": {"literalNumber": 42},
                                            "max": {"literalNumber": 100},
                                        }
                                    },
                                },
                            ],
                        }
                    }
                ),
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is None

    def test_rejects_missing_root_component_for_existing_block_when_begin_rendering_present(
        self,
    ) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"missing-root"}}',
                '{"surfaceUpdate":{"components":[]}}',
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=False)

        assert error is not None
        assert "Missing roots" in error

    def test_rejects_non_actionable_existing_surface_when_user_action_required(self) -> None:
        payload = json.dumps(
            {
                "surfaceUpdate": {
                    "components": [
                        {
                            "id": "button-1",
                            "component": {"Text": {"text": {"literalString": "No action"}}},
                        }
                    ]
                }
            }
        )

        error = validate_a2ui_messages(
            payload,
            require_initial_render=False,
            require_user_action=True,
        )

        assert error is not None
        assert "interactive updates must still resolve" in error

    def test_rejects_button_with_missing_child_reference_on_initial_render(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"button-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"button-1","component":{"Button":{"child":"missing-label","action":{"name":"submit"}}}}]}}',
            ]
        )

        error = validate_a2ui_messages(
            payload,
            require_initial_render=True,
            require_user_action=True,
        )

        assert error is not None
        assert "Button.child must reference an existing Text component id" in error

    def test_rejects_button_with_missing_child_reference_after_merge(self) -> None:
        previous = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"button-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"label-1","component":{"Text":{"text":{"literalString":"Approve"}}}},'
                '{"id":"button-1","component":{"Button":{"child":"label-1","action":{"name":"submit"}}}}]}}',
            ]
        )
        incoming = json.dumps(
            {
                "surfaceUpdate": {
                    "components": [
                        {
                            "id": "button-1",
                            "component": {
                                "Button": {
                                    "child": "missing-label",
                                    "action": {"name": "submit"},
                                }
                            },
                        }
                    ]
                }
            }
        )

        merged = merge_a2ui_message_stream(previous, incoming)
        error = validate_a2ui_messages(
            merged,
            require_initial_render=False,
            require_user_action=True,
        )

        assert error is not None
        assert "Button.child must reference an existing Text component id" in error

    def test_merge_replaces_existing_actionable_component_by_id(self) -> None:
        previous = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"button-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"label-1","component":{"Text":{"text":{"literalString":"Approve"}}}},'
                '{"id":"button-1","component":{"Button":{"child":"label-1","action":{"name":"submit"}}}}]}}',
            ]
        )
        incoming = json.dumps(
            {
                "surfaceUpdate": {
                    "components": [
                        {
                            "id": "button-1",
                            "component": {"Text": {"text": {"literalString": "Replaced"}}},
                        }
                    ]
                }
            }
        )

        merged = merge_a2ui_message_stream(previous, incoming)
        error = validate_a2ui_messages(
            merged,
            require_initial_render=False,
            require_user_action=True,
        )

        assert '"Button"' not in merged
        assert error is not None
        assert "interactive updates must still resolve" in error

    def test_merge_does_not_retarget_incremental_updates_with_drifted_surface_id(self) -> None:
        previous = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"root-1","component":{"Text":{"text":{"literalString":"Hello"}}}}]}}',
            ]
        )
        incoming = json.dumps(
            {
                "surfaceUpdate": {
                    "surfaceId": "surface-2",
                    "components": [
                        {
                            "id": "root-1",
                            "component": {"Text": {"text": {"literalString": "Updated"}}},
                        }
                    ],
                }
            }
        )

        merged = merge_a2ui_message_stream(previous, incoming)

        assert '"surfaceId": "surface-2"' in merged
        assert '"beginRendering"' not in merged

    def test_merge_canonicalizes_incremental_phase3_authoring_sugar(self) -> None:
        previous = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "root-1",
                                    "component": {
                                        "Column": {
                                            "gap": "8px",
                                            "children": {"explicitList": ["button-1"]},
                                        }
                                    },
                                },
                                {
                                    "id": "label-1",
                                    "component": {"Text": {"text": {"literalString": "Approve"}}},
                                },
                                {
                                    "id": "button-1",
                                    "component": {
                                        "Button": {
                                            "child": "label-1",
                                            "action": {"name": "submit"},
                                        }
                                    },
                                },
                            ],
                        }
                    }
                ),
            ]
        )
        incoming = json.dumps(
            {
                "surfaceUpdate": {
                    "surfaceId": "surface-1",
                    "components": [
                        {
                            "id": "root-1",
                            "component": {
                                "Column": {
                                    "gap": 16,
                                    "children": {"explicitList": ["card-1", "button-1"]},
                                }
                            },
                        },
                        {
                            "id": "card-1",
                            "component": {
                                "Card": {
                                    "title": {"literalString": "Card title"},
                                    "children": {"explicitList": ["body-1"]},
                                }
                            },
                        },
                        {
                            "id": "body-1",
                            "component": {"Text": {"text": {"literalString": "Body copy"}}},
                        },
                        {
                            "id": "button-1",
                            "component": {
                                "Button": {
                                    "label": {"literalString": "Submit"},
                                    "action": {"name": "submit"},
                                }
                            },
                        },
                    ]
                }
            }
        )

        merged = merge_a2ui_message_stream(previous, incoming)

        assert '"gap": "16px"' in merged
        assert '"child": "button-1__label"' in merged
        assert '"label":' not in merged
        assert '"card-1__title"' in merged
        assert (
            validate_a2ui_messages(
                merged,
                require_initial_render=False,
                require_user_action=True,
            )
            is None
        )

    def test_merge_avoids_synthetic_label_id_collisions_with_existing_surface_state(self) -> None:
        previous = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "root-1",
                                    "component": {
                                        "Column": {
                                            "children": {
                                                "explicitList": ["button-1", "button-1__label"]
                                            }
                                        }
                                    },
                                },
                                {
                                    "id": "button-1__label",
                                    "component": {
                                        "Text": {"text": {"literalString": "Existing component"}}
                                    },
                                },
                                {
                                    "id": "button-1",
                                    "component": {
                                        "Button": {
                                            "child": "button-1__label",
                                            "action": {"name": "submit"},
                                        }
                                    },
                                },
                            ],
                        }
                    }
                ),
            ]
        )
        incoming = json.dumps(
            {
                "surfaceUpdate": {
                    "surfaceId": "surface-1",
                    "components": [
                        {
                            "id": "button-1",
                            "component": {
                                "Button": {
                                    "label": {"literalString": "Updated submit"},
                                    "action": {"name": "submit"},
                                }
                            },
                        }
                    ]
                }
            }
        )

        merged = merge_a2ui_message_stream(previous, incoming)

        assert '"button-1__label_2"' in merged
        assert '"button-1__label"' in merged
        assert '"child": "button-1__label_2"' in merged

    def test_merge_reserves_synthetic_ids_across_multi_update_batches(self) -> None:
        previous = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"button-1"}}',
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "button-1__label",
                                    "component": {
                                        "Text": {"text": {"literalString": "Existing label"}}
                                    },
                                },
                                {
                                    "id": "button-1",
                                    "component": {
                                        "Button": {
                                            "child": "button-1__label",
                                            "action": {"name": "submit"},
                                        }
                                    },
                                },
                            ],
                        }
                    }
                ),
            ]
        )
        incoming = "\n".join(
            [
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "button-1",
                                    "component": {
                                        "Button": {
                                            "label": {"literalString": "Step one"},
                                            "action": {"name": "submit"},
                                        }
                                    },
                                }
                            ]
                        }
                    }
                ),
                json.dumps(
                    {
                        "surfaceUpdate": {
                            "surfaceId": "surface-1",
                            "components": [
                                {
                                    "id": "button-1",
                                    "component": {
                                        "Button": {
                                            "label": {"literalString": "Step two"},
                                            "action": {"name": "submit"},
                                        }
                                    },
                                }
                            ]
                        }
                    }
                ),
            ]
        )

        merged = merge_a2ui_message_stream(previous, incoming)

        assert '"child": "button-1__label_3"' in merged
        assert '"button-1__label_2"' not in merged
        assert '"button-1__label_3"' in merged

    def test_rejects_orphan_button_outside_reachable_render_tree(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"root-1","component":{"Text":{"text":{"literalString":"Visible"}}}},'
                '{"id":"label-1","component":{"Text":{"text":{"literalString":"Hidden"}}}},'
                '{"id":"button-1","component":{"Button":{"child":"label-1","action":{"name":"submit"}}}}]}}',
            ]
        )

        error = validate_a2ui_messages(
            payload,
            require_initial_render=True,
            require_user_action=True,
        )

        assert error is not None
        assert "interactive surfaces must include" in error

    def test_extract_actionable_actions_ignores_orphan_buttons(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"root-1","component":{"Text":{"text":{"literalString":"Visible"}}}},'
                '{"id":"label-1","component":{"Text":{"text":{"literalString":"Hidden"}}}},'
                '{"id":"button-1","component":{"Button":{"child":"label-1","action":{"name":"submit"}}}}]}}',
            ]
        )

        assert extract_actionable_actions(payload) == []

    def test_extract_actionable_actions_finds_button_inside_tabs(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"tabs-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"tabs-1","component":{"Tabs":{"tabItems":[{"title":{"literalString":"Review"},"child":"button-1"}]}}},'
                '{"id":"label-1","component":{"Text":{"text":{"literalString":"Approve"}}}},'
                '{"id":"button-1","component":{"Button":{"child":"label-1","action":{"name":"approve"}}}}]}}',
            ]
        )

        assert extract_actionable_actions(payload) == [
            {"source_component_id": "button-1", "action_name": "approve"}
        ]

    def test_extract_actionable_actions_finds_button_inside_modal_content(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"modal-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"modal-1","component":{"Modal":{"entryPointChild":"trigger-1","contentChild":"button-1"}}},'
                '{"id":"trigger-1","component":{"Text":{"text":{"literalString":"Open"}}}},'
                '{"id":"label-1","component":{"Text":{"text":{"literalString":"Confirm"}}}},'
                '{"id":"button-1","component":{"Button":{"child":"label-1","action":{"name":"confirm"}}}}]}}',
            ]
        )

        assert extract_actionable_actions(payload) == [
            {"source_component_id": "button-1", "action_name": "confirm"}
        ]

    def test_rejects_tabs_with_missing_child_reference(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"tabs-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"tabs-1","component":{"Tabs":{"tabItems":[{"title":{"literalString":"Review"},"child":"missing-body"}]}}}]}}',
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is not None
        assert "Tabs.tabItems[*].child must reference existing component ids" in error

    def test_rejects_modal_with_missing_child_reference(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"modal-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":['
                '{"id":"modal-1","component":{"Modal":{"entryPointChild":"trigger-1","contentChild":"missing-content"}}},'
                '{"id":"trigger-1","component":{"Text":{"text":{"literalString":"Open"}}}}]}}',
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is not None
        assert "Modal entryPointChild/contentChild must reference existing component ids" in error

    def test_rejects_unknown_component_type_for_new_surface(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":[{"id":"root-1","component":{"UnknownWidget":{}}}]}}',
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is not None
        assert "unsupported component keys" in error

    def test_rejects_supported_component_with_extra_unknown_key(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}},"UnknownWidget":{}}}]}}',
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is not None
        assert "unsupported component keys" in error

    def test_rejects_mixed_surface_ids_for_new_surface(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-2","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}',
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is not None
        assert "same surfaceId" in error

    def test_rejects_missing_root_component_for_new_surface(self) -> None:
        payload = "\n".join(
            [
                '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                '{"surfaceUpdate":{"surfaceId":"surface-1","components":[{"id":"other-root","component":{"Text":{"text":{"literal":"hello"}}}}]}}',
            ]
        )

        error = validate_a2ui_messages(payload, require_initial_render=True)

        assert error is not None
        assert "Missing roots" in error

    def test_no_legacy_fields(self) -> None:
        btn, _label = button_component("X", "x")
        assert "type" not in btn
        assert "props" not in btn
        assert "label" not in btn["component"]["Button"]
        assert "onPress" not in btn["component"]["Button"]
        assert "variant" not in btn["component"]["Button"]


class TestCardComponent:
    """Tests for card_component()."""

    def test_card_with_children(self) -> None:
        child1 = text_component("item 1")
        child2 = text_component("item 2")
        card = card_component([child1, child2], title="My Card")
        assert "component" in card
        assert "Card" in card["component"]
        card_props = card["component"]["Card"]
        assert card_props["title"] == "My Card"
        assert card_props["children"] == {"explicitList": [child1["id"], child2["id"]]}

    def test_card_without_title(self) -> None:
        child = text_component("solo")
        card = card_component([child])
        card_props = card["component"]["Card"]
        assert "title" not in card_props
        assert card_props["children"] == {"explicitList": [child["id"]]}

    def test_card_with_style(self) -> None:
        child = text_component("styled child")
        card = card_component([child], style={"padding": "16px"})
        card_props = card["component"]["Card"]
        assert card_props["style"] == {"padding": "16px"}

    def test_no_legacy_children_field(self) -> None:
        child = text_component("x")
        card = card_component([child])
        # Children should only be inside the component dict, not at top level
        assert "children" not in card


class TestColumnComponent:
    """Tests for column_component()."""

    def test_column_layout(self) -> None:
        child1 = text_component("row 1")
        child2 = text_component("row 2")
        col = column_component([child1, child2])
        assert "component" in col
        assert "Column" in col["component"]
        col_props = col["component"]["Column"]
        assert col_props["gap"] == "8px"
        assert col_props["children"] == {"explicitList": [child1["id"], child2["id"]]}

    def test_custom_gap(self) -> None:
        child = text_component("x")
        col = column_component([child], gap="16px")
        assert col["component"]["Column"]["gap"] == "16px"

    def test_numeric_gap_is_normalized_to_px(self) -> None:
        child = text_component("x")
        col = column_component([child], gap=16)
        assert col["component"]["Column"]["gap"] == "16px"

    def test_no_legacy_fields(self) -> None:
        child = text_component("x")
        col = column_component([child])
        assert "type" not in col
        assert "props" not in col
        assert "children" not in col


class TestRowComponent:
    """Tests for row_component()."""

    def test_row_layout(self) -> None:
        child1 = text_component("col 1")
        child2 = text_component("col 2")
        row = row_component([child1, child2])
        assert "component" in row
        assert "Row" in row["component"]
        row_props = row["component"]["Row"]
        assert row_props["gap"] == "8px"
        assert row_props["children"] == {"explicitList": [child1["id"], child2["id"]]}

    def test_numeric_gap_is_normalized_to_px(self) -> None:
        child = text_component("x")
        row = row_component([child], gap=12)
        assert row["component"]["Row"]["gap"] == "12px"


class TestTextFieldComponent:
    """Tests for text_field_component()."""

    def test_basic_field(self) -> None:
        comp = text_field_component("Name", "name_change")
        assert "component" in comp
        assert "TextField" in comp["component"]
        field = comp["component"]["TextField"]
        assert field["label"] == {"literalString": "Name"}
        assert field["text"] == {"path": "/name_change"}
        assert "onChange" not in field
        assert "value" not in field

    def test_field_with_defaults(self) -> None:
        comp = text_field_component(
            "Email", "email_change", placeholder="you@example.com", value="test@test.com"
        )
        field = comp["component"]["TextField"]
        assert field["placeholder"] == "you@example.com"
        assert field["text"] == {"path": "/email_change", "literalString": "test@test.com"}

    def test_no_legacy_fields(self) -> None:
        comp = text_field_component("X", "x")
        assert "type" not in comp
        assert "props" not in comp


class TestDividerComponent:
    """Tests for divider_component()."""

    def test_divider(self) -> None:
        comp = divider_component()
        assert "component" in comp
        assert "Divider" in comp["component"]
        assert comp["component"]["Divider"] == {}

    def test_no_legacy_fields(self) -> None:
        comp = divider_component()
        assert "type" not in comp
        assert "props" not in comp


class TestImageComponent:
    """Tests for image_component()."""

    def test_image_with_usage_hint(self) -> None:
        comp = image_component(
            "https://example.com/photo.png",
            usage_hint="avatar",
            fit="cover",
        )
        props = comp["component"]["Image"]
        assert props["url"] == {"literalString": "https://example.com/photo.png"}
        assert props["usageHint"] == "avatar"
        assert props["fit"] == "cover"


class TestCheckboxComponent:
    """Tests for checkbox_component()."""

    def test_checkbox_binds_boolean_value(self) -> None:
        comp = checkbox_component("Email updates", "form/updates", checked=True)
        props = comp["component"]["Checkbox"]
        assert props["label"] == {"literalString": "Email updates"}
        assert props["value"] == {"path": "/form/updates", "literalBoolean": True}


class TestSelectComponent:
    """Tests for select_component()."""

    def test_select_normalizes_string_options(self) -> None:
        comp = select_component("Priority", "form/priority", ["High", "Low"])
        props = comp["component"]["Select"]
        assert props["description"] == {"literalString": "Priority"}
        assert props["selections"] == {"path": "/form/priority"}
        assert props["options"] == [
            {"label": {"literalString": "High"}, "value": "High"},
            {"label": {"literalString": "Low"}, "value": "Low"},
        ]


class TestRadioComponent:
    """Tests for radio_component()."""

    def test_radio_binds_single_string_value(self) -> None:
        comp = radio_component("Plan", "form/plan", [("Starter", "starter")], value="starter")
        props = comp["component"]["Radio"]
        assert props["description"] == {"literalString": "Plan"}
        assert props["options"] == [{"label": {"literalString": "Starter"}, "value": "starter"}]
        assert props["value"] == {"path": "/form/plan", "literalString": "starter"}


class TestBadgeComponent:
    """Tests for badge_component()."""

    def test_badge_with_tone(self) -> None:
        comp = badge_component("Active", tone="success")
        props = comp["component"]["Badge"]
        assert props["text"] == {"literalString": "Active"}
        assert props["tone"] == "success"


class TestTabsComponent:
    """Tests for tabs_component()."""

    def test_tabs_binds_titles_to_child_ids(self) -> None:
        comp = tabs_component([("Overview", "overview-panel"), ("Activity", "activity-panel")])
        props = comp["component"]["Tabs"]
        assert props["tabItems"] == [
            {"title": {"literalString": "Overview"}, "child": "overview-panel"},
            {"title": {"literalString": "Activity"}, "child": "activity-panel"},
        ]


class TestModalComponent:
    """Tests for modal_component()."""

    def test_modal_references_entry_and_content_children(self) -> None:
        comp = modal_component("open-text", "modal-card")
        props = comp["component"]["Modal"]
        assert props == {
            "entryPointChild": "open-text",
            "contentChild": "modal-card",
        }


class TestTableComponent:
    """Tests for table_component()."""

    def test_table_normalizes_columns_and_rows(self) -> None:
        comp = table_component(
            ["Name", "Status"],
            [["Alice", True], {"cells": ["Bob", "Pending"]}],
            caption="Users",
            empty_text="No rows",
        )
        props = comp["component"]["Table"]
        assert props["caption"] == {"literalString": "Users"}
        assert props["emptyText"] == {"literalString": "No rows"}
        assert props["columns"] == [
            {"header": {"literalString": "Name"}},
            {"header": {"literalString": "Status"}},
        ]
        assert props["rows"] == [
            {
                "cells": [
                    {"literalString": "Alice"},
                    {"literalBoolean": True},
                ]
            },
            {
                "cells": [
                    {"literalString": "Bob"},
                    {"literalString": "Pending"},
                ]
            },
        ]


class TestProgressComponent:
    """Tests for progress_component()."""

    def test_progress_supports_bound_values_and_defaults(self) -> None:
        comp = progress_component(
            value=25,
            value_path="progress/current",
            label="Completion",
            max_value=100,
            tone="success",
        )
        props = comp["component"]["Progress"]
        assert props["label"] == {"literalString": "Completion"}
        assert props["value"] == {"path": "/progress/current", "literalNumber": 25}
        assert props["max"] == {"literalNumber": 100}
        assert props["tone"] == "success"
        assert props["showValue"] is True


# ---------------------------------------------------------------------------
# Envelope constructors
# ---------------------------------------------------------------------------


class TestSurfaceUpdate:
    """Tests for surface_update()."""

    def test_envelope_shape(self) -> None:
        comps = [text_component("hi")]
        envelope = surface_update("surf-1", comps)
        assert "surfaceUpdate" in envelope
        assert envelope["surfaceUpdate"]["surfaceId"] == "surf-1"
        assert envelope["surfaceUpdate"]["components"] == comps


class TestDataModelUpdate:
    """Tests for data_model_update()."""

    def test_default_path(self) -> None:
        contents = {"status": "ok", "count": 2}
        envelope = data_model_update("surf-1", contents)
        assert envelope["dataModelUpdate"]["path"] == "/"
        assert envelope["dataModelUpdate"]["contents"] == [
            {"key": "status", "valueString": "ok"},
            {"key": "count", "valueNumber": 2},
        ]

    def test_custom_path(self) -> None:
        envelope = data_model_update("surf-1", [{"x": 1}], path="/items")
        assert envelope["dataModelUpdate"]["path"] == "/items"
        assert envelope["dataModelUpdate"]["contents"] == [
            {"key": "0", "valueMap": [{"key": "x", "valueNumber": 1}]},
        ]

    def test_preformatted_value_maps_pass_through(self) -> None:
        contents = [{"key": "name", "valueString": "Alice"}]
        envelope = data_model_update("surf-1", contents)
        assert envelope["dataModelUpdate"]["contents"] == contents

    def test_mixed_value_map_lists_preserve_existing_entries(self) -> None:
        envelope = data_model_update(
            "surf-1",
            [
                {"key": "name", "valueString": "Alice"},
                {"key": "nickname"},
                {"x": 1},
            ],
        )
        assert envelope["dataModelUpdate"]["contents"] == [
            {"key": "name", "valueString": "Alice"},
            {"key": "nickname"},
            {"key": "2", "valueMap": [{"key": "x", "valueNumber": 1}]},
        ]


class TestBeginRendering:
    """Tests for begin_rendering()."""

    def test_basic(self) -> None:
        envelope = begin_rendering("surf-1", "root-id")
        assert envelope["beginRendering"]["surfaceId"] == "surf-1"
        assert envelope["beginRendering"]["root"] == "root-id"
        assert "styles" not in envelope["beginRendering"]

    def test_with_styles(self) -> None:
        envelope = begin_rendering("surf-1", "root-id", styles={"primaryColor": "#000"})
        assert envelope["beginRendering"]["styles"] == {"primaryColor": "#000"}


class TestDeleteSurface:
    """Tests for delete_surface()."""

    def test_envelope(self) -> None:
        envelope = delete_surface("surf-1")
        assert envelope["deleteSurface"]["surfaceId"] == "surf-1"


class TestExtractSurfaceId:
    """Tests for extract_surface_id()."""

    def test_single_surface(self) -> None:
        messages = pack_messages(
            [
                begin_rendering("surf-1", "root"),
                surface_update("surf-1", [text_component("hello")]),
            ]
        )
        assert extract_surface_id(messages) == "surf-1"

    def test_multiple_surfaces_returns_none(self) -> None:
        messages = pack_messages(
            [
                begin_rendering("surf-1", "root-1"),
                surface_update("surf-1", [text_component("hello")]),
                begin_rendering("surf-2", "root-2"),
            ]
        )
        assert extract_surface_id(messages) is None

    def test_nested_surface_id_fields_are_ignored(self) -> None:
        messages = json.dumps(
            {
                "surfaceUpdate": {
                    "surfaceId": "surf-1",
                    "components": [
                        {
                            "id": "btn-1",
                            "component": {
                                "Button": {
                                    "child": "label-1",
                                    "action": {
                                        "name": "submit",
                                        "context": {
                                            "surfaceId": "domain-object-id",
                                        },
                                    },
                                },
                            },
                        },
                    ],
                },
            }
        )
        assert extract_surface_id(messages) == "surf-1"

    def test_pretty_printed_multiline_payload_is_supported(self) -> None:
        messages = """
        {
          "beginRendering": {
            "surfaceId": "surf-1",
            "root": "root-1"
          }
        }
        {
          "surfaceUpdate": {
            "surfaceId": "surf-1",
            "components": []
          }
        }
        """
        assert extract_surface_id(messages) == "surf-1"


# ---------------------------------------------------------------------------
# pack_messages
# ---------------------------------------------------------------------------


class TestPackMessages:
    """Tests for pack_messages()."""

    def test_single_message(self) -> None:
        msg = begin_rendering("s1", "root")
        result = pack_messages([msg])
        parsed = json.loads(result)
        assert "beginRendering" in parsed

    def test_multiple_messages(self) -> None:
        msgs = [
            begin_rendering("s1", "root"),
            surface_update("s1", [text_component("hi")]),
        ]
        result = pack_messages(msgs)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert "beginRendering" in json.loads(lines[0])
        assert "surfaceUpdate" in json.loads(lines[1])

    def test_no_whitespace_in_json(self) -> None:
        """pack_messages uses compact separators."""
        msg = begin_rendering("s1", "root")
        result = pack_messages([msg])
        assert " " not in result  # compact JSON has no spaces


# ---------------------------------------------------------------------------
# Integration: full surface build
# ---------------------------------------------------------------------------


class TestFullSurfaceBuild:
    """End-to-end: build a surface with multiple components and pack to JSONL."""

    def test_info_card_surface(self) -> None:
        """Build a card with title, text, and a button, then pack to JSONL."""
        title = text_component("Welcome!")
        body = text_component("This is an A2UI surface rendered in MemStack.")
        action_btn, action_label = button_component("Get Started", "get_started")
        card = card_component([title, body, action_btn], title="Info Card")
        layout = column_component([card])

        surface_id = "test-surface-001"
        messages = [
            begin_rendering(surface_id, layout["id"]),
            surface_update(
                surface_id,
                [title, body, action_label, action_btn, card, layout],
            ),
        ]
        jsonl = pack_messages(messages)

        lines = jsonl.strip().split("\n")
        assert len(lines) == 2

        # Verify begin_rendering
        begin = json.loads(lines[0])
        assert begin["beginRendering"]["root"] == layout["id"]

        # Verify surface_update has all 6 components (title, body, label_text, button, card, layout)
        update = json.loads(lines[1])
        assert len(update["surfaceUpdate"]["components"]) == 6

        # Verify all components use v0.8 format
        for comp in update["surfaceUpdate"]["components"]:
            assert "id" in comp
            assert "component" in comp
            assert "type" not in comp, "Legacy 'type' field should not exist"
            assert "props" not in comp, "Legacy 'props' field should not exist"
