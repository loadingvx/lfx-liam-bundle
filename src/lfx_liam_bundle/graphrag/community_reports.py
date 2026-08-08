"""社区报告生成（对齐 GraphRAG Phase 5）。"""

from __future__ import annotations

from typing import Any

from lfx_liam_bundle.graphrag.llm_utils import invoke_llm
from lfx_liam_bundle.graphrag.models import (
    Community,
    CommunityReport,
    Covariate,
    Entity,
    Relationship,
)

REPORT_PROMPT = """你是知识图谱社区分析助手。根据下列社区内的实体、关系与事实声明，生成结构化中文社区报告。

社区层级: L{level}
实体列表:
{entities}

关系列表:
{relationships}

事实声明:
{claims}

请严格按以下格式输出（不要 Markdown 代码块）：
标题：...
摘要：...（不超过100字，概括社区主题）
报告：...（分点说明社区主题、关键实体、重要关系；200-400字）
"""


def _parse_report(text: str) -> tuple[str, str, str]:
    title, summary, full = "社区报告", "", text.strip()
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    body: list[str] = []
    mode = "body"
    for ln in lines:
        if ln.startswith("标题：") or ln.startswith("标题:"):
            title = ln.split("：", 1)[-1].split(":", 1)[-1].strip() or title
            mode = "title"
            continue
        if ln.startswith("摘要：") or ln.startswith("摘要:"):
            summary = ln.split("：", 1)[-1].split(":", 1)[-1].strip()
            mode = "summary"
            continue
        if ln.startswith("报告：") or ln.startswith("报告:"):
            rest = ln.split("：", 1)[-1].split(":", 1)[-1].strip()
            if rest:
                body.append(rest)
            mode = "body"
            continue
        if mode == "summary" and summary and not ln.startswith("报告"):
            summary = (summary + " " + ln).strip()
        else:
            body.append(ln)
    full = "\n".join(body).strip() or text.strip()
    if not summary:
        summary = full[:100]
    return title, summary, full


def generate_community_reports(
    llm: Any,
    communities: list[Community],
    entities: list[Entity],
    relationships: list[Relationship],
    covariates: list[Covariate] | None = None,
) -> list[CommunityReport]:
    if llm is None:
        msg = "生成社区报告需要 LLM。请连接语言模型后重试。"
        raise ValueError(msg)
    ent_by_id = {e.id: e for e in entities}
    covariates = covariates or []
    reports: list[CommunityReport] = []

    for community in communities:
        ents = [ent_by_id[i] for i in community.entity_ids if i in ent_by_id]
        if not ents:
            continue
        ent_titles = {e.title for e in ents}
        ent_titles_norm = {"".join(t.split()).casefold() for t in ent_titles}
        rels = [
            r
            for r in relationships
            if "".join(r.source.split()).casefold() in ent_titles_norm
            or "".join(r.target.split()).casefold() in ent_titles_norm
        ]
        claims = [
            c
            for c in covariates
            if "".join(c.subject.split()).casefold() in ent_titles_norm
            or any(
                "".join(c.subject.split()).casefold() in "".join(t.split()).casefold()
                for t in ent_titles
            )
        ]
        ent_block = "\n".join(f"- {e.title} ({e.type}): {e.description}" for e in ents[:40])
        rel_block = (
            "\n".join(
                f"- {r.source} -> {r.target}: {r.description} (w={r.weight})" for r in rels[:60]
            )
            or "（无明显关系）"
        )
        claim_block = (
            "\n".join(f"- [{c.status}] {c.subject}: {c.description}" for c in claims[:40])
            or "（无）"
        )
        prompt = REPORT_PROMPT.format(
            level=community.level,
            entities=ent_block,
            relationships=rel_block,
            claims=claim_block,
        )
        try:
            raw = invoke_llm(llm, prompt)
            title, summary, full = _parse_report(raw)
        except Exception as e:
            title = community.title or f"社区 L{community.level}"
            summary = f"社区包含 {len(ents)} 个实体、{len(rels)} 条关系。"
            full = summary + f"（报告生成失败，已使用降级摘要：{e}）"
        community.title = title
        reports.append(
            CommunityReport(
                id=f"report_{community.id}",
                community_id=community.id,
                level=community.level,
                title=title,
                summary=summary,
                full_content=full,
                rank=float(sum(e.rank for e in ents) or len(ents)),
                entity_ids=list(community.entity_ids),
            )
        )
    if not reports:
        msg = "未能生成任何社区报告。请确认实体抽取与社区检测是否成功。"
        raise ValueError(msg)
    return reports
