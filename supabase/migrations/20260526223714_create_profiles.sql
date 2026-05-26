-- User identity snapshot, auto-populated on signup via trigger.
-- Makes it easy to identify users in the dashboard (e.g. to set bypass_limit).
create table if not exists profiles (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  email      text,
  full_name  text,
  avatar_url text,
  created_at timestamptz not null default now()
);

alter table profiles enable row level security;

-- Users can read their own profile; service role (admin) can read all.
create policy "users read own profile"
  on profiles for select
  using (auth.uid() = user_id);

-- Trigger function: runs on every new auth.users row.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (user_id, email, full_name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    new.raw_user_meta_data->>'avatar_url'
  )
  on conflict (user_id) do nothing;
  return new;
end;
$$;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();