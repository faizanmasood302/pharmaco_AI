# Meta Ads Management Platform — Project Constitution

> **Version:** 1.0  
> **Status:** Active  
> **Last Updated:** June 2026  
> **Classification:** Internal — Do Not Share with Clients

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Core Principles](#2-core-principles)
3. [Technology Stack](#3-technology-stack)
4. [System Architecture](#4-system-architecture)
5. [Database Schema](#5-database-schema)
6. [Row Level Security Policies](#6-row-level-security-policies)
7. [Commission Engine](#7-commission-engine)
8. [Meta Sync Service](#8-meta-sync-service)
9. [Authentication & Access Control](#9-authentication--access-control)
10. [Client Portal](#10-client-portal)
11. [Internal Admin Tool](#11-internal-admin-tool)
12. [API Design](#12-api-design)
13. [Security Rules](#13-security-rules)
14. [Environment Variables](#14-environment-variables)
15. [Deployment](#15-deployment)
16. [Build Phases & Timeline](#16-build-phases--timeline)
17. [Handoff & Maintenance](#17-handoff--maintenance)

---

## 1. Project Overview

### What This Is

A multi-tenant Meta Ads management and reporting platform. It allows an internal team to manage Meta Business Managers, ad accounts, campaigns, ad sets, and ads across multiple clients — while giving each client a secure, isolated portal to view their own campaign performance.

### What Makes It Unique

- **Hidden commission logic.** Raw spend figures from Meta are stored internally. Clients only ever see marked-up spend figures. This logic is enforced at the database level, not just the UI level.
- **Multi-tenant isolation.** Each client sees only their own data. No client can access another client's campaigns, spend, or account structure under any circumstances.
- **AI-first development.** Built entirely using Claude Code with Meta Ads MCP connected. Fast execution is a design requirement, not just a goal.

### Who Uses It

| User Type | Access Level | What They See |
|---|---|---|
| Internal Admin | Full access | Raw spend, marked spend, all clients, all accounts, commission rules |
| Client User | Scoped to their org | Marked spend only, their own campaigns and ad sets |

---

## 2. Core Principles

These principles govern every decision made during development.

### P1 — Raw Spend Is Never Client-Visible

`raw_spend` must never appear in:
- Any client-facing API response
- Any client-facing UI component
- Any client-accessible database view or function
- Any log or error message returned to a client session

This is a non-negotiable security requirement. It is enforced at three layers: database RLS, server-side API, and TypeScript types.

### P2 — Multi-Tenant Isolation Is Absolute

A client user authenticated as Client A must be architecturally incapable of reading Client B's data. This is not a UI concern — it is an RLS and schema concern. Every query from a client session must be filtered by `client_id` via RLS automatically.

### P3 — Server-Side Transformation Only

Commission logic runs server-side, always. No commission calculation happens in the browser. The browser receives `marked_spend` only. It never receives `raw_spend` and applies a multiplier client-side.

### P4 — Schema First

The database schema is the source of truth. API routes, TypeScript types, and UI components are all derived from the schema. If there is a conflict between the schema and the code, the schema wins.

### P5 — Fail Closed

If a sync fails, the platform shows the last known good data with a visible sync warning. It does not show blank data and it does not show stale data without flagging it. If an RLS policy cannot determine the user's `client_id`, it denies access by default.

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Database | Supabase (PostgreSQL) | Data storage, auth, RLS, Edge Functions |
| Sync Service | Supabase Edge Functions | Cron-based Meta data sync |
| Backend API | Next.js 15 Route Handlers | Server-side API, commission transformation |
| Frontend | Next.js 15 App Router | Both client portal and internal admin UI |
| Charts | Recharts | All dashboard visualisations |
| Meta Data | Meta Ads MCP (`mcp.facebook.com/ads`) | Source of all ad performance data |
| Deployment | Vercel | Hosting, environment management |
| Auth | Supabase Auth | User sessions, JWT, role claims |

### What Is Not in the Stack

- No Redis or external cache layer (Supabase handles this)
- No separate Express or Fastify server (Next.js Route Handlers only)
- No GraphQL (REST API only)
- No third-party auth provider (Supabase Auth only)

---

## 4. System Architecture

### Data Flow — Sync Path

```
Meta Ads MCP
    v (raw account structure + raw spend)
Supabase Edge Function (cron, every 6 hours)
    v (writes raw_spend to daily_stats table)
PostgreSQL — internal tables (raw_spend stored here, RLS locked)
```

### Data Flow — Client Request Path

```
Client Browser
    v (authenticated request with JWT)
Next.js Route Handler (/api/client/...)
    v (queries client_spend_view — never raw table)
Supabase (RLS enforced on JWT role = 'client')
    v (returns marked_spend only)
Next.js Route Handler (typed response — no raw_spend field)
    v
Client Browser (receives marked_spend only)
```

### Data Flow — Internal Admin Request Path

```
Internal Browser
    v (authenticated request with JWT)
Next.js Route Handler (/api/admin/...)
    v (queries raw tables with service role or internal_admin role)
Supabase (RLS permits raw_spend for internal_admin role)
    v (returns raw_spend + marked_spend)
Internal Browser (both figures visible)
```

### Commission Firewall

The commission firewall is the boundary between the internal data layer and the client-facing data layer. It is not a single function — it is a combination of:

1. RLS policies that block client users from `daily_stats.raw_spend`
2. A `client_spend_view` database view that only exposes `marked_spend`
3. Next.js route handlers that only query `client_spend_view`
4. TypeScript response types that have no `raw_spend` field

---

## 5. Database Schema

### 5.1 organisations

```sql
CREATE TABLE organisations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  slug        TEXT UNIQUE NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);
```

The top-level entity. The internal team belongs to the owner organisation. Each client belongs to their own organisation.

---

### 5.2 clients

```sql
CREATE TABLE clients (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organisation_id UUID REFERENCES organisations(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'archived')),
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);
```

---

### 5.3 users

```sql
CREATE TABLE users (
  id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  organisation_id UUID REFERENCES organisations(id),
  client_id       UUID REFERENCES clients(id),
  role            TEXT NOT NULL CHECK (role IN ('internal_admin', 'client_user')),
  full_name       TEXT,
  email           TEXT UNIQUE NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);
```

- `internal_admin` users have `client_id = NULL`
- `client_user` users must have a `client_id` set

---

### 5.4 meta_business_managers

```sql
CREATE TABLE meta_business_managers (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id       UUID REFERENCES clients(id) ON DELETE CASCADE,
  meta_bm_id      TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  synced_at       TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

### 5.5 ad_accounts

```sql
CREATE TABLE ad_accounts (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_manager_id      UUID REFERENCES meta_business_managers(id) ON DELETE CASCADE,
  client_id                UUID REFERENCES clients(id) ON DELETE CASCADE,
  meta_account_id          TEXT UNIQUE NOT NULL,
  name                     TEXT NOT NULL,
  currency                 TEXT DEFAULT 'USD',
  timezone                 TEXT,
  status                   TEXT,
  synced_at                TIMESTAMPTZ,
  created_at               TIMESTAMPTZ DEFAULT now()
);
```

---

### 5.6 campaigns

```sql
CREATE TABLE campaigns (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ad_account_id     UUID REFERENCES ad_accounts(id) ON DELETE CASCADE,
  client_id         UUID REFERENCES clients(id) ON DELETE CASCADE,
  meta_campaign_id  TEXT UNIQUE NOT NULL,
  name              TEXT NOT NULL,
  objective         TEXT,
  status            TEXT,
  daily_budget      NUMERIC(12,2),
  lifetime_budget   NUMERIC(12,2),
  start_time        TIMESTAMPTZ,
  stop_time         TIMESTAMPTZ,
  synced_at         TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT now()
);
```

---

### 5.7 ad_sets

```sql
CREATE TABLE ad_sets (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id     UUID REFERENCES campaigns(id) ON DELETE CASCADE,
  client_id       UUID REFERENCES clients(id) ON DELETE CASCADE,
  meta_adset_id   TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  status          TEXT,
  daily_budget    NUMERIC(12,2),
  targeting       JSONB,
  synced_at       TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

### 5.8 ads

```sql
CREATE TABLE ads (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ad_set_id     UUID REFERENCES ad_sets(id) ON DELETE CASCADE,
  client_id     UUID REFERENCES clients(id) ON DELETE CASCADE,
  meta_ad_id    TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  status        TEXT,
  creative      JSONB,
  synced_at     TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT now()
);
```

---

### 5.9 daily_stats

```sql
CREATE TABLE daily_stats (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id       UUID REFERENCES clients(id) ON DELETE CASCADE,
  ad_account_id   UUID REFERENCES ad_accounts(id),
  campaign_id     UUID REFERENCES campaigns(id),
  ad_set_id       UUID REFERENCES ad_sets(id),
  ad_id           UUID REFERENCES ads(id),
  stat_date       DATE NOT NULL,
  raw_spend       NUMERIC(12,4) NOT NULL,
  impressions     BIGINT DEFAULT 0,
  clicks          BIGINT DEFAULT 0,
  reach           BIGINT DEFAULT 0,
  conversions     BIGINT DEFAULT 0,
  cpm             NUMERIC(10,4),
  cpc             NUMERIC(10,4),
  ctr             NUMERIC(8,6),
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE (client_id, campaign_id, ad_set_id, ad_id, stat_date)
);
```

> [WARNING]️ `raw_spend` in this table is the most sensitive field in the entire system. RLS must block all client users from this column.

---

### 5.10 commission_rules

```sql
CREATE TABLE commission_rules (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id       UUID REFERENCES clients(id) ON DELETE CASCADE,
  rate            NUMERIC(5,4) NOT NULL CHECK (rate >= 0 AND rate <= 10),
  effective_from  DATE NOT NULL,
  effective_to    DATE,
  note            TEXT,
  created_by      UUID REFERENCES users(id),
  created_at      TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT no_overlapping_rules EXCLUDE USING gist (
    client_id WITH =,
    daterange(effective_from, effective_to, '[)') WITH &&
  )
);
```

`rate` is a decimal multiplier. `0.20` means 20% markup. `marked_spend = raw_spend * (1 + rate)`.

---

### 5.11 sync_logs

```sql
CREATE TABLE sync_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sync_type     TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'partial')),
  records_synced INT DEFAULT 0,
  error_message TEXT,
  started_at    TIMESTAMPTZ DEFAULT now(),
  completed_at  TIMESTAMPTZ,
  meta          JSONB
);
```

---

### 5.12 Client Spend View (Commission Firewall)

```sql
CREATE VIEW client_spend_view AS
SELECT
  ds.id,
  ds.client_id,
  ds.ad_account_id,
  ds.campaign_id,
  ds.ad_set_id,
  ds.ad_id,
  ds.stat_date,
  ROUND(ds.raw_spend * (1 + COALESCE(cr.rate, 0)), 2) AS spend,
  ds.impressions,
  ds.clicks,
  ds.reach,
  ds.conversions,
  ds.cpm,
  ds.cpc,
  ds.ctr
FROM daily_stats ds
LEFT JOIN commission_rules cr
  ON cr.client_id = ds.client_id
  AND ds.stat_date >= cr.effective_from
  AND (cr.effective_to IS NULL OR ds.stat_date < cr.effective_to)
WHERE ds.client_id = (
  SELECT client_id FROM users WHERE id = auth.uid()
);
```

> This view has **no `raw_spend` column**. It is the only data source client-facing routes are permitted to query.

---

### 5.13 Indexes

```sql
-- Performance indexes
CREATE INDEX idx_daily_stats_client_date ON daily_stats(client_id, stat_date DESC);
CREATE INDEX idx_daily_stats_campaign ON daily_stats(campaign_id, stat_date DESC);
CREATE INDEX idx_campaigns_client ON campaigns(client_id);
CREATE INDEX idx_ad_sets_campaign ON ad_sets(campaign_id);
CREATE INDEX idx_ads_adset ON ads(ad_set_id);
CREATE INDEX idx_commission_rules_client ON commission_rules(client_id, effective_from);
CREATE INDEX idx_sync_logs_started ON sync_logs(started_at DESC);
```

---

## 6. Row Level Security Policies

### Principle

Every table has RLS enabled. The default is **deny all**. Policies explicitly grant access based on role.

```sql
-- Enable RLS on all tables
ALTER TABLE organisations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients           ENABLE ROW LEVEL SECURITY;
ALTER TABLE users             ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_business_managers ENABLE ROW LEVEL SECURITY;
ALTER TABLE ad_accounts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns         ENABLE ROW LEVEL SECURITY;
ALTER TABLE ad_sets           ENABLE ROW LEVEL SECURITY;
ALTER TABLE ads               ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_stats       ENABLE ROW LEVEL SECURITY;
ALTER TABLE commission_rules  ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_logs         ENABLE ROW LEVEL SECURITY;
```

---

### daily_stats — The Critical Table

```sql
-- Internal admins can read everything including raw_spend
CREATE POLICY "internal_admin_read_daily_stats"
ON daily_stats FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM users
    WHERE id = auth.uid() AND role = 'internal_admin'
  )
);

-- Client users CANNOT read daily_stats directly — ever
-- They must use client_spend_view which has no raw_spend column
-- No SELECT policy is granted to client_user role on this table
```

---

### clients — Scoped to own record

```sql
CREATE POLICY "client_user_read_own_client"
ON clients FOR SELECT
USING (
  id = (SELECT client_id FROM users WHERE id = auth.uid())
  OR
  EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'internal_admin')
);
```

---

### campaigns — Scoped by client_id

```sql
CREATE POLICY "client_user_read_own_campaigns"
ON campaigns FOR SELECT
USING (
  client_id = (SELECT client_id FROM users WHERE id = auth.uid())
  OR
  EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'internal_admin')
);
```

> Apply same pattern to `ad_accounts`, `ad_sets`, `ads`, `meta_business_managers`.

---

### commission_rules — Internal only

```sql
-- Clients cannot see commission rules at all
CREATE POLICY "internal_admin_only_commission_rules"
ON commission_rules FOR ALL
USING (
  EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'internal_admin')
);
```

---

### sync_logs — Internal only

```sql
CREATE POLICY "internal_admin_only_sync_logs"
ON sync_logs FOR ALL
USING (
  EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'internal_admin')
);
```

---

## 7. Commission Engine

### Rules

- Commission rate is stored as a decimal: `0.20` = 20% markup
- Formula: `marked_spend = raw_spend * (1 + rate)`
- Rate is date-ranged. The correct rate for a given day is determined by `effective_from` and `effective_to`
- If no commission rule exists for a client on a given date, the rate defaults to `0` (no markup, raw = marked)
- Commission rules cannot overlap in time for the same client (enforced by DB constraint)

### Server-Side Calculation

```typescript
// lib/commission.ts

export function applyCommission(rawSpend: number, rate: number): number {
  return Math.round(rawSpend * (1 + rate) * 100) / 100;
}

export function getCommissionRate(
  rules: CommissionRule[],
  date: Date
): number {
  const applicable = rules.find(rule => {
    const from = new Date(rule.effective_from);
    const to = rule.effective_to ? new Date(rule.effective_to) : null;
    return date >= from && (to === null || date < to);
  });
  return applicable?.rate ?? 0;
}
```

### CRUD Rules

- Only `internal_admin` users can create, update, or delete commission rules
- Rules cannot be backdated more than 90 days (enforced at API layer)
- Deleting a rule is a soft delete — it sets `effective_to` to today, it does not remove the row
- Historical spend figures are always calculated using the rate that was active on that date

---

## 8. Meta Sync Service

### Schedule

The sync runs on a cron schedule via Supabase Edge Functions:
- **Account structure sync:** Every 12 hours (Business Managers, Ad Accounts, Campaigns, Ad Sets, Ads)
- **Performance data sync:** Every 6 hours (daily_stats)

### Sync Order

Account structure must be synced top-down due to foreign key constraints:

```
1. Business Managers
2. Ad Accounts (requires Business Manager)
3. Campaigns (requires Ad Account)
4. Ad Sets (requires Campaign)
5. Ads (requires Ad Set)
6. Daily Stats (requires all above)
```

### Sync Logic

```typescript
// supabase/functions/meta-sync/index.ts

// For each client with a connected Business Manager:
// 1. Pull account structure from Meta Ads MCP
// 2. Upsert records using ON CONFLICT (meta_*_id) DO UPDATE
// 3. Pull daily stats for date range (yesterday + last 7 days for corrections)
// 4. Upsert daily_stats — Meta sometimes corrects historical figures
// 5. Write sync_log record with status and record count

const upsertCampaign = async (campaign: MetaCampaign, clientId: string) => {
  const { error } = await supabase
    .from('campaigns')
    .upsert({
      meta_campaign_id: campaign.id,
      client_id: clientId,
      name: campaign.name,
      status: campaign.status,
      objective: campaign.objective,
      daily_budget: campaign.daily_budget,
      lifetime_budget: campaign.lifetime_budget,
      synced_at: new Date().toISOString(),
    }, {
      onConflict: 'meta_campaign_id'
    });

  if (error) throw error;
};
```

### Error Handling

- If a sync fails partway through, the `sync_logs` record is marked `partial`
- Existing data is not deleted on failure — the last successful sync data remains
- Failed syncs trigger a visible warning in the internal admin UI
- Sync errors are logged with full error message in `sync_logs.error_message`

### Rate Limiting

Meta Ads API has rate limits. The sync service must:
- Batch requests where the API supports it
- Add 200ms delay between sequential entity fetches
- Respect `Retry-After` headers on 429 responses
- Never run two sync jobs simultaneously (use Supabase Edge Function single-instance guarantee)

---

## 9. Authentication & Access Control

### Auth Provider

Supabase Auth. Email + password only for the initial build.

### JWT Claims

On sign-in, a custom JWT claim is added via a Supabase Auth Hook:

```sql
-- Function to add role and client_id to JWT
CREATE OR REPLACE FUNCTION add_user_claims(event JSONB)
RETURNS JSONB AS $$
DECLARE
  user_record RECORD;
BEGIN
  SELECT role, client_id INTO user_record
  FROM users WHERE id = (event->>'user_id')::UUID;

  event := jsonb_set(event, '{claims,role}', to_jsonb(user_record.role));
  event := jsonb_set(event, '{claims,client_id}', to_jsonb(user_record.client_id::TEXT));

  RETURN event;
END;
$$ LANGUAGE plpgsql;
```

### Session Rules

- Sessions expire after 8 hours of inactivity
- Refresh tokens are valid for 30 days
- All API routes validate the JWT on every request — no exceptions
- The `role` claim in the JWT determines which data is accessible

### Access Matrix

| Resource | `internal_admin` | `client_user` |
|---|---|---|
| `raw_spend` | ✅ Read | ❌ Blocked at DB level |
| `marked_spend` | ✅ Read | ✅ Read (own client only) |
| `commission_rules` | ✅ Full CRUD | ❌ Blocked at DB level |
| `campaigns` (all clients) | ✅ Read | ❌ Blocked |
| `campaigns` (own client) | ✅ Read | ✅ Read |
| `sync_logs` | ✅ Read | ❌ Blocked |
| `clients` (all) | ✅ Full CRUD | ❌ Blocked |
| `clients` (own) | ✅ Full CRUD | ✅ Read only |
| `users` (all) | ✅ Full CRUD | ❌ Blocked |
| `users` (own account) | ✅ Full CRUD | ✅ Edit own profile |

---

## 10. Client Portal

### Routes

```
/login                          — Auth page
/dashboard                      — Spend overview, key metrics
/campaigns                      — Campaign list with performance table
/campaigns/[id]                 — Campaign detail with ad set breakdown
/campaigns/[id]/adsets/[id]     — Ad set detail with ad breakdown
/reports                        — Date-range reports, export
/settings                       — User profile, password change
```

### Dashboard Components

**Spend Overview Card**
- Shows `marked_spend` for current month, previous month, and % change
- Source: `client_spend_view` grouped by month

**Pacing Chart**
- Daily spend vs. daily budget target
- Recharts `AreaChart` with a reference line at the daily budget
- If spend is below pacing, reference line is amber. If on track, green.

**Campaign Performance Table**
- Columns: Campaign Name, Status, Spend (marked), Impressions, Clicks, CTR, CPC, Conversions
- Sortable by any column
- Links to campaign detail page

**Trend Chart**
- 30-day spend trend
- Recharts `LineChart`
- One line per active campaign (max 5, others grouped as "Other")

**Key Metrics Row**
- Total Spend (marked), Total Impressions, Total Clicks, Average CTR, Total Conversions

### Data Rules for Client Portal

- Every API call to `/api/client/*` queries `client_spend_view` only
- No route handler in `/api/client/*` ever imports from a path that touches `daily_stats` directly
- TypeScript types for client API responses never include a `raw_spend` field
- All spend figures are rounded to 2 decimal places before sending to the browser

---

## 11. Internal Admin Tool

### Routes

```
/admin                                    — Overview dashboard
/admin/clients                            — Client list
/admin/clients/[id]                       — Client detail, users, commission rules
/admin/clients/[id]/commission            — Commission rule CRUD
/admin/business-managers                  — BM overview
/admin/business-managers/[id]             — BM detail + ad accounts
/admin/ad-accounts/[id]                   — Ad account + campaigns
/admin/campaigns/[id]                     — Campaign + ad sets
/admin/sync                               — Sync status, logs, manual trigger
/admin/users                              — User management
```

### Commission Rule Management UI

- List all rules for a client with date ranges
- Form to create a new rule: client, rate (%), effective from, note
- Edit: only `rate` and `note` can be edited. Dates are immutable once created.
- Delete: sets `effective_to = today`. Does not hard-delete.
- Validation: rate must be between 0% and 1000%. Overlapping date ranges are rejected.

### Sync Dashboard

- Table of recent `sync_logs` with status badges
- Manual sync trigger button (calls the Edge Function directly)
- Last sync time per client
- Failed sync count in last 24 hours

---

## 12. API Design

### Client-Facing Routes

All client routes are under `/app/api/client/` and require a valid JWT with `role = 'client_user'`.

```
GET /api/client/dashboard/summary
GET /api/client/dashboard/spend-trend?days=30
GET /api/client/campaigns
GET /api/client/campaigns/[id]
GET /api/client/campaigns/[id]/adsets
GET /api/client/adsets/[id]/ads
GET /api/client/reports?from=YYYY-MM-DD&to=YYYY-MM-DD
```

### Internal Admin Routes

All admin routes are under `/app/api/admin/` and require `role = 'internal_admin'`.

```
GET    /api/admin/clients
POST   /api/admin/clients
GET    /api/admin/clients/[id]
PATCH  /api/admin/clients/[id]

GET    /api/admin/clients/[id]/commission
POST   /api/admin/clients/[id]/commission
PATCH  /api/admin/commission/[ruleId]
DELETE /api/admin/commission/[ruleId]

GET    /api/admin/sync/logs
POST   /api/admin/sync/trigger

GET    /api/admin/users
POST   /api/admin/users
PATCH  /api/admin/users/[id]
DELETE /api/admin/users/[id]
```

### Response Shape Rules

Client API responses must conform to this TypeScript interface — note the complete absence of `raw_spend`:

```typescript
interface ClientSpendRecord {
  id: string;
  stat_date: string;
  spend: number;          // marked_spend — NEVER raw_spend
  impressions: number;
  clicks: number;
  reach: number;
  conversions: number;
  cpm: number;
  cpc: number;
  ctr: number;
}
```

Internal API responses for spend records:

```typescript
interface AdminSpendRecord extends ClientSpendRecord {
  raw_spend: number;      // Only present in admin responses
  commission_rate: number;
  commission_amount: number;
}
```

---

## 13. Security Rules

### Absolute Rules — Cannot Be Overridden

1. `raw_spend` is never returned in any response to a client session, under any circumstances, including error responses, debug responses, or partial responses.

2. Client users are never granted direct SELECT permission on `daily_stats`. They access spend data exclusively through `client_spend_view`.

3. Commission rules are never visible to client users. Not the rate, not the existence of rules.

4. All API routes validate the JWT before processing the request. There are no public routes that return spend or campaign data.

5. The `service_role` Supabase key is never exposed to the browser. It is only used in Edge Functions and server-side Next.js code.

### Code Review Checklist for Any PR

Before merging any code change, verify:

- [ ] No `raw_spend` field in any client-facing TypeScript type
- [ ] No direct query to `daily_stats` in any `/api/client/*` route
- [ ] No commission rate or rule data returned to any client session
- [ ] All new tables have RLS enabled with a default-deny posture
- [ ] No Supabase `service_role` key used in browser-executed code
- [ ] All spend figures rounded to 2dp before API response

---

## 14. Environment Variables

### Required — All Environments

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=        # Server-side only — never expose to browser

# Meta
META_ADS_ACCESS_TOKEN=
META_APP_ID=
META_APP_SECRET=

# App
NEXT_PUBLIC_APP_URL=
NEXTAUTH_SECRET=
```

### Required — Production Only

```bash
# Vercel
VERCEL_ENV=production

# Cron auth (protects sync trigger endpoint)
SYNC_CRON_SECRET=

# Optional: error tracking
SENTRY_DSN=
```

### Variable Rules

- `SUPABASE_SERVICE_ROLE_KEY` must never appear in any `NEXT_PUBLIC_*` variable
- `META_ADS_ACCESS_TOKEN` must never be exposed to browser-side code
- All secrets must be set in Vercel's environment variable dashboard, not in `.env` files committed to the repository
- `.env.local` is gitignored. A `.env.example` with placeholder values is committed.

---

## 15. Deployment

### Vercel Configuration

```json
// vercel.json
{
  "crons": [
    {
      "path": "/api/cron/sync",
      "schedule": "0 */6 * * *"
    }
  ]
}
```

### Deployment Checklist

**Before first deploy:**
- [ ] Supabase project created and migrations run
- [ ] All environment variables set in Vercel
- [ ] RLS policies verified with test accounts (see Security section)
- [ ] At least one `internal_admin` user created in `users` table
- [ ] At least one test client with commission rule created
- [ ] Meta access token scoped correctly (ads_read permission minimum)

**Every deploy:**
- [ ] Run `supabase db push` to apply any new migrations
- [ ] Verify sync function is accessible after deploy
- [ ] Smoke test: log in as a test client user and confirm no `raw_spend` in network responses

### Environments

| Environment | URL | Supabase Project |
|---|---|---|
| Production | `https://app.yourdomain.com` | `prod-project` |
| Staging | `https://staging.yourdomain.com` | `staging-project` |
| Local | `http://localhost:3000` | Local Supabase |

---

## 16. Build Phases & Timeline

### Phase 1 — Supabase Schema + RLS (Day 1, Morning)

**Deliverables:**
- All migration files written and applied
- All RLS policies active
- `client_spend_view` created
- Seed data: 1 internal admin, 2 test clients, mock daily_stats

**Done when:** A `client_user` session cannot access `raw_spend` through any query path.

---

### Phase 2 — Meta Sync Service (Day 1, Afternoon)

**Deliverables:**
- Edge Function that pulls account structure from Meta Ads MCP
- Edge Function that pulls daily stats
- Both functions write clean data to Supabase
- `sync_logs` populated on each run
- Cron schedule configured

**Done when:** Running the sync function populates campaigns, ad sets, ads, and daily_stats for at least one real ad account.

---

### Phase 3 — Commission Engine (Day 1, Afternoon)

**Deliverables:**
- `commission_rules` CRUD API routes (admin only)
- `client_spend_view` verified to apply correct rate per date
- TypeScript commission utility functions

**Done when:** Changing a commission rule for a test client changes the `spend` value returned by `client_spend_view` for the correct date range.

---

### Phase 4 — Client Portal Auth + Access Control (Day 1, Evening)

**Deliverables:**
- Login page
- Supabase Auth integration with custom JWT claims
- Middleware that protects all `/dashboard/*` and `/api/client/*` routes
- Role-based redirect: client_user -> `/dashboard`, internal_admin -> `/admin`

**Done when:** A client user cannot access any admin route or any other client's data.

---

### Phase 5 — Client Portal UI (Day 2, Morning)

**Deliverables:**
- Dashboard with spend overview, pacing chart, trend chart, key metrics
- Campaign list page
- Campaign detail + ad set breakdown
- All spend figures showing `marked_spend` from `client_spend_view`
- Recharts visualisations for all charts

**Done when:** A client user sees their own campaign performance with marked spend figures.

---

### Phase 6 — Internal Admin Tool (Day 2, Afternoon)

**Deliverables:**
- Full Meta account tree (BM -> Accounts -> Campaigns -> Ad Sets -> Ads)
- Client management (create, edit, archive)
- User management (create, assign to client, deactivate)
- Commission rule CRUD UI
- Sync status dashboard with manual trigger

**Done when:** An internal admin can manage all clients, view raw + marked spend, and modify commission rules.

---

### Phase 7 — Deployment + Docs + Handoff (Day 2, Evening)

**Deliverables:**
- Production deploy to Vercel
- All environment variables documented
- Sync setup instructions
- This constitution document reviewed and finalised
- Handoff notes written

---

## 17. Handoff & Maintenance

### Ongoing Sync Monitoring

Check `sync_logs` weekly for failed or partial syncs. If `status = 'failed'` appears more than twice in a week for the same client, investigate the Meta access token for that client — tokens expire.

### Adding a New Client

1. Create record in `clients` table
2. Create user records in `users` table with `role = 'client_user'` and correct `client_id`
3. Link their Meta Business Manager ID in `meta_business_managers`
4. Create a commission rule in `commission_rules` with their rate and start date
5. Trigger a manual sync from the admin UI
6. Verify their data appears correctly in the client portal

### Rotating Meta Access Tokens

Meta access tokens expire. When rotating:
1. Update `META_ADS_ACCESS_TOKEN` in Vercel environment variables
2. Redeploy (or trigger a redeployment to pick up the new variable)
3. Run a manual sync to verify the new token works

### Schema Changes

All schema changes must:
1. Be written as Supabase migration files (never edited directly in the dashboard in production)
2. Include the corresponding RLS policy changes if new tables are added
3. Be tested against the `client_spend_view` to confirm no `raw_spend` leaks are introduced

---

## Appendix A — Commission Security Verification Procedure

Run this procedure before giving any client access to the portal.

```sql
-- Step 1: Impersonate a client user (replace with real user JWT)
-- In Supabase SQL editor, set role to the client user

SET LOCAL ROLE authenticated;
SET LOCAL "request.jwt.claims" TO '{"sub": "<client_user_uuid>", "role": "client_user"}';

-- Step 2: Try to read raw_spend directly — must return 0 rows
SELECT raw_spend FROM daily_stats LIMIT 1;
-- Expected: 0 rows (RLS blocks this)

-- Step 3: Try to read commission_rules — must return 0 rows
SELECT * FROM commission_rules LIMIT 1;
-- Expected: 0 rows (RLS blocks this)

-- Step 4: Read from client_spend_view — must return only marked spend
SELECT * FROM client_spend_view LIMIT 5;
-- Expected: rows with 'spend' column only, no raw_spend column

-- Step 5: Try to access another client's data
-- Set client_id in JWT to Client A, then query campaigns where client_id = Client B
SELECT * FROM campaigns WHERE client_id = '<client_b_uuid>' LIMIT 1;
-- Expected: 0 rows (RLS blocks cross-client access)
```

All five checks must pass before the platform is considered ready for client access.

---

*End of Constitution — Version 1.0*
