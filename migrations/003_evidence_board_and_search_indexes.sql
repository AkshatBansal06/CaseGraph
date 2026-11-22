-- Migration 003: Evidence Board Connections and Search Indexing
-- Safe, additive migration. Preserves all existing tables and data.

BEGIN;

CREATE TABLE IF NOT EXISTS session_board_connections (
    connection_id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES game_sessions(session_id) ON DELETE CASCADE,
    case_id INT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    source_entity_type VARCHAR(30) NOT NULL,
    source_entity_id INT NOT NULL,
    target_entity_type VARCHAR(30) NOT NULL,
    target_entity_id INT NOT NULL,
    connection_type VARCHAR(50) NOT NULL,
    player_notes TEXT DEFAULT '',
    evaluation_status VARCHAR(20) NOT NULL DEFAULT 'unverified',
    evaluation_reason TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_board_no_self_loop CHECK (NOT (source_entity_type = target_entity_type AND source_entity_id = target_entity_id)),
    CONSTRAINT uq_session_board_conn UNIQUE(session_id, source_entity_type, source_entity_id, target_entity_type, target_entity_id, connection_type)
);

CREATE INDEX IF NOT EXISTS idx_board_conn_session ON session_board_connections(session_id);
CREATE INDEX IF NOT EXISTS idx_board_conn_case ON session_board_connections(case_id);
CREATE INDEX IF NOT EXISTS idx_board_conn_source ON session_board_connections(source_entity_type, source_entity_id);
CREATE INDEX IF NOT EXISTS idx_board_conn_target ON session_board_connections(target_entity_type, target_entity_id);

CREATE INDEX IF NOT EXISTS idx_evidence_case_title ON evidence(case_id, title);
CREATE INDEX IF NOT EXISTS idx_timeline_case_time ON timeline_events(case_id, event_time);
CREATE INDEX IF NOT EXISTS idx_dialogue_session_person ON dialogue_history(session_id, person_id);

INSERT INTO schema_migrations(version, applied_at, description)
VALUES('003_evidence_board_and_search_indexes', now(), 'Additive table for player theory connections on evidence board and search optimization')
ON CONFLICT (version) DO NOTHING;

COMMIT;
