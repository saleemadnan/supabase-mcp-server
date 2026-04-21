"""
Meta Ads Dashboard — standalone web app.

Run:
    python meta_dashboard.py

Then open http://localhost:8080 in your browser.

Requires environment variables:
    META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN, META_AD_ACCOUNT_ID
"""

from __future__ import annotations

import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from supabase_mcp.clients.meta_ads_client import MetaAdsClient

APP_ID = os.environ.get("META_APP_ID", "")
APP_SECRET = os.environ.get("META_APP_SECRET", "")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "")
API_VERSION = os.environ.get("META_API_VERSION", "v21.0")

if AD_ACCOUNT_ID and not AD_ACCOUNT_ID.startswith("act_"):
    AD_ACCOUNT_ID = f"act_{AD_ACCOUNT_ID}"

# Module-level client shared across all requests.
_meta_client: MetaAdsClient | None = None


def _get_client() -> MetaAdsClient:
    global _meta_client
    if _meta_client is None:
        _meta_client = MetaAdsClient(
            access_token=ACCESS_TOKEN,
            app_id=APP_ID,
            app_secret=APP_SECRET,
            api_version=API_VERSION,
            timeout=15.0,
        )
    return _meta_client


# ── API helpers ──────────────────────────────────────────────────────────────

def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return asyncio.run(_get_client().get(path, params))


def api_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_get_client().post(path, body=body))


def api_delete(path: str) -> dict[str, Any]:
    return asyncio.run(_get_client().delete(path))


