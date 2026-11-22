-- ====================================================================
-- CaseGraph Migration 002: Manual Insights & Official Record Association
-- 100% Additive and Backward-Compatible
-- Target: PostgreSQL 18.4
-- ====================================================================

BEGIN;

-- 1. Canonical insight rules (Case 001 ground truth)
CREATE TABLE IF NOT EXISTS canonical_topic_insights (
    rule_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id integer NOT NULL REFERENCES game_case_config(case_id) ON DELETE RESTRICT,
    topic_id bigint NOT NULL REFERENCES dialogue_topics(topic_id) ON DELETE RESTRICT,
    category varchar(40) NOT NULL CHECK(category IN (
        'contradiction', 'suspicious_timing', 'timeline_inconsistency',
        'relationship', 'physical_evidence', 'motive', 'opportunity',
        'access_location', 'possible_deception'
    )),
    target_clue_id bigint NOT NULL REFERENCES case_clues(clue_id) ON DELETE RESTRICT,
    explanation text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(topic_id, category)
);

-- 2. Player-recognized insights & notes
CREATE TABLE IF NOT EXISTS session_insights (
    insight_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES game_sessions(session_id) ON DELETE CASCADE,
    dialogue_id bigint REFERENCES dialogue_history(dialogue_id) ON DELETE SET NULL,
    person_id integer NOT NULL REFERENCES persons(person_id) ON DELETE RESTRICT,
    topic_id bigint REFERENCES dialogue_topics(topic_id) ON DELETE RESTRICT,
    insight_type varchar(30) NOT NULL DEFAULT 'statement_insight' CHECK(insight_type IN ('statement_insight', 'general_note')),
    category varchar(40) CHECK(category IS NULL OR category IN (
        'contradiction', 'suspicious_timing', 'timeline_inconsistency',
        'relationship', 'physical_evidence', 'motive', 'opportunity',
        'access_location', 'possible_deception'
    )),
    player_notes text NOT NULL DEFAULT '',
    is_valid boolean NOT NULL DEFAULT false,
    matched_clue_id bigint REFERENCES case_clues(clue_id) ON DELETE SET NULL,
    recognized_at timestamptz NOT NULL DEFAULT now(),
    CHECK((insight_type = 'statement_insight' AND category IS NOT NULL) OR (insight_type = 'general_note'))
);

-- 3. Junction: links session to real evidence records in public.evidence
CREATE TABLE IF NOT EXISTS session_evidence_records (
    session_id uuid NOT NULL REFERENCES game_sessions(session_id) ON DELETE CASCADE,
    evidence_id integer NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    clue_id bigint REFERENCES case_clues(clue_id) ON DELETE SET NULL,
    created_from_insight_id bigint REFERENCES session_insights(insight_id) ON DELETE SET NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(session_id, evidence_id)
);

-- 4. Junction: links session to real relationship records in public.person_relationships
CREATE TABLE IF NOT EXISTS session_relationship_records (
    session_id uuid NOT NULL REFERENCES game_sessions(session_id) ON DELETE CASCADE,
    relationship_id integer NOT NULL REFERENCES person_relationships(relationship_id) ON DELETE CASCADE,
    person_id integer NOT NULL REFERENCES persons(person_id) ON DELETE RESTRICT,
    related_person_id integer NOT NULL REFERENCES persons(person_id) ON DELETE RESTRICT,
    relationship_type character varying(50) NOT NULL,
    created_from_insight_id bigint REFERENCES session_insights(insight_id) ON DELETE SET NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(session_id, relationship_id)
);

-- 5. Junction: links session to real timeline records in public.timeline_events
CREATE TABLE IF NOT EXISTS session_timeline_records (
    session_id uuid NOT NULL REFERENCES game_sessions(session_id) ON DELETE CASCADE,
    event_id integer NOT NULL REFERENCES timeline_events(event_id) ON DELETE CASCADE,
    created_from_insight_id bigint REFERENCES session_insights(insight_id) ON DELETE SET NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(session_id, event_id)
);

