import json
import re
from dataclasses import dataclass, field
from typing import Any


class TokenCounter:
    def __init__(self):
        try:
            import tiktoken
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoding = None
        self.cache: dict[str, int] = {}

    def count(self, text: str) -> int:
        if text not in self.cache:
            self.cache[text] = len(self.encoding.encode(text)) if self.encoding else max(1, len(text) // 3)
        return self.cache[text]


@dataclass
class ContextPacket:
    content: str
    kind: str
    priority: int = 2
    tags: list[str] = field(default_factory=list)
    token_count: int = 0
    relevance: float = 0


@dataclass
class ContextBuildResult:
    text: str
    used_tokens: int
    available_tokens: int
    stats: dict[str, Any]


class OperationsContextBuilder:
    def __init__(self, max_tokens: int = 4000, reserve_ratio: float = 0.2):
        self.max_tokens = max_tokens
        self.reserve_ratio = reserve_ratio
        self.counter = TokenCounter()

    def build(self, *, query: str, policies: list[str], task_state: dict[str, Any], evidence: list[ContextPacket], memories: list[ContextPacket], history: list[str]) -> ContextBuildResult:
        available = int(self.max_tokens * (1 - self.reserve_ratio))
        packets = [ContextPacket("\n".join(policies), "policies", 0), ContextPacket(json.dumps(task_state, ensure_ascii=False), "state", 0)]
        packets.extend(evidence)
        packets.extend(memories)
        packets.extend(ContextPacket(item, "history", 3) for item in history[-12:])
        query_terms = self._terms(query)
        query_terms.update(str(value).lower() for value in task_state.values() if isinstance(value, (str, int, float)))
        for packet in packets:
            packet.token_count = self.counter.count(packet.content)
            tag_text = " ".join(packet.tags).lower()
            content = f"{packet.content} {tag_text}".lower()
            matched = sum(1 for term in query_terms if term in content)
            packet.relevance = matched / max(1, len(query_terms))
        mandatory = [item for item in packets if item.priority == 0]
        candidates = [item for item in packets if item.priority > 0 and item.relevance > 0]
        candidates.sort(key=lambda item: (item.priority, -item.relevance, item.token_count))
        selected: list[ContextPacket] = []
        used = 0
        for packet in [*mandatory, *candidates]:
            if used + packet.token_count <= available:
                selected.append(packet)
                used += packet.token_count
        groups = {"policies": "Role & Policies", "state": "Task State", "evidence": "Evidence", "memory": "Relevant Memory", "history": "Conversation Context"}
        sections = [f"[Task]\n{query}"]
        for kind, title in groups.items():
            values = [item.content for item in selected if item.kind == kind]
            if values:
                sections.append(f"[{title}]\n" + "\n".join(values))
        text = "\n\n".join(sections)
        return ContextBuildResult(text=text, used_tokens=self.counter.count(text), available_tokens=available, stats={"gathered": len(packets), "selected": len(selected), "dropped": len(packets) - len(selected), "by_kind": {kind: sum(1 for item in selected if item.kind == kind) for kind in groups}})

    @staticmethod
    def _terms(text: str) -> set[str]:
        ascii_terms = re.findall(r"[A-Za-z0-9_]+", text.lower())
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        terms = set(ascii_terms + chinese)
        for marker in ("转化率", "库存", "价格", "竞品", "广告", "客户"):
            if marker in text:
                terms.add(marker)
        return terms
