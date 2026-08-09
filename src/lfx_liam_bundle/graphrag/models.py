"""GraphRAG Knowledge Model（对齐微软 GraphRAG 核心表结构）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DocumentRecord:
    """输入文档（Document ↔ TextUnit 溯源）。"""

    id: str
    text: str = ""
    title: str = ""
    text_unit_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TextUnit:
    """文本单元：正向挂 document_id，反向挂 entity/relationship/covariate ids。"""

    id: str
    text: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    document_id: str | None = None
    entity_ids: list[str] = field(default_factory=list)
    relationship_ids: list[str] = field(default_factory=list)
    covariate_ids: list[str] = field(default_factory=list)
    n_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Entity:
    id: str
    title: str
    type: str = "UNKNOWN"
    description: str = ""
    description_embedding: list[float] | None = None
    text_unit_ids: list[str] = field(default_factory=list)
    community_ids: list[str] = field(default_factory=list)
    rank: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Relationship:
    id: str
    source: str
    target: str
    description: str = ""
    weight: float = 1.0
    text_unit_ids: list[str] = field(default_factory=list)
    rank: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Covariate:
    """Claim / 事实声明（微软 GraphRAG 可选产物，可含时间界）。"""

    id: str
    subject: str
    object: str = ""
    type: str = "claim"
    status: str = "TRUE"
    description: str = ""
    start_date: str = ""
    end_date: str = ""
    text_unit_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Community:
    id: str
    level: int
    parent: str | None = None
    entity_ids: list[str] = field(default_factory=list)
    title: str = ""
    children: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommunityReport:
    id: str
    community_id: str
    level: int
    title: str
    summary: str
    full_content: str
    rank: float = 1.0
    embedding: list[float] | None = None
    entity_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphIndex:
    """一次完整索引流水线产物。"""

    text_units: list[TextUnit] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    communities: list[Community] = field(default_factory=list)
    community_reports: list[CommunityReport] = field(default_factory=list)
    covariates: list[Covariate] = field(default_factory=list)
    documents: list[DocumentRecord] = field(default_factory=list)

    def stats(self) -> dict[str, int]:
        levels = {c.level for c in self.communities}
        return {
            "text_units": len(self.text_units),
            "entities": len(self.entities),
            "relationships": len(self.relationships),
            "communities": len(self.communities),
            "community_levels": len(levels),
            "community_reports": len(self.community_reports),
            "covariates": len(self.covariates),
            "documents": len(self.documents),
            "entities_with_sources": sum(1 for e in self.entities if e.text_unit_ids),
            "text_units_with_entities": sum(1 for u in self.text_units if u.entity_ids),
        }


def merge_graph_indexes(base: GraphIndex, incoming: GraphIndex) -> GraphIndex:
    """按 id 合并两份索引（用于追加模式）；社区/报告需后续重建。"""

    def _by_id(items: list[Any]) -> dict[str, Any]:
        return {x.id: x for x in items if getattr(x, "id", None)}

    units = _by_id(base.text_units)
    units.update(_by_id(incoming.text_units))
    ents = _by_id(base.entities)
    for e in incoming.entities:
        if e.id in ents:
            old = ents[e.id]
            descs = [old.description, e.description]
            old.description = "；".join(d for d in descs if d)[:500]
            for uid in e.text_unit_ids:
                if uid not in old.text_unit_ids:
                    old.text_unit_ids.append(uid)
            old.rank = max(old.rank, e.rank)
            if e.description_embedding and not old.description_embedding:
                old.description_embedding = e.description_embedding
        else:
            ents[e.id] = e
    rels = _by_id(base.relationships)
    for r in incoming.relationships:
        if r.id in rels:
            old = rels[r.id]
            if r.description and r.description not in (old.description or ""):
                old.description = (old.description + "；" + r.description)[:500]
            old.weight = float(old.weight or 0) + float(r.weight or 0)
            for uid in r.text_unit_ids:
                if uid not in old.text_unit_ids:
                    old.text_unit_ids.append(uid)
        else:
            rels[r.id] = r
    covs = _by_id(base.covariates)
    covs.update(_by_id(incoming.covariates))
    docs = _by_id(base.documents)
    docs.update(_by_id(incoming.documents))
    return GraphIndex(
        text_units=list(units.values()),
        entities=list(ents.values()),
        relationships=list(rels.values()),
        covariates=list(covs.values()),
        documents=list(docs.values()),
        communities=[],
        community_reports=[],
    )
