-- Pharmacogenomic Harness — Supabase schema
-- Run in Supabase SQL editor (Dashboard → SQL → New query)

-- Utility to automatically update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

create table if not exists patients (
  id text primary key,
  display_name_encrypted text not null, -- Fernet-encrypted Application-side
  age int not null check (age >= 0 and age <= 120),
  sex text not null check (sex in ('M', 'F', 'O', 'U')),
  indication text not null,
  cyp_profiles jsonb not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
CREATE TRIGGER update_patients_modtime BEFORE UPDATE ON patients FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

create table if not exists evaluations (
  id uuid primary key default gen_random_uuid(),
  patient_id text not null references patients(id) on delete cascade,
  medication text not null,
  flagged boolean not null default false,
  risk_level text not null check (risk_level in ('none', 'low', 'moderate', 'high', 'critical')),
  result_json jsonb not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index if not exists evaluations_patient_id_idx on evaluations(patient_id);
create index if not exists evaluations_created_at_idx on evaluations(created_at desc);
CREATE TRIGGER update_evaluations_modtime BEFORE UPDATE ON evaluations FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

create table if not exists adherence_plans (
  id uuid primary key default gen_random_uuid(),
  patient_id text not null references patients(id) on delete cascade,
  medication text not null,
  evaluation_id uuid references evaluations(id) on delete set null,
  status text not null default 'active' check (status in ('active', 'completed', 'cancelled')),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
CREATE TRIGGER update_adherence_plans_modtime BEFORE UPDATE ON adherence_plans FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

create table if not exists check_ins (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references adherence_plans(id) on delete cascade,
  day_offset int not null,
  prompt text not null,
  status text not null default 'pending' check (status in ('pending', 'completed', 'skipped')),
  response text,
  side_effect_reported boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
CREATE TRIGGER update_check_ins_modtime BEFORE UPDATE ON check_ins FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- Fix #2: Audit Logging Table
create table if not exists audit_logs (
  id uuid primary key default gen_random_uuid(),
  user_id varchar(255) not null,
  action varchar(50) not null,
  patient_id varchar(20),
  resource_id varchar(255),
  details jsonb,
  timestamp timestamp with time zone default now(),
  ip_address inet,
  user_agent text
);

create index if not exists idx_audit_user_id on audit_logs(user_id);
create index if not exists idx_audit_patient_id on audit_logs(patient_id);
create index if not exists idx_audit_timestamp on audit_logs(timestamp);

-- ROW LEVEL SECURITY (C1)
alter table patients enable row level security;
alter table evaluations enable row level security;
alter table adherence_plans enable row level security;
alter table check_ins enable row level security;
alter table audit_logs enable row level security;

-- Policies for Authenticated Users (simple service role access for backend)
create policy "Allow backend read access" on patients for select using (true);
create policy "Allow backend write access" on patients for insert with check (true);
create policy "Allow backend update access" on patients for update using (true);

create policy "Allow backend read access" on evaluations for select using (true);
create policy "Allow backend write access" on evaluations for insert with check (true);

create policy "Allow backend read access" on adherence_plans for select using (true);
create policy "Allow backend write access" on adherence_plans for insert with check (true);
create policy "Allow backend update access" on adherence_plans for update using (true);

create policy "Allow backend read access" on check_ins for select using (true);
create policy "Allow backend write access" on check_ins for insert with check (true);
create policy "Allow backend update access" on check_ins for update using (true);

create policy "Allow backend write access" on audit_logs for insert with check (true);

-- Seed Data
insert into patients (id, display_name_encrypted, age, sex, indication, cyp_profiles) values
(
  'PGX-001',
  'Maria Chen',
  42,
  'F',
  'Chronic neuropathic pain (lumbar radiculopathy)',
  '[{"gene":"CYP2D6","diplotype":"*1/*1xN","phenotype":"Ultra-Rapid Metabolizer","activity_score":"2.25 (increased)"}]'::jsonb
),
(
  'PGX-002',
  'James Okonkwo',
  58,
  'M',
  'Severe osteoarthritis (bilateral knees)',
  '[{"gene":"CYP2D6","diplotype":"*4/*4","phenotype":"Poor Metabolizer","activity_score":"0.0 (no function)"}]'::jsonb
),
(
  'PGX-003',
  'Sarah Patel',
  35,
  'F',
  'Post-surgical acute pain (day 5)',
  '[{"gene":"CYP2D6","diplotype":"*1/*2","phenotype":"Normal Metabolizer","activity_score":"1.5 (normal)"}]'::jsonb
)
on conflict (id) do nothing;
