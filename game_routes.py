"""Game investigation routes and services for CaseGraph.
Implements the core investigative loop:
Interview -> Manual Insight -> Official Record (Evidence/Relationship/Timeline)
-> PostgreSQL persistence -> Dashboard visibility -> Idempotent scoring.
"""
import re
import uuid
from flask import Blueprint, jsonify, request
from psycopg.errors import UniqueViolation, ForeignKeyViolation, CheckViolation
from db import get_connection

game_bp = Blueprint('game', __name__)
CASE_SLUG = 'the-last-signal'

VALID_INSIGHT_CATEGORIES = {
    'contradiction', 'suspicious_timing', 'timeline_inconsistency',
    'relationship', 'physical_evidence', 'motive', 'opportunity',
    'access_location', 'possible_deception'
}


def err(message, status=400):
    return jsonify({'ok': False, 'error': message}), status


def valid_uuid(raw):
    try:
        return str(uuid.UUID(str(raw)))
    except (ValueError, TypeError, AttributeError):
        return None


def award(cur, sid, key, reason, points, related=None):
    """Idempotently award points. Returns True only if points were newly inserted."""
    cur.execute('''
        INSERT INTO score_events(session_id, idempotency_key, reason, points, related_key)
        VALUES(%s, %s, %s, %s, %s)
        ON CONFLICT(session_id, idempotency_key) DO NOTHING
        RETURNING score_event_id
    ''', (sid, key, reason, points, related))
    return cur.fetchone() is not None


def get_session(cur, sid):
    cur.execute('''
        SELECT gs.*, gc.case_slug, c.title AS case_title, gc.briefing
        FROM game_sessions gs
        JOIN game_case_config gc ON gc.case_id = gs.case_id
        JOIN cases c ON c.case_id = gs.case_id
        WHERE gs.session_id = %s
    ''', (sid,))
    return cur.fetchone()


def match_topic(cur, case_id, person_id, question):
    q = ' '.join(re.sub(r'[^a-z0-9 ]', ' ', question.lower()).split())
    cur.execute('''
        SELECT dt.*, COALESCE(json_agg(dta.alias_text) FILTER (WHERE dta.alias_text IS NOT NULL), '[]') AS aliases
        FROM dialogue_topics dt
        LEFT JOIN dialogue_topic_aliases dta ON dta.topic_id = dt.topic_id
        WHERE dt.case_id = %s AND dt.person_id = %s AND dt.is_initially_available = TRUE
        GROUP BY dt.topic_id
        ORDER BY dt.sort_order
    ''', (case_id, person_id))
    matches = []
    for row in cur.fetchall():
        for alias in row['aliases']:
            a = ' '.join(re.sub(r'[^a-z0-9 ]', ' ', alias.lower()).split())
            if a and (a in q or (len(a.split()) == 1 and a in q.split())):
                matches.append((len(a), row))
    return sorted(matches, key=lambda item: item[0], reverse=True)[0][1] if matches else None


def state_for(cur, session):
    sid = session['session_id']
    cid = session['case_id']

    # 1. Characters and discovery status
    cur.execute('''
        SELECT cp.person_id, cp.character_key, cp.public_bio, cp.discovery_mode, cp.is_core_character,
               p.full_name, p.occupation, p.gender, p.photo_path,
               EXISTS(SELECT 1 FROM session_character_discoveries scd WHERE scd.session_id = %s AND scd.person_id = cp.person_id) AS discovered
        FROM case_character_profiles cp
        JOIN persons p ON p.person_id = cp.person_id
        WHERE cp.case_id = %s
        ORDER BY cp.is_core_character DESC, p.full_name
    ''', (sid, cid))
    characters = cur.fetchall()

    # Attach available dialogue topics to characters
    cur.execute('''
        SELECT dt.topic_id, dt.person_id, dt.topic_key, dt.display_label,
               COALESCE((SELECT dta.alias_text FROM dialogue_topic_aliases dta WHERE dta.topic_id = dt.topic_id ORDER BY length(dta.alias_text) DESC LIMIT 1), dt.display_label) AS sample_question,
               EXISTS(SELECT 1 FROM dialogue_history dh WHERE dh.session_id = %s AND dh.topic_id = dt.topic_id) AS asked
        FROM dialogue_topics dt
        WHERE dt.case_id = %s AND dt.is_initially_available = TRUE
        ORDER BY dt.sort_order
    ''', (sid, cid))
    all_topics = cur.fetchall()
    topics_by_person = {}
    for t in all_topics:
        topics_by_person.setdefault(t['person_id'], []).append(t)
    for c in characters:
        c['topics'] = topics_by_person.get(c['person_id'], [])

    # 2. Clues discovered
    cur.execute('''
        SELECT cc.clue_id, cc.clue_key, cc.title, cc.public_description, cc.clue_category,
               cc.importance, cc.discovery_points, cc.is_initially_available,
               EXISTS(SELECT 1 FROM session_clue_discoveries scd WHERE scd.session_id = %s AND scd.clue_id = cc.clue_id) AS discovered,
               EXISTS(SELECT 1 FROM session_evidence_records ser WHERE ser.session_id = %s AND ser.clue_id = cc.clue_id) AS recorded
        FROM case_clues cc
        WHERE cc.case_id = %s
        ORDER BY cc.clue_key
    ''', (sid, sid, cid))
    clues = cur.fetchall()

    # 3. Recognized insights in this session
    cur.execute('''
        SELECT si.insight_id, si.dialogue_id, si.person_id, p.full_name AS person_name,
               si.topic_id, dt.display_label AS topic_label, si.insight_type,
               si.category, si.player_notes, si.is_valid, si.matched_clue_id,
               cc.clue_key AS matched_clue_key, cc.title AS matched_clue_title,
               si.recognized_at
        FROM session_insights si
        JOIN persons p ON p.person_id = si.person_id
        LEFT JOIN dialogue_topics dt ON dt.topic_id = si.topic_id
        LEFT JOIN case_clues cc ON cc.clue_id = si.matched_clue_id
        WHERE si.session_id = %s
        ORDER BY si.recognized_at ASC
    ''', (sid,))
    insights = cur.fetchall()

    # 4. Official records created by this session
    cur.execute('''
        SELECT ser.evidence_id, e.title, e.description, e.evidence_type, e.verification_status,
               ser.clue_id, cc.clue_key, ser.recorded_at
        FROM session_evidence_records ser
        JOIN evidence e ON e.evidence_id = ser.evidence_id
        LEFT JOIN case_clues cc ON cc.clue_id = ser.clue_id
        WHERE ser.session_id = %s
        ORDER BY ser.recorded_at DESC
    ''', (sid,))
    evidence_records = cur.fetchall()

    cur.execute('''
        SELECT srr.relationship_id, srr.person_id, p1.full_name AS person_name,
               srr.related_person_id, p2.full_name AS related_person_name,
               srr.relationship_type, srr.recorded_at
        FROM session_relationship_records srr
        JOIN persons p1 ON p1.person_id = srr.person_id
        JOIN persons p2 ON p2.person_id = srr.related_person_id
        WHERE srr.session_id = %s
        ORDER BY srr.recorded_at DESC
    ''', (sid,))
    relationship_records = cur.fetchall()

    cur.execute('''
        SELECT str.event_id, te.event_time, te.description, te.is_verified,
               p.person_id, p.full_name, l.location_name, te.source_evidence_id,
               str.recorded_at
        FROM session_timeline_records str
        JOIN timeline_events te ON te.event_id = str.event_id
        JOIN persons p ON p.person_id = te.person_id
        JOIN locations l ON l.location_id = te.location_id
        WHERE str.session_id = %s
        ORDER BY te.event_time ASC
    ''', (sid,))
    timeline_records = cur.fetchall()

    # 5. Dialogue history (recent)
    cur.execute('''
        SELECT dh.dialogue_id, dh.person_id, p.full_name AS person_name,
               dh.topic_id, dt.display_label AS topic_label,
               dh.player_question, dh.response_shown, dh.response_mode, dh.created_at
        FROM dialogue_history dh
        JOIN persons p ON p.person_id = dh.person_id
        LEFT JOIN dialogue_topics dt ON dt.topic_id = dh.topic_id
        WHERE dh.session_id = %s
        ORDER BY dh.dialogue_id ASC
    ''', (sid,))
    history = cur.fetchall()

    # 6. Score breakdown and counts
    cur.execute('SELECT COALESCE(SUM(points), 0) AS total_score FROM score_events WHERE session_id = %s', (sid,))
    score = cur.fetchone()['total_score']

    cur.execute('SELECT COUNT(*) AS n FROM session_character_discoveries WHERE session_id = %s', (sid,))
    chars_found = cur.fetchone()['n']

    cur.execute('SELECT COUNT(*) AS n FROM session_clue_discoveries WHERE session_id = %s', (sid,))
    clues_found = cur.fetchone()['n']

    cur.execute('''
        SELECT submission_id, accused_person_id, motive_key, method_key,
               culprit_correct, motive_correct, method_correct, explanation, submitted_at
        FROM case_submissions
        WHERE session_id = %s
        ORDER BY submitted_at DESC LIMIT 1
    ''', (sid,))
    submission = cur.fetchone()

    cur.execute('''
        SELECT score_event_id, reason, points, related_key, awarded_at
        FROM score_events
        WHERE session_id = %s
        ORDER BY score_event_id ASC
    ''', (sid,))
    score_events = cur.fetchall()

    solution = None
    if session['status'] == 'solved':
        solution = {
            'culprit': 'Adrian Cole',
            'motive': 'Voss discovered falsified antenna safety and grant-compliance records; Cole killed him to prevent disclosure.',
            'method': 'Cole used director override, killed Voss with the brass calibration weight, and exited through the cable-service hatch before the door latched.',
            'transmission': 'Voss recorded warning at 22:10; queued in buffer and transmitted at 23:47.'
        }

    def serialize(obj):
        if isinstance(obj, dict): return {k: serialize(v) for k, v in obj.items()}
        if isinstance(obj, list): return [serialize(v) for v in obj]
        if isinstance(obj, uuid.UUID): return str(obj)
        if hasattr(obj, 'isoformat'): return obj.isoformat()
        return obj

    return serialize({
        'session': session,
        'score': score,
        'characters': characters,
        'characters_found': chars_found,
        'characters_total': len(characters),
        'clues': clues,
        'clues_found': clues_found,
        'clues_total': len(clues),
        'insights': insights,
        'insights_count': len(insights),
        'evidence_records': evidence_records,
        'evidence_count': len(evidence_records),
        'relationship_records': relationship_records,
        'relationship_count': len(relationship_records),
        'timeline_records': timeline_records,
        'timeline_count': len(timeline_records),
        'history': history,
        'submission': submission,
        'score_events': score_events,
        'solution': solution
    })


# ---------------- API Endpoints ----------------

@game_bp.get('/api/game/sessions')
def list_sessions():
    """List sessions for a case so the player can resume their work."""
    case_id = request.args.get('case_id', type=int)
    if not case_id:
        return err('Valid case_id required.')
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('''
            SELECT gs.session_id, gs.case_id, gs.player_label, gs.status, gs.current_stage,
                   gs.started_at, gs.ended_at,
                   COALESCE((SELECT SUM(points) FROM score_events se WHERE se.session_id = gs.session_id), 0) AS score,
                   (SELECT COUNT(*) FROM session_character_discoveries scd WHERE scd.session_id = gs.session_id) AS characters_found,
                   (SELECT COUNT(*) FROM session_clue_discoveries scd WHERE scd.session_id = gs.session_id) AS clues_found,
                   (SELECT COUNT(*) FROM session_evidence_records ser WHERE ser.session_id = gs.session_id) AS evidence_count
            FROM game_sessions gs
            WHERE gs.case_id = %s
            ORDER BY gs.started_at DESC
        ''', (case_id,))
        rows = cur.fetchall()
        for r in rows:
            r['session_id'] = str(r['session_id'])
            if r.get('started_at'): r['started_at'] = r['started_at'].isoformat()
            if r.get('ended_at'): r['ended_at'] = r['ended_at'].isoformat()
        return jsonify(rows)


@game_bp.get('/api/game/001/briefing')
def get_briefing():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('''
            SELECT c.case_id, c.title, gc.case_slug, gc.briefing, gc.difficulty
            FROM game_case_config gc
            JOIN cases c ON c.case_id = gc.case_id
            WHERE gc.case_slug = %s AND gc.is_published = TRUE
        ''', (CASE_SLUG,))
        row = cur.fetchone()
        if not row:
            return err('Case 001 configuration not found.', 404)
        return jsonify(row)


@game_bp.post('/api/game/001/start')
def start_or_resume():
    """Start a new game session or resume an active session for the player."""
    data = request.get_json(silent=True) or {}
    player = (data.get('player_label') or 'Lead Investigator').strip()[:100]
    resume_id = valid_uuid(data.get('resume_session_id'))

    with get_connection() as conn:
        with conn.cursor() as cur:
            # If resuming an existing session
            if resume_id:
                session = get_session(cur, resume_id)
                if session:
                    return jsonify(state_for(cur, session))

            cur.execute('SELECT case_id FROM game_case_config WHERE case_slug = %s AND is_published = TRUE', (CASE_SLUG,))
            config = cur.fetchone()
            if not config:
                return err('Case 001 not configured.', 404)

            cur.execute('''
                INSERT INTO game_sessions(case_id, player_label, current_stage, status)
                VALUES(%s, %s, 'interviews', 'active')
                RETURNING session_id
            ''', (config['case_id'], player))
            new_id = cur.fetchone()['session_id']

            # Victim Elias Voss is initially revealed as deceased victim
            cur.execute("SELECT person_id FROM case_character_profiles WHERE case_id=%s AND character_key='elias_voss'", (config['case_id'],))
            victim = cur.fetchone()
            if victim:
                cur.execute('''
                    INSERT INTO session_character_discoveries(session_id, person_id, discovery_source)
                    VALUES(%s, %s, 'briefing')
                    ON CONFLICT DO NOTHING
                ''', (new_id, victim['person_id']))
                award(cur, new_id, 'character:elias_voss', 'character_discovered', 10, 'elias_voss')

            conn.commit()
            session = get_session(cur, new_id)
            return jsonify(state_for(cur, session)), 201


@game_bp.get('/api/game/session/<session_id>')
def load_session_state(session_id):
    sid = valid_uuid(session_id)
    if not sid:
        return err('Invalid session ID.')
    with get_connection() as conn, conn.cursor() as cur:
        session = get_session(cur, sid)
        if not session:
            return err('Session not found.', 404)
        return jsonify(state_for(cur, session))


@game_bp.post('/api/game/session/<session_id>/interview')
def conduct_interview(session_id):
    """Ask a character a question.
    Deterministic topic matching.
    NOTE: Does NOT automatically award clue discoveries or clue points!
    The player must interpret testimony and manually recognize an insight.
    """
    sid = valid_uuid(session_id)
    if not sid:
        return err('Invalid session ID.')
    data = request.get_json(silent=True) or {}
    try:
        person_id = int(data.get('person_id'))
        question = (data.get('question') or '').strip()
    except (TypeError, ValueError):
        return err('Person ID and question text required.')

    if not question:
        return err('Please enter a question.')
    if len(question) > 1000:
        return err('Question too long (max 1000 chars).')

    with get_connection() as conn:
        with conn.cursor() as cur:
            session = get_session(cur, sid)
            if not session or session['status'] != 'active':
                return err('Session is not active.', 409)

            cur.execute('''
                SELECT cp.*, p.full_name
                FROM case_character_profiles cp
                JOIN persons p ON p.person_id = cp.person_id
                WHERE cp.case_id = %s AND cp.person_id = %s
            ''', (session['case_id'], person_id))
            person = cur.fetchone()
            if not person:
                return err('Person not linked to this case.', 404)

            # Discover character on first interview
            cur.execute('''
                INSERT INTO session_character_discoveries(session_id, person_id, discovery_source)
                VALUES(%s, %s, 'interview')
                ON CONFLICT DO NOTHING RETURNING person_id
            ''', (sid, person_id))
            if cur.fetchone():
                award(cur, sid, f'character:{person["character_key"]}', 'character_discovered', 10, person['character_key'])

            topic = None
            if person['character_key'] == 'elias_voss':
                response = 'Dr. Voss is deceased and cannot be interviewed. His recorded messages, notebook, and earlier statements provide his testimony.'
            else:
                topic = match_topic(cur, session['case_id'], person_id, question)
                if topic:
                    response = topic['canonical_response']
                    # Adrian Cole confrontation check
                    if person['character_key'] == 'adrian_cole' and topic['topic_key'] == 'confrontation':
                        cur.execute('''
                            SELECT cc.clue_key
                            FROM case_clues cc
                            WHERE cc.clue_id IN (
                                SELECT clue_id FROM session_evidence_records WHERE session_id = %s
                                UNION
                                SELECT clue_id FROM session_clue_discoveries WHERE session_id = %s
                            )
                        ''', (sid, sid))
                        recorded = {r['clue_key'] for r in cur.fetchall()}
                        if not {'C03', 'C04', 'C07', 'C08'}.issubset(recorded):
                            response = "Cole's expression hardens. 'You are making assumptions from incomplete records. Show me evidence that places me in that room.'"
                else:
                    response = "I don't know that, and I won't guess. Try asking about my alibi, the observatory, the transmission, the victim, the records, or what I saw that night."

            # Record dialogue history
            cur.execute('''
                INSERT INTO dialogue_history(session_id, person_id, topic_id, player_question, response_shown, response_mode)
                VALUES(%s, %s, %s, %s, %s, %s)
                RETURNING dialogue_id
            ''', (sid, person_id, topic['topic_id'] if topic else None, question, response, 'scripted' if topic else 'fallback'))
            did = cur.fetchone()['dialogue_id']

            conn.commit()
            return jsonify({
                'ok': True,
                'dialogue_id': did,
                'topic_id': topic['topic_id'] if topic else None,
                'matched_topic': topic['display_label'] if topic else None,
                'response': response,
                'state': state_for(cur, session)
            })


@game_bp.post('/api/game/session/<session_id>/insight')
def recognize_insight(session_id):
    """Player manually flags an insight on testimony or enters an investigative note.
    Server validates whether the topic + category matches canonical case ground truth.
    Never trusts client-supplied validity or clue IDs.
    """
    sid = valid_uuid(session_id)
    if not sid:
        return err('Invalid session ID.')
    data = request.get_json(silent=True) or {}

    try:
        person_id = int(data.get('person_id'))
    except (TypeError, ValueError):
        return err('person_id must be an integer.')

    dialogue_id = data.get('dialogue_id')
    if dialogue_id is not None:
        try: dialogue_id = int(dialogue_id)
        except (TypeError, ValueError): return err('dialogue_id must be an integer.')

    topic_id = data.get('topic_id')
    if topic_id is not None:
        try: topic_id = int(topic_id)
        except (TypeError, ValueError): return err('topic_id must be an integer.')

    category = str(data.get('category', '') or '').strip().lower() or None
    notes = str(data.get('player_notes', '') or '').strip()[:2000]
    insight_type = 'general_note' if not category else 'statement_insight'

    if insight_type == 'statement_insight' and category not in VALID_INSIGHT_CATEGORIES:
        return err(f'Category must be one of: {", ".join(sorted(VALID_INSIGHT_CATEGORIES))}.')

    with get_connection() as conn:
        with conn.cursor() as cur:
            session = get_session(cur, sid)
            if not session or session['status'] != 'active':
                return err('Session is not active.', 409)

            # Verify person belongs to this case
            cur.execute('SELECT 1 FROM case_character_profiles WHERE case_id = %s AND person_id = %s', (session['case_id'], person_id))
            if not cur.fetchone():
                return err('Person is not part of this case.', 404)

            # If dialogue_id is provided, verify it belongs to this session and person
            if dialogue_id:
                cur.execute('SELECT topic_id FROM dialogue_history WHERE dialogue_id = %s AND session_id = %s AND person_id = %s', (dialogue_id, sid, person_id))
                dh_row = cur.fetchone()
                if not dh_row:
                    return err('Dialogue record not found for this session and person.', 404)
                if topic_id is None:
                    topic_id = dh_row['topic_id']

            # If topic_id is provided, verify it exists
            if topic_id:
                cur.execute('SELECT topic_id, display_label FROM dialogue_topics WHERE topic_id = %s AND case_id = %s', (topic_id, session['case_id']))
                topic_row = cur.fetchone()
                if not topic_row:
                    return err('Dialogue topic does not exist for this case.', 404)

            # Check for existing insight for this session, topic, and category
            if topic_id and category:
                cur.execute('''
                    SELECT insight_id, is_valid, player_notes, matched_clue_id
                    FROM session_insights
                    WHERE session_id = %s AND topic_id = %s AND category = %s
                ''', (sid, topic_id, category))
                existing = cur.fetchone()
                if existing:
                    if existing['is_valid']:
                        return jsonify({
                            'ok': False,
                            'status': 'already_verified',
                            'message': 'You have already verified this canonical insight in your case file. No duplicate points awarded.',
                            'insight_id': existing['insight_id'],
                            'is_valid': True,
                            'state': state_for(cur, session)
                        })
                    else:
                        # Update existing unverified note
                        cur.execute('''
                            UPDATE session_insights
                            SET player_notes = %s, recognized_at = now()
                            WHERE insight_id = %s
                        ''', (notes, existing['insight_id']))
                        conn.commit()
                        return jsonify({
                            'ok': True,
                            'status': 'note_updated',
                            'message': 'Existing investigative note updated. This theory remains unverified by canonical case evidence.',
                            'insight_id': existing['insight_id'],
                            'is_valid': False,
                            'state': state_for(cur, session)
                        })

            # Check canonical insight rules
            is_valid = False
            matched_clue_id = None
            explanation = ''
            if topic_id and category:
                cur.execute('''
                    SELECT target_clue_id, explanation
                    FROM canonical_topic_insights
                    WHERE case_id = %s AND topic_id = %s AND category = %s
                ''', (session['case_id'], topic_id, category))
                match = cur.fetchone()
                if match:
                    is_valid = True
                    matched_clue_id = match['target_clue_id']
                    explanation = match['explanation']

            # Insert into session_insights
            cur.execute('''
                INSERT INTO session_insights(session_id, dialogue_id, person_id, topic_id, insight_type, category, player_notes, is_valid, matched_clue_id)
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING insight_id
            ''', (sid, dialogue_id, person_id, topic_id, insight_type, category, notes, is_valid, matched_clue_id))
            iid = cur.fetchone()['insight_id']

            # If valid, unlock clue in session_clue_discoveries and award points once
            points_awarded = 0
            if is_valid and matched_clue_id:
                cur.execute('''
                    INSERT INTO session_clue_discoveries(session_id, clue_id, discovery_source)
                    VALUES(%s, %s, 'recognized_insight')
                    ON CONFLICT DO NOTHING
                ''', (sid, matched_clue_id))

                cur.execute('SELECT clue_key, discovery_points FROM case_clues WHERE clue_id = %s', (matched_clue_id,))
                clue_meta = cur.fetchone()
                if award(cur, sid, f'insight:{topic_id}:{category}', 'insight_recognized', 10, f'{clue_meta["clue_key"]}:{category}'):
                    points_awarded = 10

            conn.commit()
            msg = f'Breakthrough validated! Clue {clue_meta["clue_key"]} lead unlocked (+{points_awarded} pts).' if is_valid else 'Investigative note recorded in file. This statement does not establish that deduction (0 pts).'
            return jsonify({
                'ok': True,
                'status': 'verified' if is_valid else 'unverified_note',
                'insight_id': iid,
                'is_valid': is_valid,
                'matched_clue_id': matched_clue_id,
                'explanation': explanation,
                'points_awarded': points_awarded,
                'message': msg,
                'state': state_for(cur, session)
            }), 201


@game_bp.post('/api/game/session/<session_id>/record-official')
def create_official_record(session_id):
    """Create an official record in the real PostgreSQL database tables
    (evidence, person_relationships, or timeline_events) from player deductions.
    Transactional, idempotent scoring, immediately visible on CaseGraph dashboard.
    """
    sid = valid_uuid(session_id)
    if not sid:
        return err('Invalid session ID.')
    data = request.get_json(silent=True) or {}
    action = str(data.get('action', '') or '').strip().lower()

    if action not in ('evidence', 'relationship', 'timeline'):
        return err("Action must be 'evidence', 'relationship', or 'timeline'.")

    insight_id = data.get('insight_id')
    if insight_id is not None:
        try: insight_id = int(insight_id)
        except (TypeError, ValueError): insight_id = None

    with get_connection() as conn:
        with conn.cursor() as cur:
            session = get_session(cur, sid)
            if not session or session['status'] != 'active':
                return err('Session is not active.', 409)
            cid = session['case_id']

            # ---------------- ACTION 1: EVIDENCE ----------------
            if action == 'evidence':
                title = str(data.get('title', '') or '').strip()[:150]
                description = str(data.get('description', '') or '').strip()[:10000]
                evidence_type = str(data.get('evidence_type', 'document') or 'document').strip().lower().replace(' ', '_')[:40]
                status = str(data.get('verification_status', 'unverified') or 'unverified').strip().lower()
                clue_id = data.get('clue_id')
                if clue_id is not None:
                    try: clue_id = int(clue_id)
                    except (TypeError, ValueError): clue_id = None

                if not title or not description:
                    return err('Evidence title and description are required.')
                if status not in ('unverified', 'verified', 'disputed'):
                    return err('Status must be unverified, verified, or disputed.')

                people = data.get('people', [])
                if not isinstance(people, list):
                    people = []

                # Prevent duplicate evidence for the same clue in this session
                if clue_id:
                    cur.execute('SELECT evidence_id FROM session_evidence_records WHERE session_id = %s AND clue_id = %s', (sid, clue_id))
                    existing = cur.fetchone()
                    if existing:
                        return err('Official evidence for this clue is already recorded in your session.', 409)

                # Write to core table: public.evidence
                cur.execute('''
                    INSERT INTO evidence(case_id, title, description, evidence_type, verification_status)
                    VALUES(%s, %s, %s, %s, %s)
                    RETURNING evidence_id
                ''', (cid, title, description, evidence_type, status))
                eid = cur.fetchone()['evidence_id']

                # Link people in core table: public.evidence_people
                for p in people:
                    pid = int(p.get('person_id') if isinstance(p, dict) else p)
                    inv = (str(p.get('involvement', 'associated')) if isinstance(p, dict) else 'associated').strip()[:50] or 'associated'
                    cur.execute('SELECT 1 FROM case_persons WHERE case_id = %s AND person_id = %s', (cid, pid))
                    if cur.fetchone():
                        cur.execute('INSERT INTO evidence_people(evidence_id, person_id, involvement) VALUES(%s, %s, %s)', (eid, pid, inv))

                # Link session in session_evidence_records & legacy session_evidence
                cur.execute('''
                    INSERT INTO session_evidence_records(session_id, evidence_id, clue_id, created_from_insight_id)
                    VALUES(%s, %s, %s, %s)
                ''', (sid, eid, clue_id, insight_id))
                if clue_id:
                    cur.execute('INSERT INTO session_evidence(session_id, clue_id) VALUES(%s, %s) ON CONFLICT DO NOTHING', (sid, clue_id))

                # Award +5 points once
                award(cur, sid, f'record:evidence:{eid}', 'evidence_recorded', 5, f'eid:{eid}')
                conn.commit()
                return jsonify({
                    'ok': True,
                    'action': 'evidence',
                    'evidence_id': eid,
                    'message': 'Official evidence record created in PostgreSQL and visible in Vault.',
                    'state': state_for(cur, session)
                }), 201

            # ---------------- ACTION 2: RELATIONSHIP ----------------
            elif action == 'relationship':
                try:
                    p1 = int(data.get('person_id'))
                    p2 = int(data.get('related_person_id'))
                except (TypeError, ValueError):
                    return err('person_id and related_person_id must be integers.')

                rel_type = str(data.get('relationship_type', '') or '').strip()[:50]
                if not rel_type:
                    return err('Relationship type is required.')
                if p1 == p2:
                    return err('A person cannot be related to themselves.')

                for pid in (p1, p2):
                    cur.execute('SELECT 1 FROM case_persons WHERE case_id = %s AND person_id = %s', (cid, pid))
                    if not cur.fetchone():
                        return err(f'Person {pid} is not linked to this case.', 404)

                # Check if this exact relationship already exists in game session records
                cur.execute('''
                    SELECT relationship_id FROM session_relationship_records
                    WHERE session_id = %s AND person_id = %s AND related_person_id = %s AND relationship_type = %s
                ''', (sid, p1, p2, rel_type))
                existing_session_rel = cur.fetchone()
                if existing_session_rel:
                    return err('This relationship is already documented in your investigation file.', 409)

                # Check core table: reuse existing core row if identical, otherwise insert
                cur.execute('''
                    SELECT relationship_id FROM person_relationships
                    WHERE case_id = %s AND person_id = %s AND related_person_id = %s AND relationship_type = %s
                    LIMIT 1
                ''', (cid, p1, p2, rel_type))
                core_row = cur.fetchone()
                if core_row:
                    rid = core_row['relationship_id']
                else:
                    cur.execute('''
                        INSERT INTO person_relationships(case_id, person_id, related_person_id, relationship_type)
                        VALUES(%s, %s, %s, %s)
                        RETURNING relationship_id
                    ''', (cid, p1, p2, rel_type))
                    rid = cur.fetchone()['relationship_id']

                # Link in session_relationship_records
                cur.execute('''
                    INSERT INTO session_relationship_records(session_id, relationship_id, person_id, related_person_id, relationship_type, created_from_insight_id)
                    VALUES(%s, %s, %s, %s, %s, %s)
                ''', (sid, rid, p1, p2, rel_type, insight_id))

                # Award +5 points once
                award(cur, sid, f'record:rel:{min(p1, p2)}:{max(p1, p2)}:{rel_type}', 'relationship_recorded', 5, f'rid:{rid}')
                conn.commit()
                return jsonify({
                    'ok': True,
                    'action': 'relationship',
                    'relationship_id': rid,
                    'message': 'Relationship documented in PostgreSQL and updated on Graph.',
                    'state': state_for(cur, session)
                }), 201

            # ---------------- ACTION 3: TIMELINE ----------------
            elif action == 'timeline':
                try:
                    pid = int(data.get('person_id'))
                except (TypeError, ValueError):
                    return err('person_id must be an integer.')

                event_time = str(data.get('event_time', '') or '').strip()[:40]
                location_name = str(data.get('location_name', '') or '').strip()[:100]
                description = str(data.get('description', '') or '').strip()[:10000]
                is_verified = bool(data.get('is_verified', False))
                source_eid = data.get('source_evidence_id')
                if source_eid is not None:
                    try: source_eid = int(source_eid)
                    except (TypeError, ValueError): source_eid = None

                if not event_time or not location_name or not description:
                    return err('Event time, location name, and description are required.')

                cur.execute('SELECT 1 FROM case_persons WHERE case_id = %s AND person_id = %s', (cid, pid))
                if not cur.fetchone():
                    return err('Person is not linked to this case.', 404)

                if source_eid:
                    cur.execute('SELECT 1 FROM evidence WHERE case_id = %s AND evidence_id = %s', (cid, source_eid))
                    if not cur.fetchone():
                        return err('Source evidence does not belong to this case.', 404)

                # Core locations table upsert
                cur.execute('''
                    INSERT INTO locations(location_name)
                    VALUES(%s)
                    ON CONFLICT(location_name) DO UPDATE SET location_name = EXCLUDED.location_name
                    RETURNING location_id
                ''', (location_name,))
                lid = cur.fetchone()['location_id']

                # Core timeline_events insert
                cur.execute('''
                    INSERT INTO timeline_events(case_id, person_id, location_id, event_time, description, source_evidence_id, is_verified)
                    VALUES(%s, %s, %s, %s, %s, %s, %s)
                    RETURNING event_id
                ''', (cid, pid, lid, event_time, description, source_eid, is_verified))
                evid = cur.fetchone()['event_id']

                # Link in session_timeline_records
                cur.execute('''
                    INSERT INTO session_timeline_records(session_id, event_id, created_from_insight_id)
                    VALUES(%s, %s, %s)
                ''', (sid, evid, insight_id))

                # Award +5 points once
                award(cur, sid, f'record:timeline:{evid}', 'timeline_recorded', 5, f'evid:{evid}')
                conn.commit()
                return jsonify({
                    'ok': True,
                    'action': 'timeline',
                    'event_id': evid,
                    'message': 'Timeline event recorded in PostgreSQL and updated in Timeline view.',
                    'state': state_for(cur, session)
                }), 201


@game_bp.post('/api/game/session/<session_id>/submit')
def submit_accusation(session_id):
    """Final case accusation and unsealing of canonical solution."""
    sid = valid_uuid(session_id)
    if not sid:
        return err('Invalid session ID.')
    data = request.get_json(silent=True) or {}
    try:
        accused = int(data.get('accused_person_id'))
    except (TypeError, ValueError):
        return err('Choose the person you accuse.')

    motive = (data.get('motive_key') or '').strip()
    method = (data.get('method_key') or '').strip()
    explanation = (data.get('explanation') or '').strip()[:2000]

    with get_connection() as conn:
        with conn.cursor() as cur:
            session = get_session(cur, sid)
            if not session or session['status'] != 'active':
                return err('Session is not active.', 409)

            cur.execute('SELECT 1 FROM session_character_discoveries WHERE session_id = %s AND person_id = %s', (sid, accused))
            if not cur.fetchone():
                return err('Interview or discover this character before accusing them.', 409)

            cur.execute('SELECT character_key FROM case_character_profiles WHERE case_id = %s AND person_id = %s', (session['case_id'], accused))
            profile = cur.fetchone()
            correct = bool(profile and profile['character_key'] == 'adrian_cole')
            motive_ok = (motive == 'compliance_coverup')
            method_ok = (method == 'service_hatch_and_calibration_weight')

            cur.execute('''
                INSERT INTO case_submissions(session_id, accused_person_id, motive_key, method_key, culprit_correct, motive_correct, method_correct, explanation)
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (sid, accused, motive, method, correct, motive_ok, method_ok, explanation))

            if correct:
                award(cur, sid, 'solution:culprit', 'correct_culprit', 100, 'adrian_cole')
                if motive_ok: award(cur, sid, 'solution:motive', 'correct_motive', 25, 'compliance_coverup')
                if method_ok: award(cur, sid, 'solution:method', 'correct_method', 25, 'service_hatch')
                cur.execute("UPDATE game_sessions SET status = 'solved', current_stage = 'case_closed', ended_at = now() WHERE session_id = %s", (sid,))
            else:
                award(cur, sid, f'wrong-accusation:{accused}', 'wrong_accusation', -10, str(accused))

            conn.commit()
            session = get_session(cur, sid)
            solution = {
                'culprit': 'Adrian Cole',
                'motive': 'Voss discovered falsified antenna safety and grant-compliance records; Cole killed him to prevent disclosure.',
                'method': 'Cole used director override, killed Voss with the brass calibration weight, and exited through the cable-service hatch before the door latched.',
                'transmission': 'Voss recorded warning at 22:10; queued in buffer and transmitted at 23:47.'
            } if correct else None

            return jsonify({
                'ok': True,
                'correct': correct,
                'motive_correct': motive_ok,
                'method_correct': method_ok,
                'solution': solution,
                'message': 'Case solved! The canonical solution is unsealed.' if correct else 'That accusation does not fit the evidence. Re-examine your case records.',
                'state': state_for(cur, session)
            })
