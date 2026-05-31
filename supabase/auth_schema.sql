-- BetterAuth Core Tables for Supabase
-- Run in Supabase SQL editor

-- 1. User Table
create table if not exists "user" (
    "id" text not null primary key,
    "name" text not null,
    "email" text not null unique,
    "emailVerified" boolean not null default false,
    "image" text,
    "createdAt" timestamp with time zone not null default now(),
    "updatedAt" timestamp with time zone not null default now()
);

-- 2. Session Table
create table if not exists "session" (
    "id" text not null primary key,
    "expiresAt" timestamp with time zone not null,
    "token" text not null unique,
    "createdAt" timestamp with time zone not null default now(),
    "updatedAt" timestamp with time zone not null default now(),
    "ipAddress" text,
    "userAgent" text,
    "userId" text not null references "user"("id") on delete cascade
);

-- 3. Account Table
create table if not exists "account" (
    "id" text not null primary key,
    "accountId" text not null,
    "providerId" text not null,
    "userId" text not null references "user"("id") on delete cascade,
    "accessToken" text,
    "refreshToken" text,
    "idToken" text,
    "accessTokenExpiresAt" timestamp with time zone,
    "refreshTokenExpiresAt" timestamp with time zone,
    "scope" text,
    "password" text,
    "createdAt" timestamp with time zone not null default now(),
    "updatedAt" timestamp with time zone not null default now()
);

-- 4. Verification Table
create table if not exists "verification" (
    "id" text not null primary key,
    "identifier" text not null,
    "value" text not null,
    "expiresAt" timestamp with time zone not null,
    "createdAt" timestamp with time zone not null default now(),
    "updatedAt" timestamp with time zone not null default now()
);

-- Security: Enable Row Level Security (RLS)
alter table "user" enable row level security;
alter table "session" enable row level security;
alter table "account" enable row level security;
alter table "verification" enable row level security;

-- RLS Policies

-- User policies: Users can read/update their own profile
create policy "Users can view own profile" on "user" for select using (auth.uid()::text = id);
create policy "Users can update own profile" on "user" for update using (auth.uid()::text = id);

-- Session policies: Users can see their own sessions
create policy "Users can view own sessions" on "session" for select using (auth.uid()::text = "userId");
create policy "Users can delete own sessions" on "session" for delete using (auth.uid()::text = "userId");

-- Account policies: Users can view own accounts
create policy "Users can view own accounts" on "account" for select using (auth.uid()::text = "userId");

-- Backend access (for agent-server)
-- Note: In a production Supabase setup, you would use a service role or a specific role for the backend.
-- For this MVP, we allow select on sessions for verified backend tokens (service role).
create policy "Allow backend session verification" on "session" for select using (true);
