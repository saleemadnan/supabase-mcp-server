/**
 * MetaAdsClient - قالب للاتصال بـ Meta Marketing API
 * الإصدار: v25.0
 *
 * الإصلاحات المُطبَّقة:
 *  - POST يستخدم application/x-www-form-urlencoded (مطلوب من Meta API)
 *  - تنظيف القيم undefined قبل إرسالها
 *  - أنواع TypeScript أكثر أماناً بدون double-cast
 *  - معالجة أخطاء أوضح مع رمز الخطأ (error.code)
 */

import { createCipheriv, createDecipheriv, randomBytes, createHash } from 'crypto';

const API_BASE = 'https://graph.facebook.com';

// ─── أنواع البيانات ────────────────────────────────────────────────────────

export interface Campaign {
  id: string;
  name: string;
  status: 'ACTIVE' | 'PAUSED' | 'DELETED' | 'ARCHIVED';
  objective: string;
  daily_budget?: string;
  lifetime_budget?: string;
  start_time?: string;
  stop_time?: string;
  created_time?: string;
}

export interface Insight {
  reach?: string;
  impressions?: string;
  clicks?: string;
  spend?: string;
  cpc?: string;
  ctr?: string;
  cpm?: string;
  frequency?: string;
  date_start?: string;
  date_stop?: string;
}

export interface AdSet {
  id: string;
  name: string;
  status: string;
  daily_budget?: string;
  start_time?: string;
  end_time?: string;
  targeting?: Record<string, unknown>;
}

export interface Ad {
  id: string;
  name: string;
  status: string;
  creative?: { title?: string; body?: string; image_url?: string };
}

export interface AudienceBreakdown {
  age?: string;
  gender?: string;
  country?: string;
  device_platform?: string;
  impression_device?: string;
  publisher_platform?: string;
  reach?: string;
  impressions?: string;
  spend?: string;
  clicks?: string;
}

export interface AccountInfo {
  id: string;
  name: string;
  account_status: number;
  currency: string;
  timezone_name: string;
  spend_cap?: string;
  amount_spent?: string;
  balance?: string;
}

export interface CreateCampaignParams {
  name: string;
  objective: string;
  status?: 'ACTIVE' | 'PAUSED';
  dailyBudget?: number;
  lifetimeBudget?: number;
}

export interface UpdateCampaignParams {
  status?: 'ACTIVE' | 'PAUSED' | 'ARCHIVED';
  daily_budget?: number;
  lifetime_budget?: number;
  name?: string;
  start_time?: string;
  stop_time?: string;
}

// شكل الخطأ القادم من Meta API
interface MetaError {
  message: string;
  code: number;
  type?: string;
  fbtrace_id?: string;
}

interface MetaErrorResponse {
  error: MetaError;
}

// ─── تشفير/فك تشفير AES-256-GCM ───────────────────────────────────────────

function getKey(secret: string): Buffer {
  return createHash('sha256').update(secret).digest();
}