# ── Dashboard HTML ────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>لوحة تحكم إعلانات Meta</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; background: #f0f2f5; color: #1c1e21; }}
  header {{ background: #1877f2; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }}
  header h1 {{ font-size: 1.4rem; }}
  .badge {{ background: #42b72a; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; }}
  .container {{ max-width: 1200px; margin: 24px auto; padding: 0 16px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card .label {{ font-size: .8rem; color: #65676b; margin-bottom: 6px; }}
  .card .value {{ font-size: 1.6rem; font-weight: 700; color: #1877f2; }}
  .section {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.1); margin-bottom: 24px; }}
  .section h2 {{ font-size: 1.1rem; margin-bottom: 16px; border-bottom: 2px solid #e4e6eb; padding-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: right; padding: 10px 12px; border-bottom: 1px solid #e4e6eb; font-size: .9rem; }}
  th {{ background: #f7f8fa; font-weight: 600; color: #65676b; }}
  tr:hover td {{ background: #f7f8fa; }}
  .status {{ display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: .75rem; font-weight: 600; }}
  .status.ACTIVE {{ background: #d4f7e0; color: #1a7a3c; }}
  .status.PAUSED {{ background: #fff3cd; color: #856404; }}
  .status.DELETED {{ background: #fde8e8; color: #842029; }}
  .btn {{ display: inline-block; padding: 6px 14px; border-radius: 6px; border: none; cursor: pointer; font-size: .85rem; font-weight: 600; text-decoration: none; }}
  .btn-primary {{ background: #1877f2; color: white; }}
  .btn-danger {{ background: #e74c3c; color: white; }}
  .btn-success {{ background: #42b72a; color: white; }}
  .btn-warning {{ background: #f0a500; color: white; }}
  .actions {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .form-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .form-group {{ display: flex; flex-direction: column; gap: 4px; }}
  .form-group label {{ font-size: .85rem; font-weight: 600; color: #444; }}
  .form-group input, .form-group select {{ padding: 8px 12px; border: 1px solid #ccd0d5; border-radius: 8px; font-size: .9rem; }}
  .form-group input:focus, .form-group select:focus {{ outline: none; border-color: #1877f2; }}
  .modal-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 100; align-items: center; justify-content: center; }}
  .modal-overlay.open {{ display: flex; }}
  .modal {{ background: white; border-radius: 12px; padding: 24px; width: 560px; max-width: 95vw; max-height: 90vh; overflow-y: auto; }}
  .modal h3 {{ margin-bottom: 16px; }}
  .modal-actions {{ margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end; }}
  .insights-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }}
  .insight-card {{ background: #f7f8fa; border-radius: 10px; padding: 14px; text-align: center; }}
  .insight-card .metric {{ font-size: 1.4rem; font-weight: 700; color: #1877f2; }}
  .insight-card .metric-label {{ font-size: .75rem; color: #65676b; margin-top: 4px; }}
  .error {{ color: #c0392b; background: #fde8e8; padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; }}
  .nav-tabs {{ display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 2px solid #e4e6eb; padding-bottom: 0; }}
  .nav-tab {{ padding: 8px 16px; cursor: pointer; border-radius: 8px 8px 0 0; font-weight: 600; color: #65676b; border: none; background: none; font-size: .9rem; }}
  .nav-tab.active {{ background: #1877f2; color: white; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
</style>
</head>
<body>

<header>
  <svg width="32" height="32" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.879V14.89h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.989C18.343 21.129 22 16.99 22 12c0-5.523-4.477-10-10-10z"/></svg>
  <h1>لوحة تحكم إعلانات Meta</h1>
  <span class="badge">API v19.0</span>
</header>

<div class="container">

  <!-- Summary cards -->
  <div class="cards" id="summary-cards">
    <div class="card"><div class="label">إجمالي الحملات</div><div class="value" id="total-campaigns">—</div></div>
    <div class="card"><div class="label">حملات نشطة</div><div class="value" id="active-campaigns">—</div></div>
    <div class="card"><div class="label">إجمالي الإنفاق (7 أيام)</div><div class="value" id="total-spend">—</div></div>
    <div class="card"><div class="label">إجمالي النقرات (7 أيام)</div><div class="value" id="total-clicks">—</div></div>
    <div class="card"><div class="label">إجمالي الوصول (7 أيام)</div><div class="value" id="total-reach">—</div></div>
    <div class="card"><div class="label">معدل النقر CTR</div><div class="value" id="avg-ctr">—</div></div>
  </div>

  <!-- Navigation tabs -->
  <div class="nav-tabs">
    <button class="nav-tab active" onclick="showTab('campaigns')">الحملات</button>
    <button class="nav-tab" onclick="showTab('adsets')">مجموعات الإعلانات</button>
    <button class="nav-tab" onclick="showTab('ads')">الإعلانات</button>
    <button class="nav-tab" onclick="showTab('insights')">التحليلات</button>
  </div>

  <!-- Campaigns tab -->
  <div class="tab-content active" id="tab-campaigns">
    <div class="section">
      <h2>الحملات الإعلانية
        <button class="btn btn-primary" style="float:left;margin-top:-2px" onclick="openCreateCampaign()">+ إنشاء حملة</button>
      </h2>
      <div id="campaigns-error"></div>
      <table>
        <thead><tr><th>الاسم</th><th>الهدف</th><th>الحالة</th><th>الميزانية اليومية</th><th>إجراءات</th></tr></thead>
        <tbody id="campaigns-table"></tbody>
      </table>
    </div>
  </div>

  <!-- Ad Sets tab -->
  <div class="tab-content" id="tab-adsets">
    <div class="section">
      <h2>مجموعات الإعلانات</h2>
      <div id="adsets-error"></div>
      <table>
        <thead><tr><th>الاسم</th><th>معرّف الحملة</th><th>الحالة</th><th>هدف التحسين</th><th>الميزانية اليومية</th><th>إجراءات</th></tr></thead>
        <tbody id="adsets-table"></tbody>
      </table>
    </div>
  </div>

  <!-- Ads tab -->
  <div class="tab-content" id="tab-ads">
    <div class="section">
      <h2>الإعلانات</h2>
      <div id="ads-error"></div>
      <table>
        <thead><tr><th>الاسم</th><th>معرّف المجموعة</th><th>الحالة</th><th>إجراءات</th></tr></thead>
        <tbody id="ads-table"></tbody>
      </table>
    </div>
  </div>

  <!-- Insights tab -->
  <div class="tab-content" id="tab-insights">
    <div class="section">
      <h2>التحليلات والأداء</h2>
      <div style="margin-bottom:16px;display:flex;gap:12px;align-items:center;">
        <label style="font-weight:600">الفترة الزمنية:</label>
        <select id="date-preset" onchange="loadInsights()" style="padding:8px 12px;border:1px solid #ccd0d5;border-radius:8px;">
          <option value="today">اليوم</option>
          <option value="yesterday">أمس</option>
          <option value="last_7d" selected>آخر 7 أيام</option>
          <option value="last_14d">آخر 14 يوم</option>
          <option value="last_30d">آخر 30 يوم</option>
          <option value="this_month">هذا الشهر</option>
          <option value="last_month">الشهر الماضي</option>
        </select>
      </div>
      <div class="insights-grid" id="insights-grid">
        <div class="insight-card"><div class="metric" id="ins-impressions">—</div><div class="metric-label">المشاهدات</div></div>
        <div class="insight-card"><div class="metric" id="ins-clicks">—</div><div class="metric-label">النقرات</div></div>
        <div class="insight-card"><div class="metric" id="ins-spend">—</div><div class="metric-label">الإنفاق ($)</div></div>
        <div class="insight-card"><div class="metric" id="ins-reach">—</div><div class="metric-label">الوصول</div></div>
        <div class="insight-card"><div class="metric" id="ins-cpc">—</div><div class="metric-label">تكلفة النقرة CPC</div></div>
        <div class="insight-card"><div class="metric" id="ins-cpm">—</div><div class="metric-label">تكلفة الألف CPM</div></div>
        <div class="insight-card"><div class="metric" id="ins-ctr">—</div><div class="metric-label">معدل النقر CTR%</div></div>
        <div class="insight-card"><div class="metric" id="ins-frequency">—</div><div class="metric-label">التكرار</div></div>
      </div>
    </div>
  </div>

</div>

<!-- Create Campaign Modal -->
<div class="modal-overlay" id="modal-create-campaign">
  <div class="modal">
    <h3>إنشاء حملة إعلانية جديدة</h3>
    <div id="create-campaign-error"></div>
    <div class="form-grid">
      <div class="form-group" style="grid-column:1/-1">
        <label>اسم الحملة *</label>
        <input type="text" id="cc-name" placeholder="مثال: حملة المبيعات - رمضان 2024">
      </div>
      <div class="form-group">
        <label>هدف الحملة *</label>
        <select id="cc-objective">
          <option value="AWARENESS">AWARENESS - الوعي بالعلامة</option>
          <option value="TRAFFIC">TRAFFIC - الزيارات</option>
          <option value="ENGAGEMENT">ENGAGEMENT - التفاعل</option>
          <option value="LEADS">LEADS - جمع العملاء المحتملين</option>
          <option value="SALES" selected>SALES - المبيعات</option>
          <option value="APP_PROMOTION">APP_PROMOTION - الترويج للتطبيق</option>
        </select>
      </div>
      <div class="form-group">
        <label>الحالة الأولية</label>
        <select id="cc-status">
          <option value="PAUSED" selected>متوقفة (مستحسن)</option>
          <option value="ACTIVE">نشطة</option>
        </select>
      </div>
      <div class="form-group">
        <label>الميزانية اليومية (سنت) — اختياري</label>
        <input type="number" id="cc-daily-budget" placeholder="مثال: 1000 = $10">
      </div>
      <div class="form-group">
        <label>الميزانية الإجمالية (سنت) — اختياري</label>
        <input type="number" id="cc-lifetime-budget" placeholder="مثال: 50000 = $500">
      </div>
    </div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal('modal-create-campaign')" style="background:#e4e6eb">إلغاء</button>
      <button class="btn btn-primary" onclick="submitCreateCampaign()">إنشاء الحملة</button>
    </div>
  </div>
</div>

<script>
const API = '/api';

async function fetchAPI(endpoint, opts={}) {{
  const r = await fetch(API + endpoint, {{
    headers: {{'Content-Type':'application/json'}},
    ...opts
  }});
  return r.json();
}}

// ── Tabs ──────────────────────────────────────────────────────────────────
function showTab(name) {{
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector(`[onclick="showTab('${{name}}')"]`).classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'campaigns') loadCampaigns();
  if (name === 'adsets') loadAdSets();
  if (name === 'ads') loadAds();
  if (name === 'insights') loadInsights();
}}

function openCreateCampaign() {{
  document.getElementById('modal-create-campaign').classList.add('open');
}}

function closeModal(id) {{
  document.getElementById(id).classList.remove('open');
}}

function fmtMoney(v) {{
  if (!v) return '—';
  return '$' + parseFloat(v).toFixed(2);
}}

function fmtNum(v) {{
  if (!v) return '—';
  return parseInt(v).toLocaleString('ar');
}}

function statusBadge(s) {{
  return `<span class="status ${{s}}">${{s}}</span>`;
}}

// ── Load summary ──────────────────────────────────────────────────────────
async function loadSummary() {{
  const [camps, insights] = await Promise.all([
    fetchAPI('/campaigns'),
    fetchAPI('/insights?date_preset=last_7d')
  ]);
  const data = camps.data || [];
  document.getElementById('total-campaigns').textContent = data.length;
  document.getElementById('active-campaigns').textContent = data.filter(c=>c.status==='ACTIVE').length;

  if (insights.data && insights.data[0]) {{
    const d = insights.data[0];
    document.getElementById('total-spend').textContent = fmtMoney(d.spend);
    document.getElementById('total-clicks').textContent = fmtNum(d.clicks);
    document.getElementById('total-reach').textContent = fmtNum(d.reach);
    document.getElementById('avg-ctr').textContent = d.ctr ? parseFloat(d.ctr).toFixed(2)+'%' : '—';
  }}
}}

// ── Campaigns ──────────────────────────────────────────────────────────────
async function loadCampaigns() {{
  const result = await fetchAPI('/campaigns');
  const tbody = document.getElementById('campaigns-table');
  const errEl = document.getElementById('campaigns-error');
  if (result.error) {{
    errEl.innerHTML = `<div class="error">${{result.error.message}}</div>`;
    return;
  }}
  errEl.innerHTML = '';
  const rows = (result.data || []).map(c => `
    <tr>
      <td><strong>${{c.name}}</strong><br><small style="color:#65676b">${{c.id}}</small></td>
      <td>${{c.objective||'—'}}</td>
      <td>${{statusBadge(c.status)}}</td>
      <td>${{c.daily_budget ? fmtMoney(parseInt(c.daily_budget)/100) : '—'}}</td>
      <td><div class="actions">
        <button class="btn btn-success" onclick="toggleCampaign('${{c.id}}', ${{c.status!=='ACTIVE'}})">${{c.status==='ACTIVE'?'إيقاف':'تشغيل'}}</button>
        <button class="btn btn-danger" onclick="deleteCampaign('${{c.id}}','${{c.name}}')">حذف</button>
      </div></td>
    </tr>`).join('');
  tbody.innerHTML = rows || '<tr><td colspan="5" style="text-align:center;color:#65676b">لا توجد حملات</td></tr>';
}}

async function toggleCampaign(id, active) {{
  await fetchAPI('/campaigns/toggle', {{method:'POST', body:JSON.stringify({{campaign_id:id, active}})}});
  loadCampaigns(); loadSummary();
}}

async function deleteCampaign(id, name) {{
  if (!confirm(`هل أنت متأكد من حذف الحملة "${{name}}"؟ هذا الإجراء لا يمكن التراجع عنه.`)) return;
  await fetchAPI('/campaigns/' + id, {{method:'DELETE'}});
  loadCampaigns(); loadSummary();
}}

async function submitCreateCampaign() {{
  const errEl = document.getElementById('create-campaign-error');
  const body = {{
    name: document.getElementById('cc-name').value.trim(),
    objective: document.getElementById('cc-objective').value,
    status: document.getElementById('cc-status').value,
    special_ad_categories: [],
  }};
  const db = document.getElementById('cc-daily-budget').value;
  const lb = document.getElementById('cc-lifetime-budget').value;
  if (db) body.daily_budget = parseInt(db);
  if (lb) body.lifetime_budget = parseInt(lb);
  if (!body.name) {{ errEl.innerHTML='<div class="error">اسم الحملة مطلوب</div>'; return; }}
  const result = await fetchAPI('/campaigns', {{method:'POST', body:JSON.stringify(body)}});
  if (result.error) {{ errEl.innerHTML=`<div class="error">${{result.error.message}}</div>`; return; }}
  closeModal('modal-create-campaign');
  loadCampaigns(); loadSummary();
}}

// ── Ad Sets ────────────────────────────────────────────────────────────────
async function loadAdSets() {{
  const result = await fetchAPI('/adsets');
  const tbody = document.getElementById('adsets-table');
  const errEl = document.getElementById('adsets-error');
  if (result.error) {{ errEl.innerHTML=`<div class="error">${{result.error.message}}</div>`; return; }}
  errEl.innerHTML = '';
  const rows = (result.data || []).map(s => `
    <tr>
      <td><strong>${{s.name}}</strong><br><small style="color:#65676b">${{s.id}}</small></td>
      <td><small>${{s.campaign_id}}</small></td>
      <td>${{statusBadge(s.status)}}</td>
      <td>${{s.optimization_goal||'—'}}</td>
      <td>${{s.daily_budget ? fmtMoney(parseInt(s.daily_budget)/100) : '—'}}</td>
      <td><div class="actions">
        <button class="btn btn-danger" onclick="deleteAdSet('${{s.id}}','${{s.name}}')">حذف</button>
      </div></td>
    </tr>`).join('');
  tbody.innerHTML = rows || '<tr><td colspan="6" style="text-align:center;color:#65676b">لا توجد مجموعات إعلانات</td></tr>';
}}

async function deleteAdSet(id, name) {{
  if (!confirm(`هل أنت متأكد من حذف مجموعة الإعلانات "${{name}}"؟`)) return;
  await fetchAPI('/adsets/' + id, {{method:'DELETE'}});
  loadAdSets();
}}

// ── Ads ────────────────────────────────────────────────────────────────────
async function loadAds() {{
  const result = await fetchAPI('/ads');
  const tbody = document.getElementById('ads-table');
  const errEl = document.getElementById('ads-error');
  if (result.error) {{ errEl.innerHTML=`<div class="error">${{result.error.message}}</div>`; return; }}
  errEl.innerHTML = '';
  const rows = (result.data || []).map(a => `
    <tr>
      <td><strong>${{a.name}}</strong><br><small style="color:#65676b">${{a.id}}</small></td>
      <td><small>${{a.adset_id}}</small></td>
      <td>${{statusBadge(a.status)}}</td>
      <td><div class="actions">
        <button class="btn btn-danger" onclick="deleteAd('${{a.id}}','${{a.name}}')">حذف</button>
      </div></td>
    </tr>`).join('');
  tbody.innerHTML = rows || '<tr><td colspan="4" style="text-align:center;color:#65676b">لا توجد إعلانات</td></tr>';
}}

async function deleteAd(id, name) {{
  if (!confirm(`هل أنت متأكد من حذف الإعلان "${{name}}"؟`)) return;
  await fetchAPI('/ads/' + id, {{method:'DELETE'}});
  loadAds();
}}

// ── Insights ───────────────────────────────────────────────────────────────
async function loadInsights() {{
  const preset = document.getElementById('date-preset').value;
  const result = await fetchAPI(`/insights?date_preset=${{preset}}`);
  if (result.data && result.data[0]) {{
    const d = result.data[0];
    document.getElementById('ins-impressions').textContent = fmtNum(d.impressions);
    document.getElementById('ins-clicks').textContent = fmtNum(d.clicks);
    document.getElementById('ins-spend').textContent = fmtMoney(d.spend);
    document.getElementById('ins-reach').textContent = fmtNum(d.reach);
    document.getElementById('ins-cpc').textContent = d.cpc ? '$'+parseFloat(d.cpc).toFixed(3) : '—';
    document.getElementById('ins-cpm').textContent = d.cpm ? '$'+parseFloat(d.cpm).toFixed(2) : '—';
    document.getElementById('ins-ctr').textContent = d.ctr ? parseFloat(d.ctr).toFixed(2)+'%' : '—';
    document.getElementById('ins-frequency').textContent = d.frequency ? parseFloat(d.frequency).toFixed(2) : '—';
  }} else {{
    ['impressions','clicks','spend','reach','cpc','cpm','ctr','frequency'].forEach(k =>
      document.getElementById('ins-'+k).textContent = '—');
  }}
}}

// Initial load
loadSummary();
loadCampaigns();
</script>
</body>
</html>
"""


# ── HTTP handler ──────────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # suppress default logs
        pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._send_html(HTML_TEMPLATE)
            return

        if path == "/api/campaigns":
            result = api_get(f"/{AD_ACCOUNT_ID}/campaigns", {
                "fields": "id,name,status,objective,daily_budget,lifetime_budget",
                "limit": "50",
            })
            self._send_json(result)
            return

        if path == "/api/adsets":
            result = api_get(f"/{AD_ACCOUNT_ID}/adsets", {
                "fields": "id,name,status,campaign_id,daily_budget,optimization_goal",
                "limit": "50",
            })
            self._send_json(result)
            return

        if path == "/api/ads":
            result = api_get(f"/{AD_ACCOUNT_ID}/ads", {
                "fields": "id,name,status,adset_id",
                "limit": "50",
            })
            self._send_json(result)
            return

        if path == "/api/insights":
            preset = qs.get("date_preset", ["last_7d"])[0]
            result = api_get(f"/{AD_ACCOUNT_ID}/insights", {
                "fields": "impressions,clicks,spend,reach,cpc,cpm,ctr,frequency",
                "date_preset": preset,
            })
            self._send_json(result)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/campaigns":
            result = api_post(f"/{AD_ACCOUNT_ID}/campaigns", body)
            self._send_json(result)
            return

        if path == "/api/campaigns/toggle":
            cid = body.get("campaign_id", "")
            active = body.get("active", False)
            result = api_post(f"/{cid}", {"status": "ACTIVE" if active else "PAUSED"})
            self._send_json(result)
            return

        self.send_response(404)
        self.end_headers()

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        parts = path.strip("/").split("/")  # ['api', 'campaigns', 'ID']

        if len(parts) == 3 and parts[0] == "api":
            resource_id = parts[2]
            result = api_delete(f"/{resource_id}")
            self._send_json(result)
            return

        self.send_response(404)
        self.end_headers()


def main() -> None:
    if not ACCESS_TOKEN:
        print("ERROR: META_ACCESS_TOKEN is not set.")
        print("Set it with:  export META_ACCESS_TOKEN=your_token")
        return
    if not AD_ACCOUNT_ID:
        print("ERROR: META_AD_ACCOUNT_ID is not set.")
        print("Set it with:  export META_AD_ACCOUNT_ID=123456789")
        return

    port = int(os.environ.get("DASHBOARD_PORT", 8080))
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"✓ Meta Ads Dashboard running at http://localhost:{port}")
    print(f"  Ad Account: {AD_ACCOUNT_ID}")
    print("  Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
