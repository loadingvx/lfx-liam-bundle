"""Global Search：社区报告 Map-Reduce（token 预算、打乱 batch、可选动态社区）。"""

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from langchain_core.documents import Document

from lfx_liam_bundle.graphrag.kg_store import load_index
from lfx_liam_bundle.graphrag.llm_utils import invoke_llm, parse_json_payload
from lfx_liam_bundle.graphrag.models import Community, CommunityReport, GraphIndex
from lfx_liam_bundle.graphrag.tokens import count_tokens, join_under_budget, truncate_to_tokens
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

MAP_PROMPT = """你是 GraphRAG Global Search 的 Map 阶段助手。
根据社区报告回答问题，只使用报告中的信息。
{history_block}问题：{query}

社区报告：
{report}

输出 JSON：
{{
  "points": [{{"description": "要点", "score": 1到100的整数}}]
}}
若报告与问题无关，返回 {{"points": []}}
"""

REDUCE_PROMPT = """你是 GraphRAG Global Search 的 Reduce 阶段助手。
下面是多个社区报告产生的要点（含重要性评分）。请综合评分较高的要点，给出最终回答。
不要编造数据集之外的事实。若信息不足，明确说明。
期望回答形式：{response_type}
{general_knowledge_note}
{history_block}问题：{query}

要点列表：
{points}

请输出最终答案。
"""

RELEVANCE_PROMPT = """判断下列社区报告是否有助于回答用户问题。
只输出 JSON：{{"relevant": true或false, "score": 0到100的整数}}

问题：{query}
社区标题：{title}
社区摘要：{summary}
"""


def _history_block(history: str | None) -> str:
    h = (history or "").strip()
    return f"对话历史：\n{h}\n\n" if h else ""


def _chunk_reports_by_tokens(
    reports: list[CommunityReport], *, max_tokens_per_batch: int
) -> list[list[CommunityReport]]:
    batches: list[list[CommunityReport]] = []
    current: list[CommunityReport] = []
    used = 0
    for r in reports:
        block_tokens = count_tokens(f"{r.title}\n{r.summary}\n{r.full_content}")
        if current and used + block_tokens > max_tokens_per_batch:
            batches.append(current)
            current = []
            used = 0
        current.append(r)
        used += block_tokens
    if current:
        batches.append(current)
    return batches


def select_level_reports(index: GraphIndex, level: int | None) -> list[CommunityReport]:
    if not index.community_reports:
        msg = "No community reports in the knowledge base. Complete GraphRAG Index Builder first."
        raise ValueError(msg)
    levels = sorted({r.level for r in index.community_reports})
    chosen = level if level is not None else levels[0]
    reports = [r for r in index.community_reports if r.level == chosen]
    if not reports:
        nearest = min(levels, key=lambda x: abs(x - chosen))
        reports = [r for r in index.community_reports if r.level == nearest]
    return reports


def select_reports_dynamically(
    index: GraphIndex,
    query: str,
    llm: Any,
    *,
    relevance_threshold: int = 50,
) -> list[CommunityReport]:
    if not index.community_reports:
        msg = "No community reports; cannot run dynamic Global Search."
        raise ValueError(msg)
    reports_map = {r.community_id: r for r in index.community_reports}
    communities = {c.id: c for c in index.communities}
    roots = [c for c in index.communities if c.parent is None] or list(index.communities)
    selected: list[CommunityReport] = []

    def _is_relevant(report: CommunityReport) -> bool:
        prompt = RELEVANCE_PROMPT.format(
            query=query, title=report.title, summary=report.summary[:800]
        )
        try:
            payload = parse_json_payload(invoke_llm(llm, prompt))
            if not isinstance(payload, dict):
                return True
            score = int(payload.get("score") or 0)
            return bool(payload.get("relevant")) or score >= relevance_threshold
        except Exception:  # noqa: BLE001
            return True

    def _walk(community: Community) -> None:
        report = reports_map.get(community.id)
        if report is None:
            for child_id in community.children:
                child = communities.get(child_id)
                if child:
                    _walk(child)
            return
        if not _is_relevant(report):
            return
        child_communities = [communities[i] for i in (community.children or []) if i in communities]
        if child_communities:
            before = len(selected)
            for child in child_communities:
                _walk(child)
            if len(selected) == before:
                selected.append(report)
        else:
            selected.append(report)

    for root in roots:
        _walk(root)
    if not selected:
        return select_level_reports(index, 0)
    seen: set[str] = set()
    unique: list[CommunityReport] = []
    for r in selected:
        if r.id in seen:
            continue
        seen.add(r.id)
        unique.append(r)
    return unique


