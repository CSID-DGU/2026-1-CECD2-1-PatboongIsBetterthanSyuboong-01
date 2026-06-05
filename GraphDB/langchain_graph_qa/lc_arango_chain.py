"""langchain-community 버전별 시그니처 차이(allow_dangerous_requests 등) 흡수."""

from __future__ import annotations

import inspect
from typing import Any


def build_arango_graph_qa_chain(chain_cls: type, llm: Any, **kwargs: Any) -> Any:
    sig = inspect.signature(chain_cls.from_llm)
    has_varkw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    if has_varkw:
        merged = {**kwargs, "allow_dangerous_requests": True}
        try:
            return chain_cls.from_llm(llm, **merged)
        except TypeError:
            return chain_cls.from_llm(llm, **kwargs)

    names = {p.name for p in sig.parameters.values() if p.name != "cls"}
    filtered = {k: v for k, v in kwargs.items() if k in names}
    if "allow_dangerous_requests" in names:
        filtered["allow_dangerous_requests"] = True
    try:
        return chain_cls.from_llm(llm, **filtered)
    except TypeError:
        return chain_cls.from_llm(llm, **{k: v for k, v in kwargs.items() if k in names})
