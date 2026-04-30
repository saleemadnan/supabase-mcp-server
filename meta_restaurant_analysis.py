"""
تحليل حساب طعم ابوغزالة الإعلاني وإنشاء هيكل الحملات المقترح.

الاستخدام:
    python meta_restaurant_analysis.py                   # تحليل فقط
    python meta_restaurant_analysis.py --create          # تحليل + إنشاء الحملات المقترحة
    python meta_restaurant_analysis.py --refresh-token   # تجديد الرمز (60 يوم) وحفظه في .env
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── load .env if present ───────────────────────────────────────────────────────
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

import httpx  # noqa: E402 — after env load

# ── config ────────────────────────────────────────────────────────────────────
APP_ID       = os.environ.get("META_APP_ID", "3068615529961297")
APP_SECRET   = os.environ.get("META_APP_SECRET", "")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
ACCOUNT_ID   = os.environ.get("META_AD_ACCOUNT_ID", "act_1198372168168124")
API_VERSION  = os.environ.get("META_API_VERSION", "v21.0")
BASE_URL     = f"https://graph.facebook.com/{API_VERSION}"

RESTAURANT_NAME = "طعم ابوغزالة"

# ── colours ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

SEP  = "─" * 65
SEP2 = "═" * 65


# ── helpers ───────────────────────────────────────────────────────────────────

def fmt_currency(val: str | float | None, currency: str = "SAR") -> str:
    if val is None:
        return "—"
    try:
        amount = float(val) / 100  # Meta sends cents
        return f"{amount:,.2f} {currency}"
    except (ValueError, TypeError):
        return str(val)


def fmt_pct(val: str | float | None) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.2f}%"
    except (ValueError, TypeError):
        return str(val)


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{SEP2}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{SEP2}{RESET}")


def subsection(title: str) -> None:
    print(f"\n{BOLD}{YELLOW}  ▶ {title}{RESET}")
    print(f"  {SEP}")


# ── API client ────────────────────────────────────────────────────────────────

def _parse_response(r: httpx.Response) -> dict:
    ct = r.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            return r.json()
        except Exception:
            pass
    return {}


def _handle_api_error(method: str, path: str, r: httpx.Response, data: dict) -> None:
    err  = data.get("error", {})
    msg  = err.get("message") or r.text[:300]
    code = err.get("code", r.status_code)
    sub  = err.get("error_subcode", "")
    label = f"[{code}/{sub}]" if sub else f"[{code}]"
    print(f"  {RED}{method} {path} → API Error {label}: {msg}{RESET}")
    # Token-related errors
    if code in (190, 102, 104) or any(k in msg.lower() for k in ("expired", "invalid", "session")):
        print(f"  {YELLOW}  ↳ رمز الوصول منتهي أو غير صالح.")
        print(f"    شغّل:  python meta_restaurant_analysis.py --refresh-token{RESET}")
    # Permissions error
    elif code in (10, 200, 294) or "permission" in msg.lower():
        print(f"  {YELLOW}  ↳ صلاحية مفقودة — تأكد من وجود: ads_management, ads_read, business_management{RESET}")
    # Rate limit
    elif code in (4, 17, 32, 613):
        print(f"  {YELLOW}  ↳ تجاوزت حد الطلبات — انتظر دقيقة ثم أعد المحاولة{RESET}")


async def api_get(client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
    merged = {"access_token": ACCESS_TOKEN, **(params or {})}
    try:
        r = await client.get(f"{BASE_URL}/{path.lstrip('/')}", params=merged)
    except httpx.RequestError as exc:
        print(f"  {RED}Network error on GET {path}: {exc}{RESET}")
        return {}
    data = _parse_response(r)
    if not r.is_success or "error" in data:
        _handle_api_error("GET", path, r, data)
        return {}
    return data


async def api_post(client: httpx.AsyncClient, path: str, body: dict) -> dict:
    payload = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in body.items()}
    payload["access_token"] = ACCESS_TOKEN
    try:
        r = await client.post(
            f"{BASE_URL}/{path.lstrip('/')}",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except httpx.RequestError as exc:
        print(f"  {RED}Network error on POST {path}: {exc}{RESET}")
        return {}
    data = _parse_response(r)
    if not r.is_success or "error" in data:
        _handle_api_error("POST", path, r, data)
        return {}
    return data


async def validate_token(client: httpx.AsyncClient) -> bool:
    """Quick token check — returns True if valid."""
    print(f"  {YELLOW}التحقق من صلاحية الرمز...{RESET}", end=" ", flush=True)
    result = await api_get(client, "/me", {"fields": "id,name"})
    if result:
        print(f"{GREEN}✓ صالح ({result.get('name', result.get('id'))}){RESET}")
        return True
    return False


async def refresh_token_cmd() -> None:
    """Exchange the current short-lived token for a 60-day long-lived token."""
    if not APP_SECRET:
        print(f"{RED}خطأ: META_APP_SECRET غير محدد في .env{RESET}")
        sys.exit(1)

    print(f"\n{YELLOW}جارٍ تجديد رمز الوصول...{RESET}")
    url = f"{BASE_URL}/oauth/access_token"
    params = {
        "grant_type":       "fb_exchange_token",
        "client_id":        APP_ID,
        "client_secret":    APP_SECRET,
        "fb_exchange_token": ACCESS_TOKEN,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            r = await client.get(url, params=params)
        except httpx.RequestError as exc:
            print(f"{RED}Network error: {exc}{RESET}")
            sys.exit(1)

        data = _parse_response(r)
        if not r.is_success or "error" in data:
            _handle_api_error("GET", "/oauth/access_token", r, data)
            sys.exit(1)

        new_token    = data.get("access_token", "")
        expires_in   = data.get("expires_in", 0)
        expires_days = int(expires_in) // 86400 if expires_in else "?"

        if not new_token:
            print(f"{RED}لم يُعَد رمز جديد — تحقق من APP_ID و APP_SECRET{RESET}")
            sys.exit(1)

        # Update .env in place
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            text = env_path.read_text()
            import re
            text = re.sub(r"^META_ACCESS_TOKEN=.*$", f"META_ACCESS_TOKEN={new_token}", text, flags=re.MULTILINE)
            env_path.write_text(text)
            print(f"{GREEN}✓ تم حفظ الرمز الجديد في .env (صالح لـ {expires_days} يوم){RESET}")
        else:
            print(f"{GREEN}✓ الرمز الجديد:{RESET}")
            print(f"  META_ACCESS_TOKEN={new_token}")
            print(f"  (صالح لـ {expires_days} يوم — أضفه يدوياً لـ .env)")

        print(f"\n{YELLOW}شغّل السكريبت مجدداً لرؤية التحليل الكامل.{RESET}\n")


# ── data collection ───────────────────────────────────────────────────────────

async def collect_all(client: httpx.AsyncClient) -> dict:
    """Pull all data needed for analysis."""
    print(f"\n{YELLOW}جارٍ جمع البيانات من Meta API...{RESET}")

    account = await api_get(client, f"/{ACCOUNT_ID}", {
        "fields": "id,name,account_status,currency,timezone_name,amount_spent,balance,spend_cap"
    })

    campaigns = await api_get(client, f"/{ACCOUNT_ID}/campaigns", {
        "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time,created_time",
        "limit": 50,
    })

    adsets = await api_get(client, f"/{ACCOUNT_ID}/adsets", {
        "fields": "id,name,status,campaign_id,daily_budget,lifetime_budget,billing_event,optimization_goal,targeting,start_time,end_time",
        "limit": 100,
    })

    ads = await api_get(client, f"/{ACCOUNT_ID}/ads", {
        "fields": "id,name,status,adset_id,campaign_id,created_time",
        "limit": 100,
    })

    # Overall insights – last 30 days
    insights_30d = await api_get(client, f"/{ACCOUNT_ID}/insights", {
        "date_preset": "last_30d",
        "fields": "impressions,clicks,spend,reach,cpc,cpm,ctr,frequency",
        "level": "account",
    })

    # By age + gender
    insights_age = await api_get(client, f"/{ACCOUNT_ID}/insights", {
        "date_preset": "last_30d",
        "fields": "impressions,clicks,spend,reach,ctr",
        "breakdowns": "age,gender",
        "level": "account",
    })

    # By placement
    insights_placement = await api_get(client, f"/{ACCOUNT_ID}/insights", {
        "date_preset": "last_30d",
        "fields": "impressions,clicks,spend,reach,ctr,cpm",
        "breakdowns": "publisher_platform,platform_position",
        "level": "account",
    })

    # By country
    insights_geo = await api_get(client, f"/{ACCOUNT_ID}/insights", {
        "date_preset": "last_30d",
        "fields": "impressions,clicks,spend,reach,ctr",
        "breakdowns": "country",
        "level": "account",
    })

    # Weekly trend (last 28 days, 7-day buckets)
    insights_weekly = await api_get(client, f"/{ACCOUNT_ID}/insights", {
        "date_preset": "last_28d",
        "fields": "impressions,clicks,spend,reach,ctr,cpm",
        "time_increment": "7",
        "level": "account",
    })

    # Per-campaign insights
    campaign_insights: list[dict] = []
    for camp in (campaigns.get("data") or []):
        ci = await api_get(client, f"/{camp['id']}/insights", {
            "date_preset": "last_30d",
            "fields": "impressions,clicks,spend,reach,ctr,cpm,cpc",
        })
        if ci.get("data"):
            camp_copy = dict(camp)
            camp_copy["insights_30d"] = ci["data"][0]
            campaign_insights.append(camp_copy)

    return {
        "account": account,
        "campaigns": campaigns.get("data", []),
        "adsets": adsets.get("data", []),
        "ads": ads.get("data", []),
        "insights_30d": (insights_30d.get("data") or [{}])[0],
        "insights_age": insights_age.get("data", []),
        "insights_placement": insights_placement.get("data", []),
        "insights_geo": insights_geo.get("data", []),
        "insights_weekly": insights_weekly.get("data", []),
        "campaign_insights": campaign_insights,
    }


# ── analysis + report ─────────────────────────────────────────────────────────

def print_report(data: dict) -> dict:
    """Print the full Arabic analysis report. Returns scoring dict."""
    acct = data["account"]
    ins  = data["insights_30d"]
    currency = acct.get("currency", "SAR")

    print(f"\n{BOLD}{GREEN}{SEP2}")
    print(f"  تقرير تحليل الإعلانات — {RESTAURANT_NAME}")
    print(f"  التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{SEP2}{RESET}")

    # ── Account Overview ──────────────────────────────────────────────────────
    section("1 / نظرة عامة على الحساب")
    status_map = {1: f"{GREEN}نشط ✓{RESET}", 2: f"{RED}معطّل{RESET}", 3: f"{YELLOW}غير مؤكد{RESET}"}
    acct_status = status_map.get(int(acct.get("account_status", 1)), "—")
    print(f"  الحساب          : {acct.get('name', '—')} ({acct.get('id', '—')})")
    print(f"  الحالة          : {acct_status}")
    print(f"  العملة          : {currency}")
    print(f"  التوقيت         : {acct.get('timezone_name', '—')}")
    print(f"  الرصيد المتبقي  : {fmt_currency(acct.get('balance'), currency)}")
    print(f"  إجمالي الإنفاق  : {fmt_currency(acct.get('amount_spent'), currency)}")

    # ── 30-Day KPIs ───────────────────────────────────────────────────────────
    section("2 / مؤشرات الأداء — آخر 30 يوم")
    spend   = float(ins.get("spend", 0))
    reach   = int(ins.get("reach", 0))
    impr    = int(ins.get("impressions", 0))
    clicks  = int(ins.get("clicks", 0))
    cpm     = float(ins.get("cpm", 0))
    cpc_val = float(ins.get("cpc", 0))
    ctr     = float(ins.get("ctr", 0))
    freq    = float(ins.get("frequency", 0))

    print(f"  الإنفاق الإجمالي : {spend:,.2f} {currency}")
    print(f"  الوصول (Reach)   : {reach:,} شخص")
    print(f"  المشاهدات        : {impr:,}")
    print(f"  النقرات          : {clicks:,}")
    print(f"  CPM              : {cpm:.2f} {currency}  {'✓ جيد' if cpm < 25 else '⚠ مرتفع'}")
    print(f"  CPC              : {cpc_val:.2f} {currency}")
    print(f"  CTR              : {ctr:.2f}%  {'✓ جيد' if ctr > 1 else '⚠ منخفض'}")
    print(f"  التكرار (Freq)   : {freq:.1f}x  {'✓ مثالي' if 2 <= freq <= 4 else '⚠ راجع التكرار'}")

    # ── Campaigns ─────────────────────────────────────────────────────────────
    section("3 / الحملات الإعلانية")
    campaigns = data["campaigns"]
    active = [c for c in campaigns if c.get("status") == "ACTIVE"]
    paused = [c for c in campaigns if c.get("status") == "PAUSED"]
    print(f"  إجمالي الحملات  : {len(campaigns)}")
    print(f"  نشطة            : {len(active)}")
    print(f"  موقوفة          : {len(paused)}")

    if data["campaign_insights"]:
        subsection("أداء كل حملة — آخر 30 يوم")
        for c in sorted(data["campaign_insights"], key=lambda x: float(x.get("insights_30d", {}).get("spend", 0)), reverse=True):
            ci = c.get("insights_30d", {})
            obj = c.get("objective", "—")
            status_icon = f"{GREEN}●{RESET}" if c.get("status") == "ACTIVE" else f"{YELLOW}●{RESET}"
            print(f"  {status_icon} {c['name'][:45]}")
            print(f"      الهدف: {obj} | إنفاق: {float(ci.get('spend',0)):,.2f} | CPM: {float(ci.get('cpm',0)):.2f} | CTR: {float(ci.get('ctr',0)):.2f}%")

    # ── Objectives analysis ───────────────────────────────────────────────────
    subsection("تحليل الأهداف المستخدمة")
    odax = {"AWARENESS", "TRAFFIC", "ENGAGEMENT", "LEADS", "APP_PROMOTION", "SALES"}
    objectives = [c.get("objective", "") for c in campaigns]
    used_odax   = [o for o in objectives if o in odax]
    used_legacy = [o for o in objectives if o not in odax and o]
    if used_odax:
        print(f"  ODAX (موصى به)  : {', '.join(set(used_odax))}")
    if used_legacy:
        print(f"  {YELLOW}Legacy (قديم)   : {', '.join(set(used_legacy))} — يُنصح بالترقية{RESET}")
    if not objectives:
        print(f"  {YELLOW}لا توجد حملات حتى الآن{RESET}")

    # ── Ad Sets ───────────────────────────────────────────────────────────────
    section("4 / المجموعات الإعلانية")
    adsets = data["adsets"]
    print(f"  إجمالي المجموعات : {len(adsets)}")
    if adsets:
        subsection("تفاصيل المجموعات")
        for ads in adsets[:10]:
            tgt = ads.get("targeting", {})
            ages = f"{tgt.get('age_min','?')}–{tgt.get('age_max','?')}"
            countries = ", ".join((tgt.get("geo_locations") or {}).get("countries", ["—"]))
            print(f"  • {ads.get('name','—')[:45]}")
            print(f"    الفئة العمرية: {ages} | الدول: {countries} | الهدف: {ads.get('optimization_goal','—')}")

    # ── Audience breakdown ────────────────────────────────────────────────────
    section("5 / تحليل الجمهور")
    age_data = data["insights_age"]
    if age_data:
        subsection("توزيع العمر والجنس (حسب الإنفاق)")
        by_age: dict[str, dict] = {}
        for row in age_data:
            age = row.get("age", "—")
            gender = row.get("gender", "—")
            sp = float(row.get("spend", 0))
            ctr_row = float(row.get("ctr", 0))
            by_age.setdefault(age, {"male": 0.0, "female": 0.0, "total_ctr": 0.0, "count": 0})
            by_age[age]["total_ctr"] += ctr_row
            by_age[age]["count"] += 1
            if gender == "male":
                by_age[age]["male"] += sp
            else:
                by_age[age]["female"] += sp

        for age_g, vals in sorted(by_age.items()):
            total = vals["male"] + vals["female"]
            avg_ctr = vals["total_ctr"] / max(vals["count"], 1)
            print(f"  {age_g:8}  ذكور: {vals['male']:6.0f}  إناث: {vals['female']:6.0f}  CTR: {avg_ctr:.2f}%")
    else:
        print(f"  {YELLOW}  لا توجد بيانات جمهور كافية{RESET}")

    # ── Geo ───────────────────────────────────────────────────────────────────
    geo_data = data["insights_geo"]
    if geo_data:
        subsection("التوزيع الجغرافي (أعلى 8 دول)")
        top_geo = sorted(geo_data, key=lambda x: float(x.get("spend", 0)), reverse=True)[:8]
        for row in top_geo:
            print(f"  {row.get('country','—'):5}  إنفاق: {float(row.get('spend',0)):7.2f}  CTR: {float(row.get('ctr',0)):.2f}%")

    # ── Placements ────────────────────────────────────────────────────────────
    section("6 / أداء المنصات والمواضع")
    placement_data = data["insights_placement"]
    if placement_data:
        sorted_pl = sorted(placement_data, key=lambda x: float(x.get("spend", 0)), reverse=True)[:10]
        print(f"  {'المنصة':<20} {'الموضع':<25} {'إنفاق':>8} {'CPM':>8} {'CTR':>7}")
        print(f"  {SEP}")
        for row in sorted_pl:
            platform = row.get("publisher_platform", "—")
            position = row.get("platform_position", "—")
            sp = float(row.get("spend", 0))
            cpm_pl = float(row.get("cpm", 0))
            ctr_pl = float(row.get("ctr", 0))
            print(f"  {platform:<20} {position:<25} {sp:>8.2f} {cpm_pl:>8.2f} {ctr_pl:>7.2f}%")
    else:
        print(f"  {YELLOW}  لا توجد بيانات مواضع كافية{RESET}")

    # ── Weekly trend ──────────────────────────────────────────────────────────
    weekly = data["insights_weekly"]
    if weekly:
        section("7 / الأداء الأسبوعي (آخر 4 أسابيع)")
        print(f"  {'الأسبوع':<12} {'إنفاق':>8} {'وصول':>10} {'نقرات':>8} {'CTR':>7}")
        print(f"  {SEP}")
        for w in weekly:
            date_str = w.get("date_start", "—")[:10]
            print(
                f"  {date_str:<12} {float(w.get('spend',0)):>8.2f} "
                f"{int(w.get('reach',0)):>10,} {int(w.get('clicks',0)):>8,} "
                f"{float(w.get('ctr',0)):>7.2f}%"
            )

    # ── Scoring + Recommendations ─────────────────────────────────────────────
    section("8 / التشخيص والتوصيات")
    issues:    list[str] = []
    strengths: list[str] = []

    if cpm < 20:
        strengths.append(f"CPM منخفض ({cpm:.1f}) — كفاءة شراء جيدة")
    elif cpm > 30:
        issues.append(f"CPM مرتفع ({cpm:.1f}) — راجع الاستهداف أو الإبداعية")

    if ctr > 1.5:
        strengths.append(f"CTR ممتاز ({ctr:.2f}%) — الإبداعية تجذب الجمهور")
    elif ctr < 0.8:
        issues.append(f"CTR منخفض ({ctr:.2f}%) — جرّب إبداعيات جديدة (فيديو / Reels)")

    if freq > 5:
        issues.append(f"تكرار إعلاني مرتفع ({freq:.1f}x) — الجمهور يرى نفس الإعلان كثيراً → توسّع الجمهور أو غيّر الإبداعية")
    elif 2 <= freq <= 4:
        strengths.append(f"تكرار مثالي ({freq:.1f}x)")

    if used_legacy:
        issues.append(f"أهداف Legacy مستخدمة ({', '.join(set(used_legacy))}) — انتقل لـ ODAX للحصول على أداء أفضل")

    if not campaigns:
        issues.append("لا توجد حملات — ابدأ بالهيكل المقترح أدناه")

    if strengths:
        print(f"\n  {GREEN}نقاط القوة:{RESET}")
        for s in strengths:
            print(f"    ✓ {s}")

    if issues:
        print(f"\n  {RED}نقاط تحتاج تحسين:{RESET}")
        for i, iss in enumerate(issues, 1):
            print(f"    {i}. {iss}")

    # ── Recommended structure ─────────────────────────────────────────────────
    section("9 / هيكل الحملات المقترح (Q2 2026)")
    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │  AWARENESS — awareness_reels_q2_2026                   │
  │  الميزانية: 50 ريال/يوم | الجمهور: Lookalike 1–3%    │
  │  المواضع: Reels + Stories + Feed                       │
  ├─────────────────────────────────────────────────────────┤
  │  ENGAGEMENT — engagement_menu_q2_2026                  │
  │  الميزانية: 30 ريال/يوم | الجمهور: Page visitors 90d  │
  │  الهدف: تفاعل + مشاهدة منيو + فيديو                   │
  ├─────────────────────────────────────────────────────────┤
  │  LEADS — leads_whatsapp_q2_2026                        │
  │  الميزانية: 80 ريال/يوم | الجمهور: Retargeting 30d    │
  │  الهدف: رسائل واتساب + طلبات حجز                      │
  ├─────────────────────────────────────────────────────────┤
  │  TRAFFIC — leads_location_q2_2026                      │
  │  الميزانية: 40 ريال/يوم | نطاق 5كم من المطعم          │
  │  الهدف: زيارة خريطة Google / Waze                     │
  └─────────────────────────────────────────────────────────┘

  إجمالي الميزانية اليومية المقترحة: 200 ريال (~6,000 ريال/شهر)
    """)

    print(f"\n{BOLD}{GREEN}  لإنشاء الحملات تلقائياً:{RESET}")
    print(f"  python meta_restaurant_analysis.py --create\n")

    return {"cpm": cpm, "ctr": ctr, "freq": freq, "issues": len(issues)}


