"""FastGraphRAG 风格抽取：NLP 名词短语 + 共现关系（对齐微软 FastGraphRAG 思路）。

用正则/停用词实现中英轻量抽取，避免强制引入 spaCy/NLTK 重依赖。
实体描述直接取来源 TextUnit 片段；关系无自然语言描述，权重为共现次数。
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict

from lfx_liam_bundle.graphrag.models import Entity, Relationship, TextUnit

_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")
_EN_MULTI_RE = re.compile(r"\b(?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)+)\b")
_EN_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_\-]{3,}\b")

_STOP_ZH = {
    "我们",
    "你们",
    "他们",
    "它们",
    "这个",
    "那个",
    "这些",
    "那些",
    "一个",
    "一些",
    "可以",
    "已经",
    "没有",
    "不是",
    "以及",
    "或者",
    "因为",
    "所以",
    "如果",
    "但是",
    "然后",
    "进行",
    "通过",
    "关于",
    "其中",
    "其他",
    "自己",
    "什么",
    "如何",
    "怎么",
    "这样",
    "那样",
    "方面",
    "问题",
    "情况",
    "时候",
    "今天",
    "目前",
    "现在",
    "需要",
    "可能",
    "应该",
    "能够",
}
_STOP_EN = {
    "this",
    "that",
    "these",
    "those",
    "with",
    "from",
    "into",
    "about",
    "have",
    "has",
    "had",
    "were",
    "was",
    "been",
    "being",
    "will",
    "would",
    "could",
    "should",
    "their",
    "there",
    "which",
    "where",
    "when",
    "what",
    "your",
    "ours",
    "them",
    "then",
    "than",
    "also",
    "only",
    "just",
    "more",
    "most",
    "such",
    "using",
    "used",
    "use",
    "via",
    "and",
    "the",
    "for",
    "are",
    "not",
}


def _norm_title(title: str) -> str:
    return "".join((title or "").split()).casefold()


def _entity_id(title: str) -> str:
    return "ent_" + hashlib.sha1(_norm_title(title).encode("utf-8")).hexdigest()[:16]


def _rel_id(source: str, target: str) -> str:
    a, b = sorted([_norm_title(source), _norm_title(target)])
    return "rel_" + hashlib.sha1(f"{a}|{b}".encode()).hexdigest()[:16]


def extract_noun_phrases(text: str, *, max_phrases: int = 40) -> list[str]:
    """从单段文本抽取候选实体名（中英）。"""
    text = (text or "").strip()
    if not text:
        return []
    found: list[str] = []
    for m in _CJK_RE.finditer(text):
        phrase = m.group(0)
        if phrase in _STOP_ZH:
            continue
        found.append(phrase)
    for m in _EN_MULTI_RE.finditer(text):
        found.append(m.group(0).strip())
    for m in _EN_TOKEN_RE.finditer(text):
        tok = m.group(0)
        if tok.casefold() in _STOP_EN:
            continue
        # 全大写缩写或首字母大写更像实体；小写长词也保留但靠频次过滤
        found.append(tok)

    counts = Counter(found)
    # 频次优先，其次更长的短语
    ranked = sorted(counts.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    out: list[str] = []
    seen: set[str] = set()
    for phrase, _n in ranked:
        key = _norm_title(phrase)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(phrase)
        if len(out) >= max_phrases:
            break
    return out


def extract_graph_fast(
    units: list[TextUnit],
    *,
    min_entity_freq: int = 1,
    max_entities_per_unit: int = 24,
) -> tuple[list[Entity], list[Relationship], dict[str, int | str]]:
    """FastGraphRAG：名词短语实体 + 同 TextUnit 共现关系。"""
    if not units:
        msg = "没有文本单元，无法 FastGraphRAG 建图。"
        raise ValueError(msg)

    title_units: dict[str, list[str]] = defaultdict(list)
    title_display: dict[str, str] = {}
    title_freq: Counter[str] = Counter()
    cooccur: Counter[tuple[str, str]] = Counter()
    pair_units: dict[tuple[str, str], list[str]] = defaultdict(list)

    for u in units:
        phrases = extract_noun_phrases(u.text, max_phrases=max_entities_per_unit)
        norms = []
        for p in phrases:
            key = _norm_title(p)
            if not key:
                continue
            title_freq[key] += 1
            title_display.setdefault(key, p)
            if u.id not in title_units[key]:
                title_units[key].append(u.id)
            norms.append(key)
        uniq = list(dict.fromkeys(norms))
        for i, a in enumerate(uniq):
            for b in uniq[i + 1 :]:
                pair = tuple(sorted((a, b)))
                cooccur[pair] += 1
                if u.id not in pair_units[pair]:
                    pair_units[pair].append(u.id)

    entities: list[Entity] = []
    for key, freq in title_freq.items():
        if freq < min_entity_freq:
            continue
        title = title_display[key]
        unit_ids = title_units[key]
        # 描述：拼接来源片段（微软 FastGraphRAG：无独立描述，用源文本）
        snippets = []
        for uid in unit_ids[:3]:
            unit = next((x for x in units if x.id == uid), None)
            if unit and unit.text:
                snippets.append(unit.text[:180].replace("\n", " "))
        description = " | ".join(snippets)[:500] if snippets else title
        entities.append(
            Entity(
                id=_entity_id(title),
                title=title,
                type="NOUN_PHRASE",
                description=description,
                text_unit_ids=list(unit_ids),
                rank=float(freq),
            )
        )

    if not entities:
        msg = (
            "FastGraphRAG 未能抽取出实体。请确认文档含中文词组或英文专有名词，"
            "或改用「标准 GraphRAG」建图模式。"
        )
        raise ValueError(msg)

    kept = {_norm_title(e.title) for e in entities}
    relationships: list[Relationship] = []
    for (a, b), weight in cooccur.items():
        if a not in kept or b not in kept:
            continue
        sa, sb = title_display[a], title_display[b]
        relationships.append(
            Relationship(
                id=_rel_id(sa, sb),
                source=sa,
                target=sb,
                description=f"共现于同一文本单元（次数={weight}）",
                weight=float(weight),
                text_unit_ids=list(pair_units[(a, b)]),
                rank=float(weight),
            )
        )

    stats: dict[str, int | str] = {
        "method": "fast_graphrag",
        "entities": len(entities),
        "relationships": len(relationships),
        "text_units": len(units),
        "gleanings": 0,
    }
    return entities, relationships, stats
