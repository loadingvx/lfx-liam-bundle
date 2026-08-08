"""LLM 调用与 JSON 解析辅助。"""

from __future__ import annotations

import json
import re
from typing import Any


def invoke_llm(llm: Any, prompt: str) -> str:
    if llm is None:
        msg = "未连接语言模型（LLM）。完整 GraphRAG 建图/Global Search 需要 LLM。"
        raise ValueError(msg)
    if hasattr(llm, "invoke"):
        result = llm.invoke(prompt)
    elif callable(llm):
        result = llm(prompt)
    else:
        msg = "提供的 LLM 对象不可调用（需要支持 invoke）。"
        raise TypeError(msg)
    content = getattr(result, "content", result)
    if isinstance(content, list):
        content = "".join(str(getattr(c, "text", c)) for c in content)
    return str(content).strip()


def parse_json_payload(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        msg = "LLM 返回为空，无法解析 JSON。"
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
        msg = f"无法从 LLM 输出解析 JSON：{raw[:200]}"
        raise ValueError(msg) from None
