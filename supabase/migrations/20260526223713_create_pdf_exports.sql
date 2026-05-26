-- Tracks each PDF download. Separate from evaluations because
-- a user can regenerate/download multiple PDFs from one evaluation.
create table if not exists pdf_exports (
  id             uuid primary key default gen_random_uuid(),
  evaluation_id  uuid not null references evaluations(id) on delete cascade,
  user_id        uuid not null references auth.users(id) on delete cascade,
  created_at     timestamptz not null default now()
);

alter table pdf_exports enable row level security;

create policy "users manage own pdf exports"
  on pdf_exports for all
  using  (auth.uid() = user_id)
  with check (auth.uid() = user_id);