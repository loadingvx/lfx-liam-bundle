"""Token 计数与上下文预算（对齐微软 GraphRAG max_context_tokens / prop 语义）。"""

from __future__ import annotations

from typing import Any

_ENC = None


def _encoding():
    global _ENC
    if _ENC is not None:
        return _ENC
    try:
        import tiktoken

        _ENC = tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001
        _ENC = False
    return _ENC


def count_tokens(text: str) -> int:
    """统计文本 token 数；无 tiktoken 时回退到中英混合启发。"""
    raw = text or ""
    if not raw:
        return 0
    enc = _encoding()
    if enc is not False and enc is not None:
        try:
            return max(1, len(enc.encode(raw)))
        except Exception:  # noqa: BLE001
            pass
    cjk = sum(1 for ch in raw if "\u4e00" <= ch <= "\u9fff")
    if cjk >= max(1, len(raw) // 4):
        return max(1, len(raw))
    return max(1, len(raw.split()))


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0 or not text:
        return ""
    if count_tokens(text) <= max_tokens:
        return text
    enc = _encoding()
    if enc is not False and enc is not None:
        try:
            ids = enc.encode(text)[:max_tokens]
            return enc.decode(ids)
        except Exception:  # noqa: BLE001
            pass
    # 字符级近似
    ratio = max_tokens / max(1, count_tokens(text))
    cut = max(1, int(len(text) * ratio))
    return text[:cut]


def pack_sections(
    sections: list[tuple[str, str]],
    *,
    max_tokens: int,
) -> str:
    """按序装配 (标题, 正文)，总 token 不超过预算。"""
    if max_tokens <= 0:
        return ""
    parts: list[str] = []
    used = 0
    for title, body in sections:
        block = f"## {title}\n{body}".strip() if title else (body or "").strip()
        if not block:
            continue
        need = count_tokens(block) + 2
        if used + need > max_tokens:
            remain = max_tokens - used - count_tokens(f"## {title}\n") - 2
            if remain < 32:
                break
            body_cut = truncate_to_tokens(body, remain)
            parts.append(f"## {title}\n{body_cut}" if title else body_cut)
            break
        parts.append(block)
        used += need
    return "\n\n".join(parts)


def allocate_budget(
    max_context_tokens: int,
    *,
    text_unit_prop: float = 0.5,
    community_prop: float = 0.25,
) -> dict[str, int]:
    """分配 Local Search 各段 token 预算（剩余给实体/关系/claims）。"""
    total = max(256, int(max_context_tokens))
    tu = max(0.0, min(float(text_unit_prop), 0.9))
    cr = max(0.0, min(float(community_prop), 0.9))
    if tu + cr > 0.95:
        scale = 0.95 / (tu + cr)
        tu *= scale
        cr *= scale
    text_budget = int(total * tu)
    community_budget = int(total * cr)
    graph_budget = max(64, total - text_budget - community_budget)
    return {
        "total": total,
        "text_units": text_budget,
        "community_reports": community_budget,
        "graph": graph_budget,
    }


def join_under_budget(items: list[str], *, max_tokens: int, sep: str = "\n") -> str:
    out: list[str] = []
    used = 0
    for item in items:
        t = (item or "").strip()
        if not t:
            continue
        need = count_tokens(t) + (count_tokens(sep) if out else 0)
        if used + need > max_tokens:
            remain = max_tokens - used - (count_tokens(sep) if out else 0)
            if remain >= 24:
                out.append(truncate_to_tokens(t, remain))
            break
        out.append(t)
        used += need
    return sep.join(out)
