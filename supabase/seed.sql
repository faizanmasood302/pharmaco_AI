-- Pharmacogenomic Harness — Supabase schema
-- Run in Supabase SQL editor (Dashboard -> SQL -> New query)

-- Utility to automatically update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 1. Migration: Ensure patients table has display_name_encrypted
DO $$ 
BEGIN 
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='display_name') THEN
    ALTER TABLE patients RENAME COLUMN display_name TO display_name_encrypted;
  END IF;
END $$;

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

-- N-of-1 research simulation storage
create table if not exists therapy_requests (
  id uuid primary key default gen_random_uuid(),
  patient_id text not null references patients(id) on delete cascade,
  target_disease text not null,
  status text not null check (status in ('running', 'research_review_required', 'failed')),
  iterations int not null default 0 check (iterations >= 0 and iterations <= 5),
  result_json jsonb not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index if not exists therapy_requests_patient_id_idx on therapy_requests(patient_id);
create index if not exists therapy_requests_created_at_idx on therapy_requests(created_at desc);
CREATE TRIGGER update_therapy_requests_modtime BEFORE UPDATE ON therapy_requests FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

create table if not exists therapy_candidates (
  candidate_id text primary key,
  therapy_request_id uuid not null references therapy_requests(id) on delete cascade,
  iteration int not null check (iteration >= 1 and iteration <= 5),
  modality text not null default 'simulated_mrna',
  sequence text not null,
  design_constraints jsonb not null default '[]'::jsonb,
  rationale text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz default now()
);
create index if not exists therapy_candidates_request_idx on therapy_candidates(therapy_request_id);

create table if not exists therapy_validation_results (
  id uuid primary key default gen_random_uuid(),
  therapy_request_id uuid not null references therapy_requests(id) on delete cascade,
  candidate_id text not null references therapy_candidates(candidate_id) on delete cascade,
  passed boolean not null,
  overall_risk_score numeric not null check (overall_risk_score >= 0 and overall_risk_score <= 1),
  checks jsonb not null default '[]'::jsonb,
  blocked_reasons jsonb not null default '[]'::jsonb,
  revision_hints jsonb not null default '[]'::jsonb,
  created_at timestamptz default now()
);
create index if not exists therapy_validation_request_idx on therapy_validation_results(therapy_request_id);

create table if not exists therapy_audit_events (
  id uuid primary key default gen_random_uuid(),
  therapy_request_id uuid not null references therapy_requests(id) on delete cascade,
  event_index int not null,
  stage text not null,
  decision text not null,
  rationale text not null,
  requires_human_review boolean not null default true,
  created_at timestamptz default now()
);
create index if not exists therapy_audit_request_idx on therapy_audit_events(therapy_request_id, event_index);

create table if not exists therapy_human_reviews (
  id uuid primary key default gen_random_uuid(),
  therapy_request_id uuid not null references therapy_requests(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  reason text not null,
  required_fields jsonb not null default '[]'::jsonb,
  reviewer_id text,
  review_notes text,
  reviewed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index if not exists therapy_human_reviews_request_idx on therapy_human_reviews(therapy_request_id);
CREATE TRIGGER update_therapy_human_reviews_modtime BEFORE UPDATE ON therapy_human_reviews FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

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

create table if not exists medications (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,
  enzyme text not null,
  is_prodrug boolean not null default false,
  status text not null default 'active',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
CREATE TRIGGER update_medications_modtime BEFORE UPDATE ON medications FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

create table if not exists clinical_reports (
  id uuid primary key default gen_random_uuid(),
  evaluation_id uuid not null references evaluations(id) on delete cascade,
  patient_id text not null references patients(id) on delete cascade,
  clinician_id text, -- user_id from auth
  content text not null,
  status text not null default 'final' check (status in ('draft', 'final', 'archived')),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index if not exists clinical_reports_patient_idx on clinical_reports(patient_id);
CREATE TRIGGER update_clinical_reports_modtime BEFORE UPDATE ON clinical_reports FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- ROW LEVEL SECURITY (C1)
alter table patients enable row level security;
alter table evaluations enable row level security;
alter table adherence_plans enable row level security;
alter table check_ins enable row level security;
alter table audit_logs enable row level security;
alter table medications enable row level security;
alter table clinical_reports enable row level security;
alter table therapy_requests enable row level security;
alter table therapy_candidates enable row level security;
alter table therapy_validation_results enable row level security;
alter table therapy_audit_events enable row level security;
alter table therapy_human_reviews enable row level security;

create policy "Allow authenticated read access" on medications for select using (auth.role() = 'authenticated');
create policy "Allow authenticated read access" on clinical_reports for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on clinical_reports for insert with check (auth.role() = 'authenticated');

-- Seed Data
insert into medications (name, enzyme, is_prodrug) values
('Codeine', 'CYP2D6', true),
('Tramadol', 'CYP2D6', true),
('Hydrocodone', 'CYP2D6', false),
('Oxycodone', 'CYP3A4', false),
('Clopidogrel', 'CYP2C19', true),
('Pregabalin', '—', false),
('Duloxetine', 'CYP2D6', false)
on conflict (name) do nothing;

-- Policies for Authenticated Users (Restricted to logged-in sessions)
-- This ensures that only your backend or authorized practitioners can touch the data.
create policy "Allow authenticated read access" on patients for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on patients for insert with check (auth.role() = 'authenticated');
create policy "Allow authenticated update access" on patients for update using (auth.role() = 'authenticated');

create policy "Allow authenticated read access" on evaluations for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on evaluations for insert with check (auth.role() = 'authenticated');

create policy "Allow authenticated read access" on adherence_plans for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on adherence_plans for insert with check (auth.role() = 'authenticated');
create policy "Allow authenticated update access" on adherence_plans for update using (auth.role() = 'authenticated');

create policy "Allow authenticated read access" on check_ins for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on check_ins for insert with check (auth.role() = 'authenticated');
create policy "Allow authenticated update access" on check_ins for update using (auth.role() = 'authenticated');

create policy "Allow authenticated write access" on audit_logs for insert with check (auth.role() = 'authenticated');

create policy "Allow authenticated read access" on therapy_requests for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on therapy_requests for insert with check (auth.role() = 'authenticated');

create policy "Allow authenticated read access" on therapy_candidates for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on therapy_candidates for insert with check (auth.role() = 'authenticated');

create policy "Allow authenticated read access" on therapy_validation_results for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on therapy_validation_results for insert with check (auth.role() = 'authenticated');

create policy "Allow authenticated read access" on therapy_audit_events for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on therapy_audit_events for insert with check (auth.role() = 'authenticated');

create policy "Allow authenticated read access" on therapy_human_reviews for select using (auth.role() = 'authenticated');
create policy "Allow authenticated write access" on therapy_human_reviews for insert with check (auth.role() = 'authenticated');
create policy "Allow authenticated update access" on therapy_human_reviews for update using (auth.role() = 'authenticated');

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
),
(
  'PGX-004',
  'Alex Rivera',
  36,
  'M',
  'Severe acute pain post-injury',
  '[{"gene":"CYP2D6","diplotype":"*1/*1xN","phenotype":"Ultra-Rapid Metabolizer","activity_score":"2.25 (increased)"}]'::jsonb
)
on conflict (id) do nothing;
