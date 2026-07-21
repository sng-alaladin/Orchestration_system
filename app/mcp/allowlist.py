"""MCP Allowlist — 연결이 허용된 MCP Server의 curated 목록 (spec 04 §17.1 C).

목록에 없는 외부 MCP는 사용자 승인만으로 연결할 수 없다 (전문가 확인 또는 자동 차단).
"""

from pathlib import Path

import yaml

DEFAULT_ALLOWLIST_PATH = Path("configs") / "mcp-allowlist.yaml"


class McpAllowlist:
    def __init__(self, server_ids: set[str]) -> None:
        self._ids = server_ids

    @classmethod
    def load(cls, path: Path = DEFAULT_ALLOWLIST_PATH) -> "McpAllowlist":
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        ids = {str(x) for x in (raw.get("allowed_servers") or [])}
        return cls(ids)

    def contains(self, server_id: str) -> bool:
        return server_id in self._ids

    def all_ids(self) -> set[str]:
        return set(self._ids)
