-- BoardMD Leaderboard Table
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS leaderboard (
  user_id    UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  name       TEXT NOT NULL DEFAULT 'Student',
  univ       TEXT DEFAULT '',
  country    TEXT DEFAULT '',
  step       TEXT DEFAULT 's2',
  coins      INTEGER DEFAULT 0,
  streak     INTEGER DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for ranking queries
CREATE INDEX IF NOT EXISTS idx_leaderboard_coins ON leaderboard (coins DESC);
CREATE INDEX IF NOT EXISTS idx_leaderboard_country ON leaderboard (country);
CREATE INDEX IF NOT EXISTS idx_leaderboard_step ON leaderboard (step);

-- RLS: anyone can read, only own row can write
ALTER TABLE leaderboard ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read" ON leaderboard FOR SELECT USING (true);
CREATE POLICY "Own row insert" ON leaderboard FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Own row update" ON leaderboard FOR UPDATE USING (auth.uid() = user_id);
