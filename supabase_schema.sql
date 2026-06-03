-- Market Oracle AI Supabase schema
-- Paste this into Supabase Dashboard -> SQL Editor -> New query -> Run.

create extension if not exists pgcrypto;

create table if not exists public.app_alerts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  read boolean not null default false,
  read_at timestamptz,
  type text not null default 'admin',
  level text not null default 'info',
  symbol text,
  market text,
  action text,
  title text not null,
  body text not null,
  price numeric,
  predicted_close numeric,
  confidence_pct numeric,
  predicted_change_pct numeric,
  source text not null default 'system',
  unique_key text unique,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists app_alerts_created_at_idx
  on public.app_alerts (created_at desc);

create index if not exists app_alerts_read_idx
  on public.app_alerts (read, created_at desc);

create index if not exists app_alerts_symbol_idx
  on public.app_alerts (symbol, created_at desc);

create table if not exists public.update_runs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  reason text not null,
  status text not null,
  started_at timestamptz,
  finished_at timestamptz,
  asset_count integer not null default 0,
  error_count integer not null default 0,
  actionable_count integer not null default 0,
  snapshot_path text,
  error text,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists update_runs_created_at_idx
  on public.update_runs (created_at desc);

create table if not exists public.daily_snapshots (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  reason text,
  started_at timestamptz,
  finished_at timestamptz,
  payload jsonb not null
);

create index if not exists daily_snapshots_created_at_idx
  on public.daily_snapshots (created_at desc);

create table if not exists public.prediction_records (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  unique_key text not null unique,
  prediction_date date not null,
  generated_at timestamptz,
  symbol text not null,
  name text,
  market text,
  action text,
  direction text,
  current_price numeric,
  latest_model_close numeric,
  predicted_close numeric,
  predicted_change_pct numeric,
  confidence_pct numeric,
  model_profile text,
  model_name text,
  target_after_date date,
  target_date date,
  actual_close numeric,
  actual_change_pct numeric,
  actual_direction text,
  direction_correct boolean,
  price_error numeric,
  price_error_pct numeric,
  evaluation_status text not null default 'pending',
  evaluated_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists prediction_records_prediction_date_idx
  on public.prediction_records (prediction_date desc);

create index if not exists prediction_records_symbol_idx
  on public.prediction_records (symbol, prediction_date desc);

create index if not exists prediction_records_status_idx
  on public.prediction_records (evaluation_status, prediction_date desc);

create table if not exists public.market_price_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  unique_key text not null unique,
  captured_at timestamptz not null default now(),
  trading_date date not null,
  event_type text not null,
  event_reason text,
  symbol text not null,
  name text,
  market text,
  price numeric,
  open_price numeric,
  close_price numeric,
  latest_price numeric,
  previous_close numeric,
  day_high numeric,
  day_low numeric,
  currency text,
  source text not null default 'Yahoo Finance via yfinance',
  exchange_timezone text,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists market_price_events_trading_date_idx
  on public.market_price_events (trading_date desc, captured_at desc);

create index if not exists market_price_events_symbol_idx
  on public.market_price_events (symbol, trading_date desc);

create index if not exists market_price_events_event_type_idx
  on public.market_price_events (event_type, trading_date desc);

-- This app uses the Supabase service-role key on the server only.
-- Keep Row Level Security enabled for safety if you later expose client-side reads.
alter table public.app_alerts enable row level security;
alter table public.update_runs enable row level security;
alter table public.daily_snapshots enable row level security;
alter table public.prediction_records enable row level security;
alter table public.market_price_events enable row level security;
