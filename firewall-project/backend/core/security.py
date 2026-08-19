"""
Security utilities
-------------------
احراز هویت با کلید API، محدودسازی نرخ درخواست و هدرهای امنیتی پایه.
"""

from __future__ import annotations

import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from functools import wraps
from pathlib import Path

from flask import request, jsonify


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def _load_or_create_api_key(path: str | None = None) -> str:
    if path is None:
        # مسیر مطلق نسبت به این فایل، نه نسبت به working directory،
        # تا فرقی نکند برنامه از کجا اجرا می‌شود
        path = Path(__file__).resolve().parent.parent / "logs" / ".api_key"
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    key = generate_api_key()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(key, encoding="utf-8")
    os.chmod(p, 0o600)
    return key


API_KEY = os.environ.get("FIREWALL_API_KEY") or _load_or_create_api_key()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        provided = request.headers.get("X-API-Key", "")
        if not provided or not constant_time_compare(provided, API_KEY):
            return jsonify({"error": "Unauthorized", "message": "کلید API نامعتبر یا گم‌شده است"}), 401
        return fn(*args, **kwargs)
    return wrapper


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        q = self._hits[key]
        while q and now - q[0] > self.window_seconds:
            q.popleft()
        if len(q) >= self.max_requests:
            return False
        q.append(now)
        return True


rate_limiter = RateLimiter(max_requests=120, window_seconds=60)


def rate_limited(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        if not rate_limiter.allow(ip):
            return jsonify({"error": "TooManyRequests", "message": "تعداد درخواست‌ها بیش از حد مجاز است"}), 429
        return fn(*args, **kwargs)
    return wrapper


def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


def sanitize_pattern(pattern: str, max_len: int = 200) -> str:
    pattern = pattern.strip()[:max_len]
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.*_-")
    cleaned = "".join(c for c in pattern if c in allowed)
    return cleaned