def _map_batch(
    llm: Any,
    query: str,
    batch: list[CommunityReport],
    *,
    history: str | None,
    max_report_tokens: int,
) -> list[dict[str, Any]]:
    report_text = "\n\n".join(
        f"# {r.title}\n层级: L{r.level}\n摘要: {r.summary}\n{r.full_content}" for r in batch
    )
    report_text = truncate_to_tokens(report_text, max_report_tokens)
    prompt = MAP_PROMPT.format(
        query=query, report=report_text, history_block=_history_block(history)
    )
    try:
        raw = invoke_llm(llm, prompt)
        payload = parse_json_payload(raw)
        batch_points = payload.get("points") if isinstance(payload, dict) else []
        points: list[dict[str, Any]] = []
        if isinstance(batch_points, list):
            for p in batch_points:
                if not isinstance(p, dict):
                    continue
                desc = str(p.get("description") or "").strip()
                if not desc:
                    continue
                try:
                    score = int(p.get("score") or 0)
                except (TypeError, ValueError):
                    score = 0
                points.append({"description": desc, "score": score})
        return points
    except Exception:  # noqa: BLE001
        return [{"description": f"{r.title}: {r.summary}", "score": int(r.rank or 1)} for r in batch]


def global_search(
    kb: GraphRAGKnowledgeBase,
    query: str,
    llm: Any,
    *,
    community_level: int | None = 0,
    map_batch_size: int = 2,
    top_points: int = 20,
    dynamic_community_selection: bool = False,
    max_data_tokens: int = 8000,
    conversation_history: str | None = None,
    response_type: str = "Multi-paragraph answer",
    allow_general_knowledge: bool = False,
    map_concurrency: int = 1,
) -> tuple[list[Document], str, dict[str, Any]]:
    if llm is None:
        msg = "Global Search needs an LLM (Map-Reduce). Connect a language model on Retrieve."
        raise ValueError(msg)
    if not (query or "").strip():
        msg = "Search query cannot be empty."
        raise ValueError(msg)

    index = load_index(kb)
    if not index.community_reports:
        msg = "No community reports yet; cannot run Global Search. Index documents first."
        raise ValueError(msg)

    if dynamic_community_selection:
        reports = select_reports_dynamically(index, query, llm)
        selection_mode = "dynamic"
    else:
        reports = select_level_reports(index, community_level)
        selection_mode = f"level_{reports[0].level if reports else community_level}"

    # 打乱顺序，降低位置偏差（对齐微软 shuffled community report batches）
    shuffled = list(reports)
    random.Random(42).shuffle(shuffled)

    # 按 token 分 batch；map_batch_size 作为下限条数提示
    per_batch = max(512, int(max_data_tokens / max(1, (len(shuffled) // max(1, map_batch_size)) or 1)))
    per_batch = min(per_batch, max(512, max_data_tokens // 2))
    batches = _chunk_reports_by_tokens(shuffled, max_tokens_per_batch=per_batch)

    points: list[dict[str, Any]] = []
    concurrency = max(1, int(map_concurrency or 1))
    if concurrency == 1:
        for batch in batches:
            points.extend(
                _map_batch(
                    llm,
                    query,
                    batch,
                    history=conversation_history,
                    max_report_tokens=per_batch,
                )
            )
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futs = [
                pool.submit(
                    _map_batch,
                    llm,
                    query,
                    batch,
                    history=conversation_history,
                    max_report_tokens=per_batch,
                )
                for batch in batches
            ]
            for fut in as_completed(futs):
                points.extend(fut.result())

    points = sorted(points, key=lambda p: p.get("score", 0), reverse=True)[:top_points]
    if not points:
        msg = "Global Search found no usable points from community reports. Try dynamic community selection or another community level."
        raise ValueError(msg)

    points_block = join_under_budget(
        [f"- ({p['score']}) {p['description']}" for p in points],
        max_tokens=max(256, max_data_tokens // 2),
    )
    gk_note = (
        "You may lightly use general world knowledge for explanation, but mark what comes from the dataset vs general knowledge."
        if allow_general_knowledge
        else "Do not introduce general knowledge outside the dataset."
    )
    answer = invoke_llm(
        llm,
        REDUCE_PROMPT.format(
            query=query,
            points=points_block,
            response_type=response_type or "Multi-paragraph answer",
            general_knowledge_note=gk_note,
            history_block=_history_block(conversation_history),
        ),
    )

    docs = [
        Document(
            page_content=r.full_content,
            metadata={"kind": "community_report", "title": r.title, "level": r.level, "id": r.id},
            id=r.id,
        )
        for r in reports
    ]
    meta = {
        "mode": "global_search",
        "selection": selection_mode,
        "community_level": reports[0].level if reports else community_level,
        "reports_used": len(reports),
        "map_batches": len(batches),
        "points": len(points),
        "max_data_tokens": max_data_tokens,
        "map_concurrency": concurrency,
        "answer": answer,
    }
    return docs, answer, meta