-- 6. Indexes & duplicate protection constraints
CREATE INDEX IF NOT EXISTS idx_canonical_topic_insights_lookup ON canonical_topic_insights(topic_id, category);
CREATE INDEX IF NOT EXISTS idx_session_insights_session ON session_insights(session_id, recognized_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_insights_topic_cat ON session_insights(session_id, topic_id, category) WHERE topic_id IS NOT NULL AND category IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_insights_dialogue_cat ON session_insights(session_id, dialogue_id, category) WHERE dialogue_id IS NOT NULL AND category IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_evidence_clue ON session_evidence_records(session_id, clue_id) WHERE clue_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_rel_directed ON session_relationship_records(session_id, person_id, related_person_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_session_evidence_records_session ON session_evidence_records(session_id);
CREATE INDEX IF NOT EXISTS idx_session_relationship_records_session ON session_relationship_records(session_id);
CREATE INDEX IF NOT EXISTS idx_session_timeline_records_session ON session_timeline_records(session_id);

-- 7. Explicit validation and seed execution DO block
DO $$
DECLARE
    v_missing_chars text;
    v_missing_topics text;
    v_missing_clues text;
    v_conflicts text;
    v_rule_count integer;
BEGIN
    -- Assert all 9 characters exist in Case 6
    SELECT string_agg(DISTINCT v.character_key, ', ') INTO v_missing_chars
    FROM (VALUES
        ('mira_sen'), ('adrian_cole'), ('nadia_rahman'), ('jonas_reed'),
        ('evelyn_shaw'), ('leila_voss'), ('theo_pike'), ('mara_bell'), ('soren_vale')
    ) AS v(character_key)
    LEFT JOIN case_character_profiles cp ON cp.case_id = 6 AND cp.character_key = v.character_key
    WHERE cp.character_key IS NULL;

    IF v_missing_chars IS NOT NULL THEN
        RAISE EXCEPTION 'Seed verification failed: missing characters in Case 6: %', v_missing_chars;
    END IF;

    -- Assert all 14 dialogue topics exist in Case 6
    SELECT string_agg(v.character_key || '.' || v.topic_key, ', ') INTO v_missing_topics
    FROM (VALUES
        ('mira_sen', 'notebook'), ('mira_sen', 'voss'),
        ('adrian_cole', 'override'), ('adrian_cole', 'motive'),
        ('nadia_rahman', 'transmission'), ('nadia_rahman', 'queue'),
        ('jonas_reed', 'camera'), ('jonas_reed', 'detour'),
        ('evelyn_shaw', 'time'), ('evelyn_shaw', 'report'),
        ('leila_voss', 'message'),
        ('theo_pike', 'hatch'),
        ('mara_bell', 'dispatch'),
        ('soren_vale', 'audit')
    ) AS v(character_key, topic_key)
    JOIN case_character_profiles cp ON cp.case_id = 6 AND cp.character_key = v.character_key
    LEFT JOIN dialogue_topics dt ON dt.case_id = cp.case_id AND dt.person_id = cp.person_id AND dt.topic_key = v.topic_key
    WHERE dt.topic_id IS NULL;

    IF v_missing_topics IS NOT NULL THEN
        RAISE EXCEPTION 'Seed verification failed: missing dialogue topics in Case 6: %', v_missing_topics;
    END IF;

    -- Assert all 9 clues exist in Case 6
    SELECT string_agg(DISTINCT v.clue_key, ', ') INTO v_missing_clues
    FROM (VALUES
        ('C03'), ('C04'), ('C05'), ('C06'), ('C07'), ('C09'), ('C10'), ('C11'), ('C12')
    ) AS v(clue_key)
    LEFT JOIN case_clues cc ON cc.case_id = 6 AND cc.clue_key = v.clue_key
    WHERE cc.clue_id IS NULL;

    IF v_missing_clues IS NOT NULL THEN
        RAISE EXCEPTION 'Seed verification failed: missing clues in Case 6: %', v_missing_clues;
    END IF;

    -- Check for conflicting pre-existing mappings pointing to different clues
    SELECT string_agg(
        'topic ' || dt.topic_id || ' (' || v.character_key || '.' || v.topic_key || ') [' || v.category || 
        ']: existing clue_id ' || cti.target_clue_id || ' vs proposed clue ' || v.clue_key || ' (' || cc.clue_id || ')',
        '; '
    ) INTO v_conflicts
    FROM (VALUES
        ('mira_sen', 'notebook', 'physical_evidence', 'C09', 'Preserved notebook page proving antenna check discrepancies.'),
        ('mira_sen', 'notebook', 'motive', 'C09', 'Safety check discrepancies give motive to conceal audit.'),
        ('mira_sen', 'voss', 'motive', 'C09', 'Voss planned to report antenna safety discrepancies.'),
        ('adrian_cole', 'override', 'access_location', 'C04', 'Director credential used at maintenance panel at 22:14.'),
        ('adrian_cole', 'override', 'suspicious_timing', 'C04', 'Override occurred minutes before the camera gap.'),
        ('adrian_cole', 'motive', 'motive', 'C09', 'Disagreement about audit package and compliance reports.'),
        ('nadia_rahman', 'transmission', 'suspicious_timing', 'C05', 'Warning recorded at 22:10; transmitted later at 23:47.'),
        ('nadia_rahman', 'transmission', 'timeline_inconsistency', 'C05', 'Recording timestamp is not the transmission time.'),
        ('nadia_rahman', 'queue', 'timeline_inconsistency', 'C05', 'Delayed queue held message in buffer.'),
        ('jonas_reed', 'camera', 'suspicious_timing', 'C03', 'Camera feed missing for seven minutes (22:16–22:23).'),
        ('jonas_reed', 'camera', 'access_location', 'C03', 'Feed suppression indicates intentional intervention.'),
        ('jonas_reed', 'detour', 'timeline_inconsistency', 'C11', 'Patrol log differs from first statement regarding 22:29.'),
        ('jonas_reed', 'detour', 'possible_deception', 'C11', 'Omitted personal call from initial report.'),
        ('evelyn_shaw', 'time', 'contradiction', 'C06', 'Death window 22:15–22:35 contradicts incident report 23:47 time.'),
        ('evelyn_shaw', 'time', 'timeline_inconsistency', 'C06', 'Medical signs indicate death occurred well before 23:47.'),
        ('evelyn_shaw', 'report', 'possible_deception', 'C06', 'Pressured by Cole to use transmission time in official report.'),
        ('leila_voss', 'message', 'motive', 'C10', 'Voss feared report alteration and preserved copy.'),
        ('theo_pike', 'hatch', 'access_location', 'C07', 'Cable-service hatch exists behind communications console.'),
        ('theo_pike', 'hatch', 'opportunity', 'C07', 'Cole supervised previous inspection of the hatch route.'),
        ('mara_bell', 'dispatch', 'suspicious_timing', 'C12', 'Transmission sounded like buffered recording with no live pause.'),
        ('soren_vale', 'audit', 'motive', 'C10', 'Voss planned to deliver audit package the following morning.')
    ) AS v(character_key, topic_key, category, clue_key, explanation)
    JOIN case_character_profiles cp ON cp.case_id = 6 AND cp.character_key = v.character_key
    JOIN dialogue_topics dt ON dt.case_id = cp.case_id AND dt.person_id = cp.person_id AND dt.topic_key = v.topic_key
    JOIN case_clues cc ON cc.case_id = cp.case_id AND cc.clue_key = v.clue_key
    JOIN canonical_topic_insights cti ON cti.topic_id = dt.topic_id AND cti.category = v.category
    WHERE cti.target_clue_id <> cc.clue_id;

    IF v_conflicts IS NOT NULL THEN
        RAISE EXCEPTION 'Seed verification failed: conflicting pre-existing canonical mappings detected: %', v_conflicts;
    END IF;

    -- Safely insert new mappings; retain identical existing mappings safely
    INSERT INTO canonical_topic_insights(case_id, topic_id, category, target_clue_id, explanation)
    SELECT dt.case_id, dt.topic_id, v.category, cc.clue_id, v.explanation
    FROM (VALUES
        ('mira_sen', 'notebook', 'physical_evidence', 'C09', 'Preserved notebook page proving antenna check discrepancies.'),
        ('mira_sen', 'notebook', 'motive', 'C09', 'Safety check discrepancies give motive to conceal audit.'),
        ('mira_sen', 'voss', 'motive', 'C09', 'Voss planned to report antenna safety discrepancies.'),
        ('adrian_cole', 'override', 'access_location', 'C04', 'Director credential used at maintenance panel at 22:14.'),
        ('adrian_cole', 'override', 'suspicious_timing', 'C04', 'Override occurred minutes before the camera gap.'),
        ('adrian_cole', 'motive', 'motive', 'C09', 'Disagreement about audit package and compliance reports.'),
        ('nadia_rahman', 'transmission', 'suspicious_timing', 'C05', 'Warning recorded at 22:10; transmitted later at 23:47.'),
        ('nadia_rahman', 'transmission', 'timeline_inconsistency', 'C05', 'Recording timestamp is not the transmission time.'),
        ('nadia_rahman', 'queue', 'timeline_inconsistency', 'C05', 'Delayed queue held message in buffer.'),
        ('jonas_reed', 'camera', 'suspicious_timing', 'C03', 'Camera feed missing for seven minutes (22:16–22:23).'),
        ('jonas_reed', 'camera', 'access_location', 'C03', 'Feed suppression indicates intentional intervention.'),
        ('jonas_reed', 'detour', 'timeline_inconsistency', 'C11', 'Patrol log differs from first statement regarding 22:29.'),
        ('jonas_reed', 'detour', 'possible_deception', 'C11', 'Omitted personal call from initial report.'),
        ('evelyn_shaw', 'time', 'contradiction', 'C06', 'Death window 22:15–22:35 contradicts incident report 23:47 time.'),
        ('evelyn_shaw', 'time', 'timeline_inconsistency', 'C06', 'Medical signs indicate death occurred well before 23:47.'),
        ('evelyn_shaw', 'report', 'possible_deception', 'C06', 'Pressured by Cole to use transmission time in official report.'),
        ('leila_voss', 'message', 'motive', 'C10', 'Voss feared report alteration and preserved copy.'),
        ('theo_pike', 'hatch', 'access_location', 'C07', 'Cable-service hatch exists behind communications console.'),
        ('theo_pike', 'hatch', 'opportunity', 'C07', 'Cole supervised previous inspection of the hatch route.'),
        ('mara_bell', 'dispatch', 'suspicious_timing', 'C12', 'Transmission sounded like buffered recording with no live pause.'),
        ('soren_vale', 'audit', 'motive', 'C10', 'Voss planned to deliver audit package the following morning.')
    ) AS v(character_key, topic_key, category, clue_key, explanation)
    JOIN case_character_profiles cp ON cp.case_id = 6 AND cp.character_key = v.character_key
    JOIN dialogue_topics dt ON dt.case_id = cp.case_id AND dt.person_id = cp.person_id AND dt.topic_key = v.topic_key
    JOIN case_clues cc ON cc.case_id = cp.case_id AND cc.clue_key = v.clue_key
    ON CONFLICT (topic_id, category) DO NOTHING;

    -- Assert exactly 21 rules exist
    SELECT count(*) INTO v_rule_count FROM canonical_topic_insights WHERE case_id = 6;
    IF v_rule_count <> 21 THEN
        RAISE EXCEPTION 'Seed verification failed: expected 21 canonical insight rules for Case 6, but found %', v_rule_count;
    END IF;
END $$;

-- 8. Record migration
INSERT INTO schema_migrations(version, description)
VALUES('002_manual_insights_and_official_records', 'Additive support for manual insight categorization and linking sessions to core DBMS records')
ON CONFLICT(version) DO NOTHING;

COMMIT;
