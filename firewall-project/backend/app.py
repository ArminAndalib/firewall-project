"""
Firewall Backend Server
------------------------
سرور اصلی Flask برای فایروال کوکی و شبکه.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, request, send_from_directory

from core.rules_engine import RulesEngine, RuleType, Action
from core.security import (
    require_api_key,
    rate_limited,
    apply_security_headers,
    sanitize_pattern,
    API_KEY,
)

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR.parent / "dashboard"

app = Flask(__name__, static_folder=None)

_ALLOWED_ORIGIN_PREFIXES = (
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "chrome-extension://",
    "moz-extension://",
)


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin and any(origin.startswith(p) for p in _ALLOWED_ORIGIN_PREFIXES):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return response


@app.after_request
def add_security_headers(response):
    return apply_security_headers(response)


@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return ("", 204)


engine = RulesEngine(
    storage_path=BASE_DIR / "logs" / "rules.json",
    log_path=BASE_DIR / "logs" / "events.json",
)


# ---------------------------------------------------------------------------
# داشبورد (فایل‌های استاتیک)
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard_index():
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.route("/static/<path:filename>")
def dashboard_static(filename):
    return send_from_directory(DASHBOARD_DIR / "static", filename)


# ---------------------------------------------------------------------------
# API: وضعیت کلی و آمار
# ---------------------------------------------------------------------------

@app.route("/api/status", methods=["GET"])
@rate_limited
def status():
    return jsonify({"status": "running", "service": "cookie-network-firewall"})


@app.route("/api/stats", methods=["GET"])
@rate_limited
@require_api_key
def stats():
    return jsonify(engine.stats())


# ---------------------------------------------------------------------------
# API: مدیریت قوانین (CRUD)
# ---------------------------------------------------------------------------

@app.route("/api/rules", methods=["GET"])
@rate_limited
@require_api_key
def list_rules():
    rule_type = request.args.get("type")
    rt = RuleType(rule_type) if rule_type in ("cookie", "network") else None
    return jsonify(engine.list_rules(rt))


@app.route("/api/rules", methods=["POST"])
@rate_limited
@require_api_key
def add_rule():
    data = request.get_json(silent=True) or {}
    pattern = sanitize_pattern(data.get("pattern", ""))
    rule_type = data.get("rule_type")
    action = data.get("action")
    note = (data.get("note") or "")[:200]

    if not pattern:
        return jsonify({"error": "BadRequest", "message": "الگو (pattern) معتبر نیست"}), 400
    if rule_type not in ("cookie", "network"):
        return jsonify({"error": "BadRequest", "message": "rule_type باید cookie یا network باشد"}), 400
    if action not in ("allow", "block"):
        return jsonify({"error": "BadRequest", "message": "action باید allow یا block باشد"}), 400

    rule = engine.add_rule(pattern, RuleType(rule_type), Action(action), note=note)
    return jsonify(rule.to_dict()), 201


@app.route("/api/rules/<rule_id>", methods=["DELETE"])
@rate_limited
@require_api_key
def delete_rule(rule_id):
    ok = engine.remove_rule(rule_id)
    if not ok:
        return jsonify({"error": "NotFound", "message": "قانون یافت نشد"}), 404
    return jsonify({"message": "قانون حذف شد"})


@app.route("/api/rules/<rule_id>/toggle", methods=["POST"])
@rate_limited
@require_api_key
def toggle_rule(rule_id):
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", True))
    ok = engine.toggle_rule(rule_id, enabled)
    if not ok:
        return jsonify({"error": "NotFound", "message": "قانون یافت نشد"}), 404
    return jsonify({"message": "به‌روزرسانی شد", "enabled": enabled})


# ---------------------------------------------------------------------------
# API: ارزیابی (مصرف توسط اکستنشن مرورگر)
# ---------------------------------------------------------------------------

@app.route("/api/evaluate/cookie", methods=["POST"])
@rate_limited
@require_api_key
def evaluate_cookie():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "")[:200]
    if not name:
        return jsonify({"error": "BadRequest", "message": "نام کوکی لازم است"}), 400
    action, rule_id = engine.evaluate(name, RuleType.COOKIE)
    return jsonify({"action": action.value, "matched_rule_id": rule_id})


@app.route("/api/evaluate/network", methods=["POST"])
@rate_limited
@require_api_key
def evaluate_network():
    data = request.get_json(silent=True) or {}
    domain = (data.get("domain") or "")[:300]
    if not domain:
        return jsonify({"error": "BadRequest", "message": "دامنه لازم است"}), 400
    action, rule_id = engine.evaluate(domain, RuleType.NETWORK)
    return jsonify({"action": action.value, "matched_rule_id": rule_id})


# ---------------------------------------------------------------------------
# API: لاگ‌های رویداد
# ---------------------------------------------------------------------------

@app.route("/api/logs", methods=["GET"])
@rate_limited
@require_api_key
def get_logs():
    limit = min(int(request.args.get("limit", 200)), 2000)
    return jsonify(engine.get_logs(limit))


# ---------------------------------------------------------------------------
# مدیریت خطا
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "NotFound", "message": "مسیر یافت نشد"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "ServerError", "message": "خطای داخلی سرور"}), 500


if __name__ == "__main__":
    print("=" * 60)
    print("🔒 Cookie & Network Firewall — Backend")
    print("=" * 60)
    print(f"API Key شما (آن را در اکستنشن و داشبورد وارد کنید):\n\n  {API_KEY}\n")
    print("این کلید در backend/logs/.api_key هم ذخیره شده است.")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
