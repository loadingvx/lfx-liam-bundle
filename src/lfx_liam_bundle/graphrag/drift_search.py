"""DRIFT Search：社区报告 Primer + Local Follow-up（对齐微软 DRIFT 三阶段思路）。

A Primer：取 top-K 相关社区报告，生成初始答案与追问
B Follow-Up：对追问跑 Local Search，可多轮扩展
C Output：汇总为分层问答并生成最终答案
"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.kg_store import load_index
from lfx_liam_bundle.graphrag.llm_utils import invoke_llm, parse_json_payload
from lfx_liam_bundle.graphrag.local_search import _cosine, local_search
from lfx_liam_bundle.graphrag.models import CommunityReport, GraphIndex
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase
from lfx_liam_bundle.graphrag.vector_search import ann_search

PRIMER_PROMPT = """你是 GraphRAG DRIFT Search 的 Primer 阶段助手。
请仅依据给定社区报告，回答用户问题，并给出需要继续深挖的追问。

期望回答形式：{response_type}
{history_block}问题：{query}

社区报告：
{reports}

严格输出 JSON（不要 Markdown）：
{{
  "answer": "基于社区报告的初步回答；信息不足时明确说明",
  "confidence": 0到100的整数,
  "follow_ups": [
    {{"question": "追问", "score": 1到100的整数}}
  ]
}}
追问 2～5 个，应能通过局部实体/原文检索得到更具体事实。
"""

FOLLOWUP_REFINE_PROMPT = """你是 DRIFT Follow-Up 精炼助手。
根据「追问」与「局部检索答案」，判断是否还要继续追问。

原问题：{root_query}
当前追问：{follow_up}
局部答案：
{local_answer}

输出 JSON：
{{
  "confidence": 0到100的整数,
  "follow_ups": [{{"question": "更具体的追问", "score": 1到100的整数}}]
}}
若已足够，follow_ups 可为 []。
"""

REDUCE_PROMPT = """你是 GraphRAG DRIFT Search 的汇总助手。
下面是 Primer 与多轮 Local Follow-Up 的分层结果。请综合给出最终答案。
不要编造知识库外事实；可引用各节点要点。
期望回答形式：{response_type}
{history_block}用户原问题：{query}

分层结果：
{hierarchy}

