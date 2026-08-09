"""LLM 调用与 JSON 解析辅助。"""

from __future__ import annotations

import json
import re
from typing import Any


def invoke_llm(llm: Any, prompt: str) -> str:
    if llm is None:
        msg = "No language model (LLM) connected. Full GraphRAG indexing / Global Search needs an LLM."
        raise ValueError(msg)
    if hasattr(llm, "invoke"):
        result = llm.invoke(prompt)
    elif callable(llm):
        result = llm(prompt)
    else:
        msg = "Provided LLM object is not callable (must support invoke)."
        raise TypeError(msg)
    content = getattr(result, "content", result)
    if isinstance(content, list):
        content = "".join(str(getattr(c, "text", c)) for c in content)
    text = str(content).strip()
    # MiniMax 等模型可能返回 <think>…</think>，下游 JSON/答案解析前去掉
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
    text = re.sub(r"<thinking>[\s\S]*?</thinking>", "", text, flags=re.I).strip()
    return text


def parse_json_payload(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        msg = "LLM returned empty output; cannot parse JSON."
        raise ValueError(msg)
    # fenced code
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # try object/array slice
        for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
            m = re.search(pattern, raw)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue
        msg = f"Could not parse JSON from LLM output: {raw[:200]}"
        raise ValueError(msg) from None