# ── campaign creation ─────────────────────────────────────────────────────────

CAMPAIGNS_TO_CREATE = [
    {
        "name": "awareness_reels_q2_2026",
        "objective": "AWARENESS",
        "daily_budget": 5000,  # 50 SAR in halala
        "adsets": [{
            "name": "lookalike_ksa_1_3pct",
            "optimization_goal": "REACH",
            "billing_event": "IMPRESSIONS",
            "daily_budget": 5000,
            "targeting": {
                "age_min": 18, "age_max": 50,
                "genders": [1, 2],
                "geo_locations": {"countries": ["SA"]},
            },
        }],
    },
    {
        "name": "engagement_menu_q2_2026",
        "objective": "ENGAGEMENT",
        "daily_budget": 3000,
        "adsets": [{
            "name": "page_visitors_90d",
            "optimization_goal": "POST_ENGAGEMENT",
            "billing_event": "IMPRESSIONS",
            "daily_budget": 3000,
            "targeting": {
                "age_min": 18, "age_max": 50,
                "genders": [1, 2],
                "geo_locations": {"countries": ["SA"]},
            },
        }],
    },
    {
        "name": "leads_whatsapp_q2_2026",
        "objective": "LEADS",
        "daily_budget": 8000,
        "adsets": [{
            "name": "retargeting_30d",
            "optimization_goal": "LEAD_GENERATION",
            "billing_event": "IMPRESSIONS",
            "daily_budget": 8000,
            "targeting": {
                "age_min": 18, "age_max": 55,
                "genders": [1, 2],
                "geo_locations": {"countries": ["SA"]},
            },
        }],
    },
    {
        "name": "traffic_location_q2_2026",
        "objective": "TRAFFIC",
        "daily_budget": 4000,
        "adsets": [{
            "name": "radius_5km_restaurant",
            "optimization_goal": "LINK_CLICKS",
            "billing_event": "IMPRESSIONS",
            "daily_budget": 4000,
            "targeting": {
                "age_min": 18, "age_max": 55,
                "genders": [1, 2],
                "geo_locations": {"countries": ["SA"]},
            },
        }],
    },
]


