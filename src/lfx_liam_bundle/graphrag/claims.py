"""Claim / Covariate 抽取（可选；含时间界字段）。"""

from __future__ import annotations

import hashlib
from typing import Any

from lfx_liam_bundle.graphrag.llm_utils import invoke_llm, parse_json_payload
from lfx_liam_bundle.graphrag.models import Covariate, TextUnit

CLAIM_PROMPT = """你是事实声明抽取助手。从文本中抽取可核验的事实声明（claims）。
每条声明包含：主体(subject)、客体(object，可空)、状态(TRUE/FALSE/SUSPECTED)、
描述、可选时间界 start_date/end_date（ISO 日期或原文时间短语，未知则空字符串）。

严格输出 JSON：
{{
  "claims": [
    {{
      "subject": "主体",
      "object": "客体",
      "status": "TRUE",
      "description": "一句话事实",
      "start_date": "",
      "end_date": ""
    }}
  ]
}}
若没有明确事实，返回 {{"claims": []}}

文本：
{text}
"""


def _claim_id(subject: str, description: str) -> str:
    key = f"{subject.strip().casefold()}|{description.strip().casefold()}"
    return "cov_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]  # noqa: S324


def extract_claims_from_units(llm: Any, units: list[TextUnit]) -> list[Covariate]:
    if llm is None:
        return []
    bucket: dict[str, Covariate] = {}
    for unit in units:
        prompt = CLAIM_PROMPT.format(text=unit.text[:5000])
        try:
            payload = parse_json_payload(invoke_llm(llm, prompt))
        except Exception:  # noqa: BLE001
            continue
        claims = payload.get("claims") if isinstance(payload, dict) else []
        if not isinstance(claims, list):
            continue
        for c in claims:
            if not isinstance(c, dict):
                continue
            subject = str(c.get("subject") or "").strip()
            description = str(c.get("description") or "").strip()
            if not subject or not description:
                continue
            cid = _claim_id(subject, description)
            if cid in bucket:
                if unit.id not in bucket[cid].text_unit_ids:
                    bucket[cid].text_unit_ids.append(unit.id)
                continue
            status = str(c.get("status") or "TRUE").strip().upper()
            if status not in {"TRUE", "FALSE", "SUSPECTED"}:
                status = "TRUE"
            bucket[cid] = Covariate(
                id=cid,
                subject=subject,
                object=str(c.get("object") or "").strip(),
                type="claim",
                status=status,
                description=description,
                start_date=str(c.get("start_date") or "").strip(),
                end_date=str(c.get("end_date") or "").strip(),
                text_unit_ids=[unit.id],
            )
    return list(bucket.values())
