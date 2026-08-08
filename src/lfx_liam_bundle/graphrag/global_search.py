"""Global Search：社区报告 Map-Reduce（对齐微软 Global Search）。

支持：
- 固定社区层级（community_level）
- 动态社区选择（从粗到细剪枝无关子树，降低成本）
"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from lfx_liam_bundle.graphrag.kg_store import load_index
from lfx_liam_bundle.graphrag.llm_utils import invoke_llm, parse_json_payload
from lfx_liam_bundle.graphrag.models import Community, CommunityReport, GraphIndex
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

MAP_PROMPT = """你是 GraphRAG Global Search 的 Map 阶段助手。
根据社区报告回答问题，只使用报告中的信息。

问题：{query}

社区报告：
{report}

输出 JSON：
{{
  "points": [{{"description": "要点", "score": 1到100的整数}}]
}}
若报告与问题无关，返回 {{"points": []}}
"""

REDUCE_PROMPT = """你是 GraphRAG Global Search 的 Reduce 阶段助手。
下面是多个社区报告产生的要点（含重要性评分）。请综合评分较高的要点，给出最终中文回答。
不要编造数据集之外的事实。若信息不足，明确说明。

问题：{query}

要点列表：
{points}

请输出最终答案（可多段）。
"""

RELEVANCE_PROMPT = """判断下列社区报告是否有助于回答用户问题。
只输出 JSON：{{"relevant": true或false, "score": 0到100的整数}}

问题：{query}

社区标题：{title}
社区摘要：{summary}
"""


def _chunk_reports(
    reports: list[CommunityReport], batch_size: int = 3
) -> list[list[CommunityReport]]:
    batches: list[list[CommunityReport]] = []
    for i in range(0, len(reports), max(1, batch_size)):
        batches.append(reports[i : i + batch_size])
    return batches


def select_level_reports(index: GraphIndex, level: int | None) -> list[CommunityReport]:
    if not index.community_reports:
        msg = "知识库中没有社区报告。请先完成完整 GraphRAG「入库建图」（含社区摘要）。"
        raise ValueError(msg)
    levels = sorted({r.level for r in index.community_reports})
    chosen = level if level is not None else levels[0]
    reports = [r for r in index.community_reports if r.level == chosen]
    if not reports:
        nearest = min(levels, key=lambda x: abs(x - chosen))
        reports = [r for r in index.community_reports if r.level == nearest]
    return reports


def _report_by_community(index: GraphIndex) -> dict[str, CommunityReport]:
    return {r.community_id: r for r in index.community_reports}


def _community_by_id(index: GraphIndex) -> dict[str, Community]:
    return {c.id: c for c in index.communities}


def select_reports_dynamically(
    index: GraphIndex,
    query: str,
    llm: Any,
    *,
    relevance_threshold: int = 50,
) -> list[CommunityReport]:
    """从 level0 向下：无关则剪枝，相关则优先深入子社区。"""
    if not index.community_reports:
        msg = "知识库中没有社区报告，无法执行动态 Global Search。"
        raise ValueError(msg)
    reports_map = _report_by_community(index)
    communities = _community_by_id(index)
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
            relevant = bool(payload.get("relevant"))
            return relevant or score >= relevance_threshold
        except Exception:
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
        child_ids = community.children or []
        child_communities = [communities[i] for i in child_ids if i in communities]
        if child_communities:
            before = len(selected)
            for child in child_communities:
                _walk(child)
            if len(selected) == before:
                # 子社区都未贡献，保留当前层报告
                selected.append(report)
        else:
            selected.append(report)

    for root in roots:
        _walk(root)

    if not selected:
        # 降级：使用最粗层级全部报告
        return select_level_reports(index, 0)
    # 去重
    seen: set[str] = set()
    unique: list[CommunityReport] = []
    for r in selected:
        if r.id in seen:
            continue
        seen.add(r.id)
        unique.append(r)
    return unique


def global_search(
    kb: GraphRAGKnowledgeBase,
    query: str,
    llm: Any,
    *,
    community_level: int | None = 0,
    map_batch_size: int = 2,
    top_points: int = 20,
    dynamic_community_selection: bool = False,
) -> tuple[list[Document], str, dict[str, Any]]:
    if llm is None:
        msg = "Global Search 需要 LLM（Map-Reduce）。请在检索组件连接语言模型。"
        raise ValueError(msg)
    if not (query or "").strip():
        msg = "检索问题不能为空。"
        raise ValueError(msg)

    index = load_index(kb)
    if not index.community_reports:
        msg = (
            "知识库尚未生成社区报告，无法 Global Search。请先用「入库建图」完成完整 GraphRAG 索引。"
        )
        raise ValueError(msg)

    if dynamic_community_selection:
        reports = select_reports_dynamically(index, query, llm)
        selection_mode = "dynamic"
    else:
        reports = select_level_reports(index, community_level)
        selection_mode = f"level_{reports[0].level if reports else community_level}"

    batches = _chunk_reports(reports, batch_size=map_batch_size)
    points: list[dict[str, Any]] = []
    for batch in batches:
        report_text = "\n\n".join(
            f"# {r.title}\n层级: L{r.level}\n摘要: {r.summary}\n{r.full_content}" for r in batch
        )
        prompt = MAP_PROMPT.format(query=query, report=report_text[:8000])
        try:
            raw = invoke_llm(llm, prompt)
            payload = parse_json_payload(raw)
            batch_points = payload.get("points") if isinstance(payload, dict) else []
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
        except Exception:
            for r in batch:
                points.append({"description": f"{r.title}: {r.summary}", "score": int(r.rank or 1)})

    points = sorted(points, key=lambda p: p.get("score", 0), reverse=True)[:top_points]
    if not points:
        msg = (
            "Global Search 未能从社区报告中提取到有效要点。"
            "可尝试：开启动态社区选择、更换社区层级，或重新建图提高报告质量。"
        )
        raise ValueError(msg)

    points_block = "\n".join(f"- ({p['score']}) {p['description']}" for p in points)
    answer = invoke_llm(llm, REDUCE_PROMPT.format(query=query, points=points_block))

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
        "answer": answer,
    }
    return docs, answer, meta
