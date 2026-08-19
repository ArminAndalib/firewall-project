import sys
from pathlib import Path
import shutil

sys.path.insert(0, str(Path(__file__).parent))

logs_dir = Path(__file__).parent / "logs"
if logs_dir.exists():
    shutil.rmtree(logs_dir)

import app as appmodule
from core.security import rate_limiter as limiter

client = appmodule.app.test_client()
api_key = appmodule.API_KEY


def check(label, cond):
    print(f"{'✅' if cond else '❌'} {label}")
    assert cond, label


r = client.get("/api/status")
check("status 200", r.status_code == 200)

r = client.get("/api/stats")
check("stats بدون کلید -> 401", r.status_code == 401)

r = client.get("/api/stats", headers={"X-API-Key": api_key})
check("stats با کلید -> 200", r.status_code == 200)
check("قوانین پیش‌فرض بارگذاری شدند", r.get_json()["total_rules"] >= 7)

r = client.post("/api/evaluate/network", json={"domain": "stats.doubleclick.net"},
                 headers={"X-API-Key": api_key})
check("doubleclick.net بلاک می‌شود", r.get_json()["action"] == "block")

r = client.post("/api/evaluate/network", json={"domain": "anthropic.com"},
                 headers={"X-API-Key": api_key})
check("anthropic.com اجازه داده می‌شود", r.get_json()["action"] == "allow")

r = client.post("/api/evaluate/cookie", json={"name": "_ga_ABC123"},
                 headers={"X-API-Key": api_key})
check("کوکی _ga بلاک می‌شود", r.get_json()["action"] == "block")

r = client.post("/api/rules", json={
    "pattern": "*tracker-x.com*", "rule_type": "network", "action": "block", "note": "تست"
}, headers={"X-API-Key": api_key})
check("افزودن قانون جدید -> 201", r.status_code == 201)
new_rule_id = r.get_json()["id"]

r = client.post("/api/evaluate/network", json={"domain": "ads.tracker-x.com"},
                 headers={"X-API-Key": api_key})
check("قانون جدید فوراً اعمال می‌شود", r.get_json()["action"] == "block")

r = client.post(f"/api/rules/{new_rule_id}/toggle", json={"enabled": False},
                 headers={"X-API-Key": api_key})
check("غیرفعال‌سازی قانون -> 200", r.status_code == 200)

r = client.post("/api/evaluate/network", json={"domain": "ads.tracker-x.com"},
                 headers={"X-API-Key": api_key})
check("بعد از غیرفعال‌سازی، دیگر بلاک نمی‌شود", r.get_json()["action"] == "allow")

r = client.delete(f"/api/rules/{new_rule_id}", headers={"X-API-Key": api_key})
check("حذف قانون -> 200", r.status_code == 200)

r = client.post("/api/rules", json={
    "pattern": "<script>alert(1)</script>*evil.com*",
    "rule_type": "network", "action": "block"
}, headers={"X-API-Key": api_key})
saved_pattern = r.get_json()["pattern"]
check("کاراکترهای خطرناک حذف می‌شوند", "<" not in saved_pattern and ">" not in saved_pattern)

r = client.get("/api/logs", headers={"X-API-Key": api_key})
check("لاگ‌ها ثبت می‌شوند", len(r.get_json()) > 0)

limiter.max_requests = 3
limiter.window_seconds = 60
ok_count = sum(1 for _ in range(5) if limiter.allow("test-ip"))
check("rate limiter بعد از سقف، رد می‌کند", ok_count == 3)

print("\nهمه‌ی تست‌ها با موفقیت پاس شدند 🎉")
