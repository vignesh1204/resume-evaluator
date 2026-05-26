-- Core history table. One row per analysis run.
create table if not exists evaluations (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references auth.users(id) on delete cascade,
  created_at           timestamptz not null default now(),

  -- Scalar fields for quick display without parsing JSON
  resume_file_name     text,
  job_description      text,
  model                text,
  mode                 text,
  original_ats_score   int,
  optimized_ats_score  int,
  estimated_cost_usd   numeric(10, 6),
  cache_hit            boolean,

  -- Full analysis blob (original + optimized skeletons, improvements, signals, telemetry)
  analysis             jsonb,

  -- Editor state — updated as user reorders/toggles/edits on PDF page
  editable_skeleton    jsonb,
  section_order        text[],
  enabled_section_ids  text[]
);

alter table evaluations enable row level security;

create policy "users manage own evaluations"
  on evaluations for all
  using  (auth.uid() = user_id)
  with check (auth.uid() = user_id);