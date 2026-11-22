-- Run once in pgAdmin Query Tool against the existing casegraph database.
-- This is additive: it preserves all existing person records.
ALTER TABLE persons ADD COLUMN IF NOT EXISTS gender TEXT;
ALTER TABLE persons ADD COLUMN IF NOT EXISTS photo_path TEXT;

-- Optional validation constraint; blank/NULL gender remains allowed.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'persons_gender_check') THEN
        ALTER TABLE persons ADD CONSTRAINT persons_gender_check CHECK (gender IS NULL OR gender IN ('male', 'female'));
    END IF;
END $$;