请输出最终答案。
"""


def _history_block(history: str | None) -> str:
    h = (history or "").strip()
    return f"对话历史：\n{h}\n\n" if h else ""


def _rank_reports(
    index: GraphIndex,
    query_vec: list[float],
    kb: GraphRAGKnowledgeBase,
    *,
    top_k: int,
) -> tuple[list[CommunityReport], str]:
    """优先 ANN 报告；失败则内存余弦。"""
    by_id = {r.id: r for r in index.community_reports}
    if kb.use_vector_index and index.community_reports:
        try:
            hits = ann_search(kb, query_vec, target="reports", top_k=top_k)
            ranked = [by_id[i] for i, _ in hits if i in by_id]
            if ranked:
                return ranked, "ann"
        except Exception:
            pass
    scored = sorted(
        index.community_reports,
        key=lambda r: _cosine(query_vec, r.embedding),
        reverse=True,
    )
    return scored[:top_k], "exact_cosine"


def _format_reports(reports: list[CommunityReport]) -> str:
    blocks = []
    for r in reports:
        blocks.append(f"### {r.title}\n摘要：{r.summary}\n{r.full_content}")
    return "\n\n".join(blocks) if blocks else "（无社区报告）"


def drift_search(
    kb: GraphRAGKnowledgeBase,
    query: str,
    embedding: Embeddings,
    llm: Any,
    *,
    n_depth: int = 2,
    top_k_reports: int = 5,
    top_k_entities: int = 8,
    top_k_chunks: int = 6,
    max_follow_ups: int = 3,
    min_follow_up_score: int = 40,
    max_context_tokens: int = 8000,
    text_unit_prop: float = 0.5,
    community_prop: float = 0.25,
    conversation_history: str | None = None,
    response_type: str = "Multi-paragraph answer",
) -> tuple[list[Document], str, dict[str, Any]]:
    if llm is None:
        msg = "DRIFT Search requires an LLM (Primer / Follow-Up / Reduce)."
        raise ValueError(msg)
    if embedding is None:
        msg = "DRIFT Search requires Embedding (community reports and Local entry)."
        raise ValueError(msg)

    index = load_index(kb)
    if not index.community_reports:
        msg = "No community reports; cannot run DRIFT Search. Index documents first."
        raise ValueError(msg)

    qvec = embedding.embed_query(query)
    # 补全缺失报告向量，便于回退余弦
    missing = [r for r in index.community_reports if not r.embedding]
    if missing:
        vectors = embedding.embed_documents(
            [f"{r.title}\n{r.summary}\n{r.full_content}" for r in missing]
        )
        for r, vec in zip(missing, vectors, strict=True):
            r.embedding = vec

    primer_reports, report_rank = _rank_reports(
        index, qvec, kb, top_k=max(1, int(top_k_reports))
    )
    primer_raw = invoke_llm(
        llm,
        PRIMER_PROMPT.format(
            query=query,
            reports=_format_reports(primer_reports),
            response_type=response_type or "Multi-paragraph answer",
            history_block=_history_block(conversation_history),
        ),
    )
    try:
        primer = parse_json_payload(primer_raw) or {}
        if not isinstance(primer, dict):
            primer = {}
    except ValueError:
        # 模型未按 JSON 输出时降级：把原文当初步答案，并给默认追问，避免整条 DRIFT 失败
        primer = {
            "answer": (primer_raw or "").strip() or "Community reports are insufficient; continuing with local retrieval.",
            "confidence": 40,
            "follow_ups": [
                {"question": query, "score": 80},
            ],
        }
    primer_answer = str(primer.get("answer") or primer_raw).strip()
    try:
        primer_conf = int(primer.get("confidence") or 50)
    except (TypeError, ValueError):
        primer_conf = 50

    follow_ups: list[dict[str, Any]] = []
    for item in primer.get("follow_ups") or []:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question") or "").strip()
        if not q:
            continue
        try:
            score = int(item.get("score") or 50)
        except (TypeError, ValueError):
            score = 50
        follow_ups.append({"question": q, "score": score})
    if not follow_ups:
        follow_ups = [{"question": query, "score": 70}]
    follow_ups = sorted(follow_ups, key=lambda x: x["score"], reverse=True)[
        : max(1, int(max_follow_ups))
    ]

    hierarchy: list[dict[str, Any]] = [
        {
            "phase": "primer",
            "answer": primer_answer,
            "confidence": primer_conf,
            "reports": [r.id for r in primer_reports],
            "follow_ups": list(follow_ups),
            "report_ranking": report_rank,
        }
    ]
    all_docs: list[Document] = [
        Document(
            page_content=r.summary or r.full_content,
            metadata={"kind": "community_report", "id": r.id, "title": r.title},
            id=r.id,
        )
        for r in primer_reports
    ]

    queue = [fu for fu in follow_ups if fu["score"] >= int(min_follow_up_score)]
    depth = max(0, int(n_depth))
    for d in range(depth):
        if not queue:
            break
        next_queue: list[dict[str, Any]] = []
        for fu in queue[: max(1, int(max_follow_ups))]:
            local_docs, local_text, local_meta = local_search(
                kb,
                fu["question"],
                embedding,
                llm=llm,
                top_k_entities=top_k_entities,
                top_k_chunks=top_k_chunks,
                answer_with_llm=True,
                max_context_tokens=max_context_tokens,
                text_unit_prop=text_unit_prop,
                community_prop=community_prop,
                conversation_history=conversation_history,
                response_type="Concise bullet points",
            )
            all_docs.extend(local_docs)
            refine_raw = invoke_llm(
                llm,
                FOLLOWUP_REFINE_PROMPT.format(
                    root_query=query,
                    follow_up=fu["question"],
                    local_answer=local_text,
                ),
            )
            refine = parse_json_payload(refine_raw) or {}
            try:
                conf = int(refine.get("confidence") or local_meta.get("entities") or 50)
            except (TypeError, ValueError):
                conf = 50
            node = {
                "phase": f"follow_up_d{d + 1}",
                "question": fu["question"],
                "score": fu["score"],
                "answer": local_text,
                "confidence": conf,
                "local_meta": {
                    "entities": local_meta.get("entities"),
                    "text_units": local_meta.get("text_units"),
                    "vector_ranking": local_meta.get("vector_ranking"),
                },
                "follow_ups": [],
            }
            for item in refine.get("follow_ups") or []:
                if not isinstance(item, dict):
                    continue
                nq = str(item.get("question") or "").strip()
                if not nq:
                    continue
                try:
                    nscore = int(item.get("score") or 50)
                except (TypeError, ValueError):
                    nscore = 50
                if nscore >= int(min_follow_up_score):
                    next_queue.append({"question": nq, "score": nscore})
                    node["follow_ups"].append({"question": nq, "score": nscore})
            hierarchy.append(node)
        # 去重追问
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in sorted(next_queue, key=lambda x: x["score"], reverse=True):
            key = "".join(item["question"].split()).casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        queue = deduped[: max(1, int(max_follow_ups))]

    hier_text_parts = []
    for node in hierarchy:
        if node["phase"] == "primer":
            hier_text_parts.append(
                f"[Primer|confidence={node['confidence']}]\n{node['answer']}"
            )
        else:
            hier_text_parts.append(
                f"[{node['phase']}|q={node['question']}|confidence={node['confidence']}]\n"
                f"{node['answer']}"
            )
    final = invoke_llm(
        llm,
        REDUCE_PROMPT.format(
            query=query,
            hierarchy="\n\n---\n\n".join(hier_text_parts),
            response_type=response_type or "Multi-paragraph answer",
            history_block=_history_block(conversation_history),
        ),
    )
    meta = {
        "mode": "drift_search",
        "primer_reports": len(primer_reports),
        "report_ranking": report_rank,
        "n_depth": depth,
        "hierarchy_nodes": len(hierarchy),
        "hierarchy": hierarchy,
        "avg_confidence": round(
            sum(float(n.get("confidence") or 0) for n in hierarchy)
            / max(1, len(hierarchy)),
            2,
        ),
    }
    # 文档去重
    uniq_docs: list[Document] = []
    seen_ids: set[str] = set()
    for doc in all_docs:
        did = str(doc.id or doc.metadata.get("id") or "")
        if did and did in seen_ids:
            continue
        if did:
            seen_ids.add(did)
        uniq_docs.append(doc)
    return uniq_docs, final.strip(), meta
