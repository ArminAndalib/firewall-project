"""
Rules Engine
-------------
موتور اصلی فایروال: قوانین allow/block را برای کوکی‌ها و درخواست‌های
شبکه نگه می‌دارد، اعمال می‌کند و رویدادها را ثبت می‌کند.
"""

from __future__ import annotations

import fnmatch
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Optional


class Action(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class RuleType(str, Enum):
    COOKIE = "cookie"
    NETWORK = "network"


@dataclass
class Rule:
    pattern: str
    rule_type: RuleType
    action: Action
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: float = field(default_factory=time.time)
    enabled: bool = True
    note: str = ""

    def matches(self, value: str) -> bool:
        if not self.enabled:
            return False
        return fnmatch.fnmatch(value.lower(), self.pattern.lower())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rule_type"] = self.rule_type.value
        d["action"] = self.action.value
        return d


@dataclass
class LogEntry:
    timestamp: float
    rule_type: str
    target: str
    action: str
    matched_rule_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_RULES: list[dict] = [
    {"pattern": "*doubleclick.net*", "rule_type": "network", "action": "block", "note": "تبلیغات گوگل"},
    {"pattern": "*googlesyndication.com*", "rule_type": "network", "action": "block", "note": "تبلیغات گوگل"},
    {"pattern": "*facebook.com/tr*", "rule_type": "network", "action": "block", "note": "ردیاب فیسبوک"},
    {"pattern": "*google-analytics.com*", "rule_type": "network", "action": "block", "note": "آنالیتیکس گوگل"},
    {"pattern": "*scorecardresearch.com*", "rule_type": "network", "action": "block", "note": "ردیاب آماری"},
    {"pattern": "_ga*", "rule_type": "cookie", "action": "block", "note": "کوکی گوگل آنالیتیکس"},
    {"pattern": "_fbp", "rule_type": "cookie", "action": "block", "note": "کوکی پیکسل فیسبوک"},
    {"pattern": "__gads", "rule_type": "cookie", "action": "block", "note": "کوکی تبلیغات گوگل"},
    {"pattern": "IDE", "rule_type": "cookie", "action": "block", "note": "کوکی تبلیغات DoubleClick"},
]


class RulesEngine:
    def __init__(self, storage_path: str | Path = "backend/logs/rules.json",
                 log_path: str | Path = "backend/logs/events.json",
                 max_log_entries: int = 2000):
        self._lock = RLock()
        self.storage_path = Path(storage_path)
        self.log_path = Path(log_path)
        self.max_log_entries = max_log_entries
        self.rules: dict[str, Rule] = {}
        self.logs: list[LogEntry] = []

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

        if not self.rules:
            for r in DEFAULT_RULES:
                self.add_rule(r["pattern"], RuleType(r["rule_type"]), Action(r["action"]), note=r.get("note", ""))

    def add_rule(self, pattern: str, rule_type: RuleType, action: Action, note: str = "") -> Rule:
        with self._lock:
            rule = Rule(pattern=pattern, rule_type=rule_type, action=action, note=note)
            self.rules[rule.id] = rule
            self._save()
            return rule

    def remove_rule(self, rule_id: str) -> bool:
        with self._lock:
            existed = self.rules.pop(rule_id, None) is not None
            if existed:
                self._save()
            return existed

    def toggle_rule(self, rule_id: str, enabled: bool) -> bool:
        with self._lock:
            rule = self.rules.get(rule_id)
            if not rule:
                return False
            rule.enabled = enabled
            self._save()
            return True

    def list_rules(self, rule_type: Optional[RuleType] = None) -> list[dict]:
        with self._lock:
            rules = self.rules.values()
            if rule_type:
                rules = [r for r in rules if r.rule_type == rule_type]
            return [r.to_dict() for r in sorted(rules, key=lambda r: r.created_at, reverse=True)]

    def evaluate(self, value: str, rule_type: RuleType) -> tuple[Action, Optional[str]]:
        with self._lock:
            candidates = [r for r in self.rules.values() if r.rule_type == rule_type and r.matches(value)]
            block_rule = next((r for r in candidates if r.action == Action.BLOCK), None)
            if block_rule:
                self._log(value, rule_type, Action.BLOCK, block_rule.id)
                return Action.BLOCK, block_rule.id

            allow_rule = next((r for r in candidates if r.action == Action.ALLOW), None)
            if allow_rule:
                self._log(value, rule_type, Action.ALLOW, allow_rule.id)
                return Action.ALLOW, allow_rule.id

            self._log(value, rule_type, Action.ALLOW, None)
            return Action.ALLOW, None

    def _log(self, target: str, rule_type: RuleType, action: Action, rule_id: Optional[str]) -> None:
        entry = LogEntry(
            timestamp=time.time(),
            rule_type=rule_type.value,
            target=target,
            action=action.value,
            matched_rule_id=rule_id,
        )
        self.logs.append(entry)
        if len(self.logs) > self.max_log_entries:
            self.logs = self.logs[-self.max_log_entries:]
        self._save_logs()

    def get_logs(self, limit: int = 200) -> list[dict]:
        with self._lock:
            return [e.to_dict() for e in self.logs[-limit:][::-1]]

    def stats(self) -> dict:
        with self._lock:
            blocked = sum(1 for e in self.logs if e.action == Action.BLOCK.value)
            allowed = sum(1 for e in self.logs if e.action == Action.ALLOW.value)
            return {
                "total_events": len(self.logs),
                "blocked": blocked,
                "allowed": allowed,
                "active_rules": sum(1 for r in self.rules.values() if r.enabled),
                "total_rules": len(self.rules),
            }

    def _save(self) -> None:
        data = [r.to_dict() for r in self.rules.values()]
        self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_logs(self) -> None:
        data = [e.to_dict() for e in self.logs]
        self.log_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for item in data:
                    rule = Rule(
                        pattern=item["pattern"],
                        rule_type=RuleType(item["rule_type"]),
                        action=Action(item["action"]),
                        id=item["id"],
                        created_at=item["created_at"],
                        enabled=item.get("enabled", True),
                        note=item.get("note", ""),
                    )
                    self.rules[rule.id] = rule
            except (json.JSONDecodeError, KeyError):
                pass

        if self.log_path.exists():
            try:
                data = json.loads(self.log_path.read_text(encoding="utf-8"))
                self.logs = [LogEntry(**item) for item in data]
            except (json.JSONDecodeError, TypeError):
                pass
