-- Tracks free-tier usage per authenticated user.
-- One row per user; upserted on each analysis run.
create table if not exists user_usage (
  user_id               uuid primary key references auth.users(id) on delete cascade,
  free_analyses_used    int  not null default 0,
  updated_at            timestamptz not null default now()
);

-- Users can only read/write their own row.
alter table user_usage enable row level security;

create policy "users manage own usage"
  on user_usage for all
  using  (auth.uid() = user_id)
  with check (auth.uid() = user_id);