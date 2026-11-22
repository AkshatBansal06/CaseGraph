import os
import re
import time
import uuid
from flask import Blueprint, request, jsonify
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from db import get_connection

advanced_bp = Blueprint('advanced_features', __name__)

VALID_ENTITY_TYPES = {'person', 'evidence', 'location', 'timeline'}
VALID_CONNECTION_TYPES = {
    'connected_to',
    'contradicts',
    'supports',
    'present_at',
    'has_access_to',
    'possible_motive',
    'associated_with'
}

FORBIDDEN_SQL_KEYWORDS = {
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
    'TRUNCATE', 'GRANT', 'REVOKE', 'COPY', 'EXECUTE', 'CALL',
    'REPLACE', 'VACUUM', 'SET', 'RESET', 'LOCK'
}

def valid_uuid(raw):
    try:
        return str(uuid.UUID(str(raw).strip()))
    except (ValueError, TypeError, AttributeError):
        return None

def serialize_item(obj):
    if isinstance(obj, dict):
        return {k: serialize_item(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_item(v) for v in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


# =====================================================================
# FEATURE 1: INTERACTIVE EVIDENCE BOARD
# =====================================================================

@advanced_bp.get('/api/game/board')
def get_board_state():
    """Load all board entities and relationships (both official DBMS records and player theories)."""
    case_id = request.args.get('case_id', type=int) or 6
    session_id = valid_uuid(request.args.get('session_id'))

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # 1. Persons
        if session_id:
            cur.execute('''
                SELECT cp.person_id, p.full_name, p.occupation, p.gender, p.photo_path,
                       cp.character_key, cp.public_bio, cp.is_core_character,
                       EXISTS(SELECT 1 FROM session_character_discoveries scd WHERE scd.session_id = %s AND scd.person_id = cp.person_id) AS is_discovered
                FROM case_character_profiles cp
                JOIN persons p ON p.person_id = cp.person_id
                WHERE cp.case_id = %s
                ORDER BY cp.is_core_character DESC, p.full_name
            ''', (session_id, case_id))
        else:
            cur.execute('''
                SELECT cp.person_id, p.full_name, p.occupation, p.gender, p.photo_path,
                       cp.character_key, cp.public_bio, cp.is_core_character,
                       TRUE AS is_discovered
                FROM case_character_profiles cp
                JOIN persons p ON p.person_id = cp.person_id
                WHERE cp.case_id = %s
                ORDER BY cp.is_core_character DESC, p.full_name
            ''', (case_id,))
        persons = cur.fetchall()

        # 2. Evidence
        if session_id:
            cur.execute('''
                SELECT e.evidence_id, e.title, e.description, e.evidence_type, e.verification_status,
                       ser.clue_id, cc.clue_key,
                       (ser.evidence_id IS NOT NULL OR e.case_id = %s) AS is_available
                FROM evidence e
                LEFT JOIN session_evidence_records ser ON ser.evidence_id = e.evidence_id AND ser.session_id = %s
                LEFT JOIN case_clues cc ON cc.clue_id = ser.clue_id
                WHERE e.case_id = %s
                ORDER BY e.evidence_id
            ''', (case_id, session_id, case_id))
        else:
            cur.execute('''
                SELECT e.evidence_id, e.title, e.description, e.evidence_type, e.verification_status,
                       NULL::bigint AS clue_id, NULL::varchar AS clue_key,
                       TRUE AS is_available
                FROM evidence e
                WHERE e.case_id = %s
                ORDER BY e.evidence_id
            ''', (case_id,))
        evidence = cur.fetchall()

        # 3. Discovered Clues (can be placed on board)
        clues = []
        if session_id:
            cur.execute('''
                SELECT cc.clue_id, cc.clue_key, cc.title, cc.public_description, cc.clue_category,
                       TRUE AS is_discovered,
                       EXISTS(SELECT 1 FROM session_evidence_records ser WHERE ser.session_id = %s AND ser.clue_id = cc.clue_id) AS is_filed
                FROM case_clues cc
                JOIN session_clue_discoveries scd ON scd.clue_id = cc.clue_id AND scd.session_id = %s
                WHERE cc.case_id = %s
                ORDER BY cc.clue_key
            ''', (session_id, session_id, case_id))
            clues = cur.fetchall()

        # 4. Locations
        cur.execute('''
            SELECT location_id, location_name
            FROM locations
            WHERE location_id IN (SELECT DISTINCT location_id FROM timeline_events WHERE case_id = %s)
               OR location_id IN (1, 2, 3, 4, 5)
            ORDER BY location_name
        ''', (case_id,))
        locations = cur.fetchall()

        # 5. Timeline Events
        cur.execute('''
            SELECT te.event_id, te.event_time, te.description, te.is_verified,
                   te.person_id, p.full_name AS person_name,
                   te.location_id, l.location_name
            FROM timeline_events te
            JOIN persons p ON p.person_id = te.person_id
            JOIN locations l ON l.location_id = te.location_id
            WHERE te.case_id = %s
            ORDER BY te.event_time
        ''', (case_id,))
        timeline = cur.fetchall()

        # 6. Official Connections from PostgreSQL Core Tables
        official_conns = []

        # 6a. Person Relationships
        cur.execute('''
            SELECT pr.relationship_id, 'person' AS source_type, pr.person_id AS source_id,
                   'person' AS target_type, pr.related_person_id AS target_id,
                   pr.relationship_type AS connection_type,
                   'Official database relationship' AS notes,
                   TRUE AS is_official, 'verified' AS evaluation_status,
                   'Recorded in person_relationships' AS evaluation_reason
            FROM person_relationships pr
            WHERE pr.case_id = %s
        ''', (case_id,))
        official_conns.extend(cur.fetchall())

        # 6b. Evidence-to-Person links
        cur.execute('''
            SELECT ep.evidence_id AS relationship_id, 'evidence' AS source_type, ep.evidence_id AS source_id,
                   'person' AS target_type, ep.person_id AS target_id,
                   ep.involvement AS connection_type,
                   'Official evidence custody link' AS notes,
                   TRUE AS is_official, 'verified' AS evaluation_status,
                   'Recorded in evidence_people' AS evaluation_reason
            FROM evidence_people ep
            JOIN evidence e ON e.evidence_id = ep.evidence_id
            WHERE e.case_id = %s
        ''', (case_id,))
        official_conns.extend(cur.fetchall())

        # 6c. Timeline-to-Person & Location links
        cur.execute('''
            SELECT te.event_id AS relationship_id, 'timeline' AS source_type, te.event_id AS source_id,
                   'person' AS target_type, te.person_id AS target_id,
                   'present_at' AS connection_type,
                   'Timeline event presence' AS notes,
                   TRUE AS is_official,
                   CASE WHEN te.is_verified THEN 'verified' ELSE 'unverified' END AS evaluation_status,
                   'Recorded in timeline_events' AS evaluation_reason
            FROM timeline_events te
            WHERE te.case_id = %s
        ''', (case_id,))
        official_conns.extend(cur.fetchall())

        # 7. Player Theory Connections (from session_board_connections)
        player_theories = []
        if session_id:
            cur.execute('''
                SELECT sbc.connection_id, sbc.source_entity_type AS source_type, sbc.source_entity_id AS source_id,
                       sbc.target_entity_type AS target_type, sbc.target_entity_id AS target_id,
                       sbc.connection_type, sbc.player_notes AS notes,
                       FALSE AS is_official, sbc.evaluation_status, sbc.evaluation_reason,
                       sbc.created_at
                FROM session_board_connections sbc
                WHERE sbc.session_id = %s
                ORDER BY sbc.created_at ASC
            ''', (session_id,))
            player_theories = cur.fetchall()

    return jsonify(serialize_item({
        'ok': True,
        'case_id': case_id,
        'entities': {
            'persons': persons,
            'evidence': evidence,
            'clues': clues,
            'locations': locations,
            'timeline': timeline
        },
        'connections': {
            'official': official_conns,
            'player_theories': player_theories
        },
        'allowed_connection_types': [
            {'type': 'connected_to', 'label': 'Connected To', 'description': 'General investigative link between two entities'},
            {'type': 'contradicts', 'label': 'Contradicts', 'description': 'Direct factual or temporal contradiction between statements/records'},
            {'type': 'supports', 'label': 'Supports', 'description': 'Corroborating record, testimony, or physical proof'},
            {'type': 'present_at', 'label': 'Was Present At', 'description': 'Entity was present at this time or location'},
            {'type': 'has_access_to', 'label': 'Has Access To', 'description': 'Possessed credentials, keys, or physical opportunity'},
            {'type': 'possible_motive', 'label': 'Possible Motive', 'description': 'Grievance, conflict of interest, or threat of exposure'},
            {'type': 'associated_with', 'label': 'Associated With', 'description': 'Professional, departmental, or personal affiliation'}
        ]
    }))


def evaluate_board_connection(cur, case_id, src_type, src_id, tgt_type, tgt_id, conn_type):
    """Evaluate whether a player's theory connection is supported by case ground truth,
    contradicted, or currently unverified. Never leaks the final solution.
    """
    pair = {(src_type, src_id), (tgt_type, tgt_id)}

    # Adrian Cole (15) <-> Maintenance Override Evidence (4)
    if {('person', 15), ('evidence', 4)}.issubset(pair) or {('person', 15), ('evidence', 1)}.issubset(pair):
        if conn_type in ('has_access_to', 'connected_to', 'supports'):
            return 'supported', 'Maintenance panel audit logged Director Cole credentials override at 22:14.'

    # Adrian Cole (15) <-> Dr. Elias Voss (13) Motive
    if {('person', 15), ('person', 13)}.issubset(pair):
        if conn_type in ('possible_motive', 'contradicts'):
            return 'supported', 'Dr. Voss audit package threatened to expose Cole falsified antenna records.'

    # Dr. Evelyn Shaw (18) <-> Broadcast Timeline (e.g. death window)
    if ('person', 18) in pair and conn_type in ('contradicts', 'timeline_inconsistency'):
        return 'supported', 'Dr. Shaw medical notes (22:15-22:35) directly contradict the 23:47 broadcast time.'

    # Theo Pike (20) <-> Service Hatch (evidence 7 or 8)
    if ('person', 20) in pair and (('evidence', 7) in pair or ('evidence', 8) in pair):
        if conn_type in ('has_access_to', 'connected_to', 'supports'):
            return 'supported', 'Theo Pike maintenance schematics confirm concealed crawlspace hatch.'

    # Jonas Reed (17) <-> Camera Gap (evidence 3)
    if ('person', 17) in pair and ('evidence', 3) in pair:
        if conn_type in ('connected_to', 'supports', 'present_at'):
            return 'supported', 'Security camera blackout (22:16-22:23) coincided with Jonas patrol delay.'

    # Nadia Rahman (16) <-> Dr. Elias Voss (13) Motive (Contradicted)
    if {('person', 16), ('person', 13)}.issubset(pair) and conn_type == 'possible_motive':
        return 'contradicted', 'No evidence or witness statements indicate Nadia had any grievance or motive against Dr. Voss.'

    # Nadia Rahman (16) <-> Transmission Evidence (5)
    if ('person', 16) in pair and ('evidence', 5) in pair:
        if conn_type in ('supports', 'connected_to'):
            return 'supported', 'Radio console buffer diagnostics confirm warning was queued at 22:10.'

    return 'unverified', 'Investigative theory documented. Corroborating evidence required.'


@advanced_bp.post('/api/game/board/connection')
def create_board_connection():
    """Create or update a player theory connection on the Evidence Board."""
    data = request.get_json(silent=True) or {}
    session_id = valid_uuid(data.get('session_id'))
    if not session_id:
        return jsonify({'error': 'Valid session_id required.'}), 400

    case_id = int(data.get('case_id') or 6)
    src_type = str(data.get('source_entity_type', '')).strip().lower()
    tgt_type = str(data.get('target_entity_type', '')).strip().lower()
    try:
        src_id = int(data.get('source_entity_id'))
        tgt_id = int(data.get('target_entity_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'source_entity_id and target_entity_id must be integers.'}), 400

    conn_type = str(data.get('connection_type', '')).strip().lower()
    notes = str(data.get('player_notes', '')).strip()[:1000]

    if src_type not in VALID_ENTITY_TYPES or tgt_type not in VALID_ENTITY_TYPES:
        return jsonify({'error': f'Entity types must be one of: {", ".join(sorted(VALID_ENTITY_TYPES))}'}), 400

    if conn_type not in VALID_CONNECTION_TYPES:
        return jsonify({'error': f'Connection type must be one of: {", ".join(sorted(VALID_CONNECTION_TYPES))}'}), 400

    if src_type == tgt_type and src_id == tgt_id:
        return jsonify({'error': 'An entity cannot connect to itself.'}), 400

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # Check active session
        cur.execute('SELECT case_id, status FROM game_sessions WHERE session_id = %s', (session_id,))
        sess = cur.fetchone()
        if not sess:
            return jsonify({'error': 'Session not found.'}), 404

        # Evaluate connection against case rules
        eval_status, eval_reason = evaluate_board_connection(cur, case_id, src_type, src_id, tgt_type, tgt_id, conn_type)

        cur.execute('''
            INSERT INTO session_board_connections(
                session_id, case_id, source_entity_type, source_entity_id,
                target_entity_type, target_entity_id, connection_type,
                player_notes, evaluation_status, evaluation_reason, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (session_id, source_entity_type, source_entity_id, target_entity_type, target_entity_id, connection_type)
            DO UPDATE SET
                player_notes = EXCLUDED.player_notes,
                evaluation_status = EXCLUDED.evaluation_status,
                evaluation_reason = EXCLUDED.evaluation_reason,
                updated_at = now()
            RETURNING connection_id, created_at, updated_at
        ''', (session_id, case_id, src_type, src_id, tgt_type, tgt_id, conn_type, notes, eval_status, eval_reason))
        row = cur.fetchone()
        conn.commit()

        return jsonify({
            'ok': True,
            'connection_id': row['connection_id'],
            'evaluation_status': eval_status,
            'evaluation_reason': eval_reason,
            'message': f'Theory connection saved ({eval_status.upper()}).'
        }), 201


@advanced_bp.delete('/api/game/board/connection/<int:connection_id>')
def delete_board_connection(connection_id):
    """Remove a player theory connection from the Evidence Board."""
    session_id = valid_uuid(request.args.get('session_id') or (request.get_json(silent=True) or {}).get('session_id'))
    if not session_id:
        return jsonify({'error': 'Valid session_id required.'}), 400

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('''
            DELETE FROM session_board_connections
            WHERE connection_id = %s AND session_id = %s
            RETURNING connection_id
        ''', (connection_id, session_id))
        deleted = cur.fetchone()
        conn.commit()

        if not deleted:
            return jsonify({'error': 'Connection not found or not owned by session.'}), 404

        return jsonify({'ok': True, 'deleted_id': connection_id, 'message': 'Theory connection removed.'})


# =====================================================================
# FEATURE 2: INVESTIGATION SEARCH TERMINAL
# =====================================================================

@advanced_bp.get('/api/game/search-terminal')
def search_terminal():
    """Real case-scoped PostgreSQL search across suspects, evidence, testimony,
    timeline, and discovered clues. Strictly respects legitimate player discovery.
    """
    case_id = request.args.get('case_id', type=int) or 6
    session_id = valid_uuid(request.args.get('session_id'))
    raw_query = (request.args.get('q') or '').strip()

    if len(raw_query) < 2:
        return jsonify({'ok': True, 'query': raw_query, 'total': 0, 'results': []})

    term = f'%{raw_query}%'
    results = []

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # 1. Persons
        cur.execute('''
            SELECT p.person_id, p.full_name, p.occupation, cp.public_bio
            FROM persons p
            JOIN case_character_profiles cp ON cp.person_id = p.person_id
            WHERE cp.case_id = %s AND (
                p.full_name ILIKE %s OR p.occupation ILIKE %s OR cp.public_bio ILIKE %s
            )
            LIMIT 10
        ''', (case_id, term, term, term))
        for r in cur.fetchall():
            results.append({
                'kind': 'person',
                'id': r['person_id'],
                'title': r['full_name'],
                'subtitle': r['occupation'] or 'Staff member',
                'excerpt': r['public_bio'] or 'Case person of interest.',
                'status': 'discovered',
                'navigate_view': 'people',
                'target_id': r['person_id']
            })

        # 2. Evidence Records (case-scoped)
        cur.execute('''
            SELECT e.evidence_id, e.title, e.description, e.evidence_type, e.verification_status
            FROM evidence e
            WHERE e.case_id = %s AND (
                e.title ILIKE %s OR e.description ILIKE %s OR e.evidence_type ILIKE %s
            )
            LIMIT 10
        ''', (case_id, term, term, term))
        for r in cur.fetchall():
            results.append({
                'kind': 'evidence',
                'id': r['evidence_id'],
                'title': r['title'],
                'subtitle': f"{r['evidence_type'].title()} · {r['verification_status'].upper()}",
                'excerpt': r['description'][:180] + ('...' if len(r['description']) > 180 else ''),
                'status': r['verification_status'],
                'navigate_view': 'evidence',
                'target_id': r['evidence_id']
            })

        # 3. Discovered Clues (Strictly filtered: initially public OR unlocked in this session)
        if session_id:
            cur.execute('''
                SELECT cc.clue_id, cc.clue_key, cc.title, cc.public_description, cc.clue_category
                FROM case_clues cc
                WHERE cc.case_id = %s 
                  AND (cc.is_initially_available = TRUE OR cc.clue_id IN (
                      SELECT clue_id FROM session_clue_discoveries WHERE session_id = %s
                  ))
                  AND (cc.clue_key ILIKE %s OR cc.title ILIKE %s OR cc.public_description ILIKE %s)
                LIMIT 10
            ''', (case_id, session_id, term, term, term))
            for r in cur.fetchall():
                results.append({
                    'kind': 'clue',
                    'id': r['clue_id'],
                    'title': f"[{r['clue_key']}] {r['title']}",
                    'subtitle': f"Forensic Clue · {r['clue_category'].upper()}",
                    'excerpt': r['public_description'][:180],
                    'status': 'unlocked',
                    'navigate_view': 'interviews',
                    'target_id': r['clue_id']
                })

        # 4. Actual Conducted Testimony (Strictly filtered to this session)
        if session_id:
            cur.execute('''
                SELECT dh.dialogue_id, dh.person_id, p.full_name, dt.display_label,
                       dh.player_question, dh.response_shown, dh.created_at
                FROM dialogue_history dh
                JOIN persons p ON p.person_id = dh.person_id
                LEFT JOIN dialogue_topics dt ON dt.topic_id = dh.topic_id
                WHERE dh.session_id = %s AND (
                    dh.player_question ILIKE %s OR dh.response_shown ILIKE %s OR p.full_name ILIKE %s
                )
                ORDER BY dh.dialogue_id DESC
                LIMIT 10
            ''', (session_id, term, term, term))
            for r in cur.fetchall():
                results.append({
                    'kind': 'testimony',
                    'id': r['dialogue_id'],
                    'title': f"Testimony: {r['full_name']}",
                    'subtitle': f"Q: {r['player_question'][:45]}...",
                    'excerpt': r['response_shown'][:180] + ('...' if len(r['response_shown']) > 180 else ''),
                    'status': 'recorded',
                    'navigate_view': 'interviews',
                    'target_id': r['person_id']
                })

        # 5. Timeline Events
        cur.execute('''
            SELECT te.event_id, te.event_time, te.description, te.is_verified,
                   p.full_name, l.location_name
            FROM timeline_events te
            JOIN persons p ON p.person_id = te.person_id
            JOIN locations l ON l.location_id = te.location_id
            WHERE te.case_id = %s AND (
                te.description ILIKE %s OR l.location_name ILIKE %s OR p.full_name ILIKE %s
            )
            LIMIT 10
        ''', (case_id, term, term, term))
        for r in cur.fetchall():
            results.append({
                'kind': 'timeline',
                'id': r['event_id'],
                'title': f"{r['full_name']} at {r['location_name']}",
                'subtitle': f"Time: {r['event_time']} · {'VERIFIED' if r['is_verified'] else 'UNVERIFIED'}",
                'excerpt': r['description'][:180],
                'status': 'verified' if r['is_verified'] else 'unverified',
                'navigate_view': 'timeline',
                'target_id': r['event_id']
            })

        # 6. Locations
        cur.execute('''
            SELECT location_id, location_name
            FROM locations
            WHERE location_name ILIKE %s
            LIMIT 5
        ''', (term,))
        for r in cur.fetchall():
            results.append({
                'kind': 'location',
                'id': r['location_id'],
                'title': r['location_name'],
                'subtitle': 'Station Facility Zone',
                'excerpt': f"Facility zone: {r['location_name']}",
                'status': 'public',
                'navigate_view': 'timeline',
                'target_id': r['location_id']
            })

    return jsonify(serialize_item({
        'ok': True,
        'query': raw_query,
        'total': len(results),
        'results': results
    }))


# =====================================================================
# FEATURE 3: DBMS QUERY LAB
# =====================================================================

PREBUILT_QUERIES = {
    'evidence_per_person': {
        'name': '1. Evidence Records Per Person',
        'category': 'Forensic Aggregation',
        'description': 'Aggregates official evidence items linked to each person, grouped by verification status.',
        'sql': '''
SELECT p.person_id, p.full_name, p.occupation,
       COUNT(ep.evidence_id) AS total_evidence,
       COUNT(CASE WHEN e.verification_status = 'verified' THEN 1 END) AS verified_evidence,
       COUNT(CASE WHEN e.verification_status = 'unverified' THEN 1 END) AS unverified_evidence
FROM persons p
LEFT JOIN evidence_people ep ON ep.person_id = p.person_id
LEFT JOIN evidence e ON e.evidence_id = ep.evidence_id AND e.case_id = %(case_id)s
WHERE p.person_id IN (SELECT person_id FROM case_persons WHERE case_id = %(case_id)s)
GROUP BY p.person_id, p.full_name, p.occupation
ORDER BY total_evidence DESC, p.full_name ASC;
'''
    },
    'multi_person_evidence': {
        'name': '2. Multi-Suspect Evidence Nexus',
        'category': 'Cross-Referencing',
        'description': 'Identifies evidence items linked to two or more individuals (shared custody or joint presence).',
        'sql': '''
SELECT e.evidence_id, e.title, e.evidence_type, e.verification_status,
       COUNT(ep.person_id) AS linked_persons_count,
       STRING_AGG(p.full_name, ', ' ORDER BY p.full_name) AS associates
FROM evidence e
JOIN evidence_people ep ON ep.evidence_id = e.evidence_id
JOIN persons p ON p.person_id = ep.person_id
WHERE e.case_id = %(case_id)s
GROUP BY e.evidence_id, e.title, e.evidence_type, e.verification_status
HAVING COUNT(ep.person_id) > 1
ORDER BY linked_persons_count DESC;
'''
    },
    'verification_distribution': {
        'name': '3. Evidence Verification Status Distribution',
        'category': 'Data Integrity',
        'description': 'Summarizes evidence records by forensic status with percentage calculations.',
        'sql': '''
SELECT verification_status,
       COUNT(*) AS record_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS percentage_of_total
FROM evidence
WHERE case_id = %(case_id)s
GROUP BY verification_status
ORDER BY record_count DESC;
'''
    },
    'chronological_timeline': {
        'name': '4. Reconstructed Chronological Event Stream',
        'category': 'Temporal Analysis',
        'description': 'Extracts ordered sequence of movements, locations, and verification status during the incident.',
        'sql': '''
SELECT te.event_id, te.event_time, p.full_name, l.location_name,
       te.description, te.is_verified,
       CASE WHEN te.source_evidence_id IS NOT NULL THEN 'Yes' ELSE 'No' END AS has_supporting_evidence
FROM timeline_events te
JOIN persons p ON p.person_id = te.person_id
JOIN locations l ON l.location_id = te.location_id
WHERE te.case_id = %(case_id)s
ORDER BY te.event_time ASC;
'''
    },
    'relationship_centrality': {
        'name': '5. Suspect Relationship Degree Centrality',
        'category': 'Network Analysis',
        'description': 'Ranks persons by the count of distinct interpersonal and operational relationships in the database.',
        'sql': '''
SELECT p.person_id, p.full_name, p.occupation,
       COUNT(pr.relationship_id) AS total_connections,
       STRING_AGG(DISTINCT pr.relationship_type, ' | ') AS relationship_types
FROM persons p
JOIN case_persons cp ON cp.person_id = p.person_id AND cp.case_id = %(case_id)s
LEFT JOIN person_relationships pr ON (pr.person_id = p.person_id OR pr.related_person_id = p.person_id) AND pr.case_id = %(case_id)s
GROUP BY p.person_id, p.full_name, p.occupation
ORDER BY total_connections DESC, p.full_name ASC;
'''
    },
    'location_density': {
        'name': '6. Location Activity & Evidence Density',
        'category': 'Spatial Distribution',
        'description': 'Measures activity frequency across observatory zones based on recorded timeline events.',
        'sql': '''
SELECT l.location_id, l.location_name,
       COUNT(te.event_id) AS recorded_events_count,
       COUNT(DISTINCT te.person_id) AS unique_visitors_count,
       MIN(te.event_time) AS earliest_event,
       MAX(te.event_time) AS latest_event
FROM locations l
LEFT JOIN timeline_events te ON te.location_id = l.location_id AND te.case_id = %(case_id)s
GROUP BY l.location_id, l.location_name
ORDER BY recorded_events_count DESC;
'''
    },
    'timeline_conflicts': {
        'name': '7. Simultaneous Location Conflict Audit',
        'category': 'Forensic Audit',
        'description': 'Queries impossible spatial conflicts where the same person is logged at different locations at the exact same timestamp.',
        'sql': '''
SELECT t1.person_id, p.full_name, t1.event_time,
       l1.location_name AS loc_1, t1.description AS desc_1, t1.is_verified AS ver_1,
       l2.location_name AS loc_2, t2.description AS desc_2, t2.is_verified AS ver_2
FROM timeline_events t1
JOIN timeline_events t2 ON t1.person_id = t2.person_id 
                       AND t1.event_time = t2.event_time 
                       AND t1.event_id < t2.event_id 
                       AND t1.location_id <> t2.location_id
JOIN persons p ON p.person_id = t1.person_id
JOIN locations l1 ON l1.location_id = t1.location_id
JOIN locations l2 ON l2.location_id = t2.location_id
WHERE t1.case_id = %(case_id)s;
'''
    },
    'scoring_history': {
        'name': '8. Investigation Scoring Audit Trail',
        'category': 'Session Analytics',
        'description': 'Lists all awarded points, deduction events, and progression timestamps for active and completed sessions.',
        'sql': '''
SELECT gs.session_id, gs.player_label, gs.status AS session_status,
       se.score_event_id, se.points, se.reason, se.related_key, se.awarded_at
FROM score_events se
JOIN game_sessions gs ON gs.session_id = se.session_id
WHERE gs.case_id = %(case_id)s
ORDER BY se.awarded_at DESC
LIMIT 50;
'''
    },
    'evidence_by_type': {
        'name': '9. Forensic Evidence Type Classification',
        'category': 'Classification',
        'description': 'Breakdown of digital, physical, document, and statement records across the investigation.',
        'sql': '''
SELECT evidence_type,
       COUNT(*) AS total_items,
       COUNT(CASE WHEN verification_status = 'verified' THEN 1 END) AS verified_items,
       MIN(recorded_at) AS first_recorded,
       MAX(recorded_at) AS last_recorded
FROM evidence
WHERE case_id = %(case_id)s
GROUP BY evidence_type
ORDER BY total_items DESC;
'''
    },
    'dialogue_topic_index': {
        'name': '10. Dialogue Topic & Fuzzy Matching Alias Index',
        'category': 'NLP & Knowledge Index',
        'description': 'Analyzes dialogue topics per character and counts active aliases powering the fuzzy question matcher.',
        'sql': '''
SELECT p.person_id, p.full_name,
       COUNT(DISTINCT dt.topic_id) AS total_dialogue_topics,
       COUNT(dta.alias_id) AS total_fuzzy_aliases,
       STRING_AGG(DISTINCT dt.topic_key, ', ') AS topic_keys
FROM persons p
JOIN dialogue_topics dt ON dt.person_id = p.person_id
LEFT JOIN dialogue_topic_aliases dta ON dta.topic_id = dt.topic_id
WHERE dt.case_id = %(case_id)s
GROUP BY p.person_id, p.full_name
ORDER BY total_dialogue_topics DESC;
'''
    }
}


@advanced_bp.get('/api/dbms/tables')
def list_dbms_tables():
    """List all application tables in public schema with row counts and categories."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute('''
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        ''')
        table_rows = cur.fetchall()

        tables_meta = []
        for r in table_rows:
            tname = r['table_name']
            # Get exact count
            try:
                cur.execute(sql.SQL('SELECT COUNT(*) AS n FROM {}').format(sql.Identifier(tname)))
                cnt = cur.fetchone()['n']
            except Exception:
                cnt = 0

            cat = 'Core Investigation Records'
            if tname.startswith('session_') or tname in ('game_sessions', 'score_events'):
                cat = 'Session & Player State'
            elif tname.startswith('dialogue_') or tname in ('case_clues', 'case_facts', 'case_submissions', 'case_character_profiles'):
                cat = 'Game Logic & Testimony'
            elif tname in ('schema_migrations', 'game_case_config'):
                cat = 'Schema & Case Config'

            tables_meta.append({
                'table_name': tname,
                'row_count': cnt,
                'category': cat
            })

    return jsonify({'ok': True, 'total': len(tables_meta), 'tables': tables_meta})


@advanced_bp.get('/api/dbms/table/<table_name>')
def inspect_table(table_name):
    """Safely inspect table schema, columns, primary keys, foreign keys, and sample data."""
    # Ensure table exists in public schema
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute('''
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = %s
        ''', (table_name,))
        if not cur.fetchone():
            return jsonify({'error': f'Table "{table_name}" does not exist in public schema.'}), 404

        # Columns info
        cur.execute('''
            SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        ''', (table_name,))
        columns = cur.fetchall()

        # Primary Key columns
        cur.execute('''
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'public'
              AND tc.table_name = %s
        ''', (table_name,))
        pks = [r['column_name'] for r in cur.fetchall()]

        # Foreign Key constraints
        cur.execute('''
            SELECT kcu.column_name, ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
              AND tc.table_name = %s
        ''', (table_name,))
        fks = cur.fetchall()

        # Sample Rows (limit 25)
        cur.execute(sql.SQL('SELECT * FROM {} LIMIT 25').format(sql.Identifier(table_name)))
        sample_rows = cur.fetchall()

    return jsonify(serialize_item({
        'ok': True,
        'table_name': table_name,
        'columns': columns,
        'primary_keys': pks,
        'foreign_keys': fks,
        'sample_rows': sample_rows,
        'sample_count': len(sample_rows)
    }))


@advanced_bp.get('/api/dbms/queries')
def list_queries():
    """List available prebuilt academic analytical queries."""
    query_list = []
    for qid, q in PREBUILT_QUERIES.items():
        query_list.append({
            'query_id': qid,
            'name': q['name'],
            'category': q['category'],
            'description': q['description'],
            'sql': q['sql'].strip()
        })
    return jsonify({'ok': True, 'queries': query_list})


@advanced_bp.post('/api/dbms/execute-predefined')
def execute_predefined_query():
    """Execute one of the prebuilt analytical queries safely."""
    data = request.get_json(silent=True) or {}
    qid = str(data.get('query_id', '')).strip()
    case_id = int(data.get('case_id') or 6)

    if qid not in PREBUILT_QUERIES:
        return jsonify({'error': f'Invalid query_id "{qid}".'}), 400

    q_meta = PREBUILT_QUERIES[qid]
    query_sql = q_meta['sql']

    start_time = time.perf_counter()
    with get_connection() as conn, conn.cursor() as cur:
        # Run read only
        cur.execute('SET TRANSACTION READ ONLY')
        cur.execute(query_sql, {'case_id': case_id})
        col_names = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return jsonify(serialize_item({
        'ok': True,
        'query_id': qid,
        'name': q_meta['name'],
        'description': q_meta['description'],
        'columns': col_names,
        'rows': rows,
        'row_count': len(rows),
        'execution_time_ms': elapsed_ms,
        'sql_executed': query_sql.strip()
    }))


@advanced_bp.post('/api/dbms/execute-custom')
def execute_custom_sql():
    """Safely execute custom read-only SQL queries (SELECT / WITH CTE only)."""
    data = request.get_json(silent=True) or {}
    raw_sql = str(data.get('sql', '')).strip()

    if not raw_sql:
        return jsonify({'error': 'SQL query is required.'}), 400

    # Safety checks
    # 1. No semicolons (prevent multiple statements)
    clean_sql = raw_sql.rstrip(';').strip()
    if ';' in clean_sql:
        return jsonify({'error': 'Multi-statement SQL execution is strictly forbidden.'}), 400

    # 2. Must start with SELECT or WITH
    upper_sql = clean_sql.upper()
    if not (upper_sql.startswith('SELECT') or upper_sql.startswith('WITH')):
        return jsonify({'error': 'Only read-only SELECT and WITH (CTE) queries are allowed in the DBMS Lab.'}), 400

    # 3. Check forbidden mutation keywords
    words = set(re.findall(r'\b[A-Z]+\b', upper_sql))
    forbidden_found = words.intersection(FORBIDDEN_SQL_KEYWORDS)
    if forbidden_found:
        return jsonify({'error': f'Mutation keyword detected: {", ".join(sorted(forbidden_found))}. Query rejected.'}), 400

    # Add limit if none exists
    if 'LIMIT' not in upper_sql:
        clean_sql = f"{clean_sql} LIMIT 50"

    start_time = time.perf_counter()
    try:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute('SET TRANSACTION READ ONLY')
                    cur.execute(clean_sql)
                    col_names = [desc[0] for desc in cur.description] if cur.description else []
                    rows = cur.fetchall()
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

                    return jsonify(serialize_item({
                        'ok': True,
                        'columns': col_names,
                        'rows': rows,
                        'row_count': len(rows),
                        'execution_time_ms': elapsed_ms,
                        'sql_executed': clean_sql
                    }))
    except psycopg.Error as e:
        return jsonify({'error': f'PostgreSQL Error: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Execution failed: {str(e)}'}), 500


@advanced_bp.get('/api/dbms/schema-graph')
def get_schema_graph():
    """Return relational schema tables and foreign-key edges for visual diagram."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # Get public tables
        cur.execute('''
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        ''')
        tables = [r['table_name'] for r in cur.fetchall()]

        # Columns per table
        cur.execute('''
            SELECT table_name, COUNT(*) AS col_count
            FROM information_schema.columns
            WHERE table_schema = 'public'
            GROUP BY table_name
        ''')
        counts = {r['table_name']: r['col_count'] for r in cur.fetchall()}

        # Primary keys
        cur.execute('''
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
        ''')
        pks = {}
        for r in cur.fetchall():
            pks.setdefault(r['table_name'], []).append(r['column_name'])

        # Foreign keys
        cur.execute('''
            SELECT tc.table_name AS from_table, kcu.column_name AS from_column,
                   ccu.table_name AS to_table, ccu.column_name AS to_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
        ''')
        fks = cur.fetchall()

        nodes = []
        for t in tables:
            nodes.append({
                'data': {
                    'id': t,
                    'label': t,
                    'columns_count': counts.get(t, 0),
                    'pks': pks.get(t, ['id'])
                }
            })

        edges = []
        for idx, fk in enumerate(fks):
            edges.append({
                'data': {
                    'id': f'fk_{idx}',
                    'source': fk['from_table'],
                    'target': fk['to_table'],
                    'label': f"{fk['from_column']} -> {fk['to_column']}",
                    'from_col': fk['from_column'],
                    'to_col': fk['to_column']
                }
            })

        return jsonify({'ok': True, 'nodes': nodes, 'edges': edges})
