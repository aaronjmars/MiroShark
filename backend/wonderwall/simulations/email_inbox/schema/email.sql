-- Email inbox simulation schema
-- Tracks email variants and per-agent inbox state for copy variant testing.

-- Email copy variants under test
CREATE TABLE IF NOT EXISTS email_variant (
    variant_id   INTEGER PRIMARY KEY,
    variant_label TEXT NOT NULL,       -- e.g. "Variant A — Timeline Hook"
    subject_line TEXT NOT NULL,
    body         TEXT NOT NULL,
    hook_type    TEXT DEFAULT 'unknown', -- timeline, problem, numbers, social_proof, curiosity
    created_at   TEXT NOT NULL
);

-- Per-agent state per variant across all rounds
-- One row per (agent_id, variant_id) — updated in place as rounds progress
CREATE TABLE IF NOT EXISTS agent_inbox_state (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id            INTEGER NOT NULL,
    variant_id          INTEGER NOT NULL,
    -- Cumulative boolean flags (0/1) — set to 1 once triggered, never reversed
    opened              INTEGER NOT NULL DEFAULT 0,
    read_to_completion  INTEGER NOT NULL DEFAULT 0,
    replied             INTEGER NOT NULL DEFAULT 0,
    forwarded           INTEGER NOT NULL DEFAULT 0,
    -- Where the agent dropped off (NULL = completed or not yet decided)
    dropout_point       TEXT,  -- 'subject_line' | 'opening' | 'body' | 'cta' | NULL
    -- Accumulated reply intent score (0.0–1.0), updated each active round
    reply_intent_score  REAL NOT NULL DEFAULT 0.0,
    last_round          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,
    UNIQUE(agent_id, variant_id)
);

-- Append-only event log for every inbox interaction
CREATE TABLE IF NOT EXISTS inbox_event (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id     INTEGER NOT NULL,
    variant_id   INTEGER NOT NULL,
    round_num    INTEGER NOT NULL,
    -- Action taken: open_email | read_email | reply | forward | archive | do_nothing
    event_type   TEXT NOT NULL,
    dropout_point TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL
);
