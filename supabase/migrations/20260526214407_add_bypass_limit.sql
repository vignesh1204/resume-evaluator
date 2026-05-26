-- Add bypass_limit column so specific users can run unlimited analyses.
-- Only settable by admin via Supabase dashboard / service role — not by users themselves.
alter table user_usage add column if not exists bypass_limit boolean not null default false;

-- Replace the broad "all" policy with separate policies so users cannot
-- update bypass_limit on their own row.
drop policy if exists "users manage own usage" on user_usage;

-- Users can read their own row (including bypass_limit so the frontend can check it).
create policy "users read own usage"
  on user_usage for select
  using (auth.uid() = user_id);

-- Users can insert their own row (bypass_limit will always default to false).
create policy "users insert own usage"
  on user_usage for insert
  with check (auth.uid() = user_id AND bypass_limit = false);

-- Users can update their own row but cannot change bypass_limit.
create policy "users update own usage"
  on user_usage for update
  using (auth.uid() = user_id)
  with check (
    auth.uid() = user_id
    AND bypass_limit = (select bypass_limit from user_usage where user_id = auth.uid())
  );