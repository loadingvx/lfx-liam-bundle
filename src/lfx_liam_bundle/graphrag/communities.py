"""分层社区检测（Hierarchical Louvain，对齐 GraphRAG 分层社区思想）。

微软默认用 Hierarchical Leiden（graspologic）；为避免重型原生依赖，
此处用 networkx Louvain 做递归分层，产出多 level 社区供 Global/Local Search。

语义：
- level 0 = 最粗分区（Louvain 对全图的结果）
- 更大 level = 更细子社区
- 每个社区可有 parent/children，供 Global Search 动态社区选择
"""

from __future__ import annotations

from lfx_liam_bundle.graphrag.models import Community, Entity, Relationship


def _require_networkx():
    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities
    except ImportError as e:
        msg = (
            "缺少 networkx（分层社区检测依赖）。"
            f"请安装：pip install 'networkx>=3.2'（原始错误：{e}）"
        )
        raise ImportError(msg) from e
    return nx, louvain_communities


def _norm(title: str) -> str:
    return "".join((title or "").split()).casefold()


def build_entity_graph(entities: list[Entity], relationships: list[Relationship]):
    nx, _ = _require_networkx()
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
    """用度数 + 出现频次估算实体重要性。"""
    g = build_entity_graph(entities, relationships)
    for e in entities:
        degree = float(g.degree(e.id, weight="weight")) if g.has_node(e.id) else 0.0
        e.rank = degree + float(len(e.text_unit_ids))


def detect_hierarchical_communities(
    entities: list[Entity],
    relationships: list[Relationship],
    *,
    max_cluster_size: int = 10,
    max_levels: int = 3,
) -> list[Community]:
    _nx, louvain_communities = _require_networkx()
    g = build_entity_graph(entities, relationships)
    apply_entity_ranks(entities, relationships)
    if g.number_of_nodes() == 0:
        return []

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

        # 终止：达到层数上限或规模够小
        if level >= max_levels - 1 or len(nodes) <= max_cluster_size:
            _add(nodes, level, parent)
            return

        sub = g.subgraph(nodes).copy()
        if sub.number_of_edges() == 0:
            _add(nodes, level, parent)
            return

        parts = [list(p) for p in louvain_communities(sub, weight="weight", seed=42)]
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
    return communities


def community_levels(communities: list[Community]) -> list[int]:
    return sorted({c.level for c in communities})
