-- ScamShield database schema (PostgreSQL / Supabase)
-- Paste this into Supabase → SQL Editor → Run.
-- (The backend also auto-creates these tables on startup, so this file is mainly for your report.)

create table if not exists model_versions (
    id          serial primary key,
    name        varchar(32)  not null,          -- 'text' or 'url'
    version     varchar(64)  not null,
    metrics     jsonb,                           -- precision / recall / f1 etc.
    created_at  timestamptz  not null default now()
);

create table if not exists analyses (
    id              varchar(36) primary key,     -- uuid
    created_at      timestamptz not null default now(),
    channel         varchar(16) not null default 'web',   -- web | telegram | extension | api
    input_type      varchar(8)  not null,                  -- text | url | image
    redacted_input  text        not null,                  -- PII removed before saving
    verdict         varchar(12) not null,                  -- scam | suspicious | safe
    risk_score      real        not null,
    text_score      real,
    url_score       real,
    reasons         jsonb,
    language        varchar(8),
    model_version   varchar(64)
);
create index if not exists idx_analyses_created on analyses (created_at desc);
create index if not exists idx_analyses_verdict on analyses (verdict);

create table if not exists feedback (
    id             serial primary key,
    analysis_id    varchar(36) not null references analyses(id) on delete cascade,
    is_correct     boolean     not null,
    correct_label  varchar(12),                  -- what the user says it really was
    comment        text,
    created_at     timestamptz not null default now()
);
create index if not exists idx_feedback_analysis on feedback (analysis_id);

-- Useful query for retraining: every analysis the user corrected
-- select a.redacted_input, coalesce(f.correct_label, a.verdict) as label
-- from analyses a join feedback f on f.analysis_id = a.id;
