"""Knowledge Base UI field visibility by backend."""

from __future__ import annotations

from lfx_liam_bundle.components.liam.kb_instance import GraphRAGKBInstanceComponent


def _base_config() -> dict:
    names = [
        "backend",
        "api_endpoint",
        "token",
        "data_api_environment",
        "data_api_username",
        "data_api_password",
        "keyspace",
        "arango_url",
        "arango_username",
        "arango_password",
        "arango_database",
        "graph_name",
        "vector_index_factory",
    ]
    cfg = {n: {"show": True, "required": False, "value": None} for n in names}
    cfg["backend"]["value"] = "AstraDB"
    cfg["data_api_environment"]["value"] = "astra"
    return cfg


def test_astra_hides_arango_fields() -> None:
    comp = GraphRAGKBInstanceComponent()
    cfg = comp.update_build_config(_base_config(), "AstraDB", "backend")
    assert cfg["api_endpoint"]["show"] is True
    assert cfg["token"]["show"] is True
    assert cfg["keyspace"]["show"] is True
    assert cfg["arango_url"]["show"] is False
    assert cfg["arango_password"]["show"] is False
    assert cfg["vector_index_factory"]["show"] is False
    assert cfg["data_api_username"]["show"] is False
    assert cfg["api_endpoint"]["required"] is True
    assert cfg["arango_url"]["required"] is False
    assert cfg["token"]["required"] is True


def test_arango_hides_astra_fields() -> None:
    comp = GraphRAGKBInstanceComponent()
    cfg = comp.update_build_config(_base_config(), "ArangoDB", "backend")
    assert cfg["arango_url"]["show"] is True
    assert cfg["arango_database"]["show"] is True
    assert cfg["vector_index_factory"]["show"] is True
    assert cfg["api_endpoint"]["show"] is False
    assert cfg["token"]["show"] is False
    assert cfg["data_api_environment"]["show"] is False
    assert cfg["data_api_username"]["show"] is False
    assert cfg["arango_url"]["required"] is True
    assert cfg["api_endpoint"]["required"] is False


def test_hcd_shows_username_password_only_on_astra() -> None:
    comp = GraphRAGKBInstanceComponent()
    cfg = _base_config()
    cfg = comp.update_build_config(cfg, "AstraDB", "backend")
    cfg = comp.update_build_config(cfg, "hcd", "data_api_environment")
    assert cfg["data_api_username"]["show"] is True
    assert cfg["data_api_password"]["show"] is True
    assert cfg["data_api_username"]["required"] is True
    assert cfg["token"]["required"] is False

    cfg = comp.update_build_config(cfg, "ArangoDB", "backend")
    assert cfg["data_api_username"]["show"] is False
    assert cfg["data_api_password"]["show"] is False