async def create_campaigns(client: httpx.AsyncClient) -> None:
    section("إنشاء هيكل الحملات المقترح")
    for camp_spec in CAMPAIGNS_TO_CREATE:
        print(f"\n  {YELLOW}▶ إنشاء حملة: {camp_spec['name']}{RESET}")
        camp_body = {
            "name":                  camp_spec["name"],
            "objective":             camp_spec["objective"],
            "status":                "PAUSED",
            "daily_budget":          camp_spec["daily_budget"],
            "special_ad_categories": "[]",
        }
        result = await api_post(client, f"/{ACCOUNT_ID}/campaigns", camp_body)
        campaign_id = result.get("id")
        if not campaign_id:
            print(f"  {RED}    فشل إنشاء الحملة — راجع الأخطاء أعلاه{RESET}")
            continue
        print(f"  {GREEN}    ✓ تم إنشاء الحملة — ID: {campaign_id}{RESET}")

        for adset_spec in camp_spec.get("adsets", []):
            print(f"    {YELLOW}▶ إنشاء مجموعة: {adset_spec['name']}{RESET}")
            adset_body = {
                "campaign_id":       campaign_id,
                "name":              adset_spec["name"],
                "billing_event":     adset_spec["billing_event"],
                "optimization_goal": adset_spec["optimization_goal"],
                "daily_budget":      adset_spec["daily_budget"],
                "status":            "PAUSED",
                "targeting":         adset_spec["targeting"],
            }
            adset_result = await api_post(client, f"/{ACCOUNT_ID}/adsets", adset_body)
            adset_id = adset_result.get("id")
            if adset_id:
                print(f"    {GREEN}    ✓ مجموعة إعلانية — ID: {adset_id}{RESET}")
            else:
                print(f"    {RED}    تعذّر إنشاء المجموعة{RESET}")

    print(f"\n{GREEN}{BOLD}  تم إنشاء الهيكل الكامل بنجاح — كل الحملات في وضع PAUSED{RESET}")
    print(f"  أضف الإعلانات عبر لوحة التحكم أو أداة meta_create_ad\n")


