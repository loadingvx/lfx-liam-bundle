"""分层社区检测：优先 Hierarchical Leiden（leidenalg），失败则 Louvain。"""

from __future__ import annotations

from typing import Any

from lfx_liam_bundle.graphrag.models import Community, Entity, Relationship


def _norm(title: str) -> str:
    return "".join((title or "").split()).casefold()


def build_entity_graph(entities: list[Entity], relationships: list[Relationship]):
    import networkx as nx

    g = nx.Graph()
    title_to_id = {_norm(e.title): e.id for e in entities}
    for e in entities:
        g.add_node(e.id, title=e.title, type=e.type)
    for r in relationships:
        s = title_to_id.get(_norm(r.source))
        t = title_to_id.get(_norm(r.target))
        if not s or not t or s == t:
            continue
        w = float(r.weight or 1.0)
        if g.has_edge(s, t):
            g[s][t]["weight"] += w
        else:
            g.add_edge(s, t, weight=w)
    return g


def apply_entity_ranks(entities: list[Entity], relationships: list[Relationship]) -> None:
    g = build_entity_graph(entities, relationships)
    for e in entities:
        degree = float(g.degree(e.id, weight="weight")) if g.has_node(e.id) else 0.0
        e.rank = degree + float(len(e.text_unit_ids))


def _nx_to_igraph(g):
    import igraph as ig

    nodes = list(g.nodes())
    index = {n: i for i, n in enumerate(nodes)}
    edges = [(index[u], index[v]) for u, v in g.edges()]
    weights = [float(g[u][v].get("weight", 1.0)) for u, v in g.edges()]
    ig_g = ig.Graph(n=len(nodes), edges=edges, directed=False)
    if weights:
        ig_g.es["weight"] = weights
    return ig_g, nodes


def _partition_leiden(sub_nodes: list[str], g) -> list[list[str]] | None:
    try:
        import leidenalg as la
    except ImportError:
        return None
    if len(sub_nodes) <= 1:
        return [sub_nodes]
    sub = g.subgraph(sub_nodes).copy()
    if sub.number_of_edges() == 0:
        return [sub_nodes]
    ig_g, nodes = _nx_to_igraph(sub)
    try:
        part = la.find_partition(
            ig_g,
            la.ModularityVertexPartition,
            weights="weight" if ig_g.ecount() and "weight" in ig_g.es.attributes() else None,
            seed=42,
        )
    except Exception:  # noqa: BLE001
        return None
    groups: dict[int, list[str]] = {}
    for vid, cid in enumerate(part.membership):
        groups.setdefault(int(cid), []).append(nodes[vid])
    return list(groups.values())


def _partition_louvain(sub_nodes: list[str], g) -> list[list[str]]:
    from networkx.algorithms.community import louvain_communities

    sub = g.subgraph(sub_nodes).copy()
    if sub.number_of_edges() == 0:
        return [sub_nodes]
    parts = [list(p) for p in louvain_communities(sub, weight="weight", seed=42)]
    return parts or [sub_nodes]


def detect_hierarchical_communities(
    entities: list[Entity],
    relationships: list[Relationship],
    *,
    max_cluster_size: int = 10,
    max_levels: int = 3,
) -> tuple[list[Community], dict[str, Any]]:
    """递归分层社区。优先 Leiden，否则 Louvain。"""
    g = build_entity_graph(entities, relationships)
    apply_entity_ranks(entities, relationships)
    if g.number_of_nodes() == 0:
        return [], {"algorithm": "none"}

    try:
        import leidenalg as _la  # noqa: F401
        import igraph as _ig  # noqa: F401

        algorithm = "hierarchical_leiden"
    except ImportError:
        algorithm = "hierarchical_louvain"

    communities: list[Community] = []
    by_id: dict[str, Community] = {}

    def _add(nodes: list[str], level: int, parent: str | None) -> str:
        cid = f"comm_L{level}_{len(communities)}"
        community = Community(
            id=cid,
            level=level,
            parent=parent,
            entity_ids=list(nodes),
            title=f"社区 L{level}-{len(communities)}",
        )
        communities.append(community)
        by_id[cid] = community
        if parent and parent in by_id and cid not in by_id[parent].children:
            by_id[parent].children.append(cid)
        return cid

    def _split(nodes: list[str], level: int, parent: str | None) -> None:
        if not nodes:
            return
        if level >= max_levels - 1 or len(nodes) <= max_cluster_size:
            _add(nodes, level, parent)
            return

        if algorithm == "hierarchical_leiden":
            parts = _partition_leiden(nodes, g) or [nodes]
        else:
            parts = _partition_louvain(nodes, g)

        if len(parts) <= 1:
            _add(nodes, level, parent)
            return

        for part_nodes in parts:
            if not part_nodes:
                continue
            cid = _add(part_nodes, level, parent)
            if len(part_nodes) > max_cluster_size and level + 1 < max_levels:
                _split(part_nodes, level + 1, parent=cid)

    _split(list(g.nodes()), level=0, parent=None)

    ent_by_id = {e.id: e for e in entities}
    for e in entities:
        e.community_ids = []
    for c in communities:
        for eid in c.entity_ids:
            ent = ent_by_id.get(eid)
            if ent and c.id not in ent.community_ids:
                ent.community_ids.append(c.id)

    return communities, {"algorithm": algorithm, "communities": len(communities)}


def community_levels(communities: list[Community]) -> list[int]:
    return sorted({c.level for c in communities})