export function encryptToken(token: string, secret: string): string {
  const key = getKey(secret);
  const iv = randomBytes(16);
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  const encrypted = Buffer.concat([cipher.update(token, 'utf8'), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return Buffer.concat([iv, authTag, encrypted]).toString('base64');
}

export function decryptToken(encrypted: string, secret: string): string {
  const buf = Buffer.from(encrypted, 'base64');
  const iv = buf.subarray(0, 16);
  const authTag = buf.subarray(16, 32);
  const ciphertext = buf.subarray(32);
  const key = getKey(secret);
  const decipher = createDecipheriv('aes-256-gcm', key, iv);
  decipher.setAuthTag(authTag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString('utf8');
}

// ─── خطأ مُخصَّص ────────────────────────────────────────────────────────────

export class MetaApiError extends Error {
  constructor(
    message: string,
    public readonly code: number,
    public readonly type?: string,
    public readonly traceId?: string,
  ) {
    super(`Meta API Error [${code}]: ${message}`);
    this.name = 'MetaApiError';
  }
}

// ─── مساعد: تنظيف undefined من الكائن ─────────────────────────────────────

function stripUndefined(obj: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(obj)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => [k, String(v)]),
  ) as Record<string, string>;
}

// ─── MetaAdsClient ─────────────────────────────────────────────────────────

export class MetaAdsClient {
  private readonly token: string;
  private readonly adAccountId: string;
  private readonly apiVersion: string;

  constructor(token: string, adAccountId: string, apiVersion = 'v25.0') {
    if (!token) throw new Error('token is required');
    if (!adAccountId) throw new Error('adAccountId is required');
    this.token = token;
    this.adAccountId = adAccountId.startsWith('act_') ? adAccountId : `act_${adAccountId}`;
    this.apiVersion = apiVersion;
  }

  // ─── HTTP helpers ───────────────────────────────────────────────────────

  private async request<T>(path: string, params: Record<string, string> = {}): Promise<T> {
    const url = new URL(`${API_BASE}/${this.apiVersion}/${path}`);
    url.searchParams.set('access_token', this.token);
    for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);

    const res = await fetch(url.toString());
    const data = (await res.json()) as T | MetaErrorResponse;
    this.throwIfError(data);
    return data as T;
  }

  /**
   * ИСПРАВЛЕНИЕ: Meta Graph API требует application/x-www-form-urlencoded для POST,
   * а НЕ application/json.
   * FIX: Meta Graph API requires application/x-www-form-urlencoded for POST, NOT application/json.
   * إصلاح: Meta API تتطلب application/x-www-form-urlencoded للـ POST وليس JSON.
   */
  private async post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    const url = `${API_BASE}/${this.apiVersion}/${path}`;

    // تنظيف undefined + إضافة token
    const clean = stripUndefined({ ...body, access_token: this.token });
    const formBody = new URLSearchParams(clean).toString();

    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formBody,
    });

    const data = (await res.json()) as T | MetaErrorResponse;
    this.throwIfError(data);
    return data as T;
  }

  private throwIfError(data: unknown): void {
    if (data && typeof data === 'object' && 'error' in data) {
      const err = (data as MetaErrorResponse).error;
      throw new MetaApiError(err.message, err.code, err.type, err.fbtrace_id);
    }
  }

  // ─── الحملات ─────────────────────────────────────────────────────────────

  async getCampaigns(): Promise<{ data: Campaign[] }> {
    return this.request(`${this.adAccountId}/campaigns`, {
      fields: 'id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time,created_time',
    });
  }

  async getCampaignInsights(
    campaignId: string,
    datePreset = 'last_30d',
  ): Promise<{ data: Insight[] }> {
    return this.request(`${campaignId}/insights`, {
      fields: 'reach,impressions,clicks,spend,cpc,ctr,cpm,frequency',
      date_preset: datePreset,
    });
  }

  async createCampaign(params: CreateCampaignParams): Promise<{ id: string }> {
    const body: Record<string, unknown> = {
      name: params.name,
      objective: params.objective,
      status: params.status ?? 'PAUSED',
      special_ad_categories: '[]',
    };
    // إرسال الميزانية فقط إذا كانت موجودة — لا يُسمح بإرسالهما معاً
    if (params.dailyBudget !== undefined) body.daily_budget = params.dailyBudget;
    else if (params.lifetimeBudget !== undefined) body.lifetime_budget = params.lifetimeBudget;

    return this.post(`${this.adAccountId}/campaigns`, body);
  }

  async updateCampaign(
    campaignId: string,
    updates: UpdateCampaignParams,
  ): Promise<{ success: boolean }> {
    return this.post(campaignId, updates as Record<string, unknown>);
  }

  async deleteCampaign(campaignId: string): Promise<{ success: boolean }> {
    return this.post(campaignId, { _method: 'DELETE' });
  }

  // ─── Ad Sets ──────────────────────────────────────────────────────────────

  async getAdSets(campaignId: string): Promise<{ data: AdSet[] }> {
    return this.request(`${campaignId}/adsets`, {
      fields: 'id,name,status,daily_budget,start_time,end_time,targeting',
    });
  }

  async updateAdSet(
    adSetId: string,
    updates: { status?: string; daily_budget?: number },
  ): Promise<{ success: boolean }> {
    return this.post(adSetId, updates as Record<string, unknown>);
  }

  // ─── الإعلانات ────────────────────────────────────────────────────────────

  async getAds(adSetId: string): Promise<{ data: Ad[] }> {
    return this.request(`${adSetId}/ads`, {
      fields: 'id,name,status,creative{title,body,image_url}',
    });
  }

  async updateAd(adId: string, updates: { status?: string }): Promise<{ success: boolean }> {
    return this.post(adId, updates as Record<string, unknown>);
  }

  // ─── تحليل الجمهور ────────────────────────────────────────────────────────

  async getAudienceDemographics(
    campaignId: string,
    datePreset = 'last_30d',
  ): Promise<{ data: AudienceBreakdown[] }> {
    return this.request(`${campaignId}/insights`, {
      fields: 'reach,impressions,spend,clicks',
      breakdowns: 'age,gender',
      date_preset: datePreset,
    });
  }

  async getAudienceGeographic(
    campaignId: string,
    datePreset = 'last_30d',
  ): Promise<{ data: AudienceBreakdown[] }> {
    return this.request(`${campaignId}/insights`, {
      fields: 'reach,impressions,spend',
      breakdowns: 'country',
      date_preset: datePreset,
    });
  }

  async getAudienceDevices(
    campaignId: string,
    datePreset = 'last_30d',
  ): Promise<{ data: AudienceBreakdown[] }> {
    return this.request(`${campaignId}/insights`, {
      fields: 'reach,impressions,spend',
      breakdowns: 'device_platform,impression_device',
      date_preset: datePreset,
    });
  }

  async getAudienceHourly(campaignId: string): Promise<{ data: AudienceBreakdown[] }> {
    return this.request(`${campaignId}/insights`, {
      fields: 'reach,impressions,spend',
      breakdowns: 'hourly_stats_aggregated_by_advertiser_time_zone',
      date_preset: 'last_7d',
    });
  }

  // ─── معلومات الحساب ───────────────────────────────────────────────────────

  async getAccountInfo(): Promise<AccountInfo> {
    return this.request(this.adAccountId, {
      fields: 'id,name,account_status,currency,timezone_name,spend_cap,amount_spent,balance',
    });
  }

  /** التحقق من صلاحية الـ token */
  async validateToken(): Promise<{ id: string; name: string }> {
    return this.request('me', { fields: 'id,name' });
  }
}