# ── main ──────────────────────────────────────────────────────────────────────

async def main(create: bool = False) -> None:
    if not ACCESS_TOKEN:
        print(f"{RED}خطأ: META_ACCESS_TOKEN غير محدد في ملف .env{RESET}")
        print(f"{YELLOW}شغّل أولاً: python meta_restaurant_analysis.py --refresh-token{RESET}")
        sys.exit(1)

    async with httpx.AsyncClient(timeout=30) as client:
        # Validate token before doing anything else
        if not await validate_token(client):
            sys.exit(1)

        data = await collect_all(client)
        print_report(data)

        if create:
            print(f"\n{YELLOW}سيتم إنشاء الحملات الأربع المقترحة بوضع PAUSED (لن تُنفق مالاً الآن)...{RESET}")
            confirm = input("  اكتب YES للتأكيد: ").strip()
            if confirm.upper() == "YES":
                await create_campaigns(client)
            else:
                print("  تم الإلغاء.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meta Restaurant Ads Analyzer")
    parser.add_argument("--create",        action="store_true", help="Create recommended campaign structure after analysis")
    parser.add_argument("--refresh-token", action="store_true", help="Exchange short-lived token for 60-day long-lived token")
    args = parser.parse_args()

    if args.refresh_token:
        asyncio.run(refresh_token_cmd())
    else:
        asyncio.run(main(create=args.create))
