import os, sys, json
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql://postgres:Ak%40160606@localhost:5432/casegraph"
sys.path.insert(0, r"C:\Users\aksha\Downloads\casegraph")

import db
from app import app

client = app.test_client()

def run_tests():
    print("=" * 60)
    print("RUNNING STAGE 1 AUTOMATED INTEGRATION TEST SUITE")
    print("=" * 60)

    # -------------------------------------------------------------
    # 0. Benchmark Check: Solved session is untouched
    # -------------------------------------------------------------
    with db.get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT status, current_stage, 
                   (SELECT count(*) FROM score_events se WHERE se.session_id = gs.session_id) as score_count
            FROM game_sessions gs
            WHERE session_id = 'bddee33b-6e0c-4910-b842-80e5fcd066ca'
        """)
        solved_session = cur.fetchone()
        assert solved_session is not None, "Original solved session must exist"
        assert solved_session['status'] == 'solved', "Original solved session must remain 'solved'"
        assert solved_session['score_count'] == 29, f"Original score events must be 29, found {solved_session['score_count']}"
    print("TEST 0 PASSED: Solved session bddee33b-6e0c-4910-b842-80e5fcd066ca and 29 score events untouched.")

    # -------------------------------------------------------------
    # 1. Start a fresh, separate test session
    # -------------------------------------------------------------
    res = client.post('/api/game/001/start', json={'player_label': 'Stage 1 QA Test'})
    assert res.status_code == 201, f"Failed to start session: {res.data}"
    start_data = res.get_json()
    test_session_id = start_data['session']['session_id']
    assert test_session_id != 'bddee33b-6e0c-4910-b842-80e5fcd066ca', "Must create a distinct session"
    initial_score = start_data['score']
    print(f"TEST 1 PASSED: Separate test session started: {test_session_id} (Initial score: {initial_score})")

    # -------------------------------------------------------------
    # 2. Interview: Verify Grounded Response & NO Automatic Clues
    # -------------------------------------------------------------
    # Person 16 is Nadia Rahman in Case 6
    res = client.post(f'/api/game/session/{test_session_id}/interview', json={
        'person_id': 16,
        'question': 'When was the transmission sent?'
    })
    assert res.status_code == 200, f"Interview failed: {res.data}"
    inv_data = res.get_json()
    assert inv_data['ok'] is True
    assert inv_data['matched_topic'] is not None
    assert 'not spoken at 23:47' in inv_data['response']
    did = inv_data['dialogue_id']
    tid = inv_data['topic_id']
    assert did is not None and tid is not None

    # CRITICAL CHECK: In the reference build, this dialogue automatically unlocked C05!
    # In our corrected loop, C05 must NOT be unlocked yet!
    c05 = next(c for c in inv_data['state']['clues'] if c['clue_key'] == 'C05')
    assert c05['discovered'] is False, "CRITICAL: Clue C05 must NOT be automatically discovered upon interview!"
    print(f"TEST 2 PASSED: Interview returns grounded response. Clue C05 remains undiscovered.")

    # -------------------------------------------------------------
    # 3. Manual Insight Recognition
    # -------------------------------------------------------------
    # 3A. Unsupported inference: Flagging 'motive' on Nadia's transmission statement
    res = client.post(f'/api/game/session/{test_session_id}/insight', json={
        'dialogue_id': did,
        'person_id': 16,
        'topic_id': tid,
        'category': 'motive',
        'player_notes': 'I think Nadia sent the transmission to frame Cole.'
    })
    assert res.status_code == 201
    bad_insight = res.get_json()
    assert bad_insight['is_valid'] is False
    assert bad_insight['points_awarded'] == 0
    print("TEST 3A PASSED: Unsupported insight stored as unverified note with 0 points.")

    # 3B. Repeated submission of unsupported note: should update, not award duplicate points
    res = client.post(f'/api/game/session/{test_session_id}/insight', json={
        'dialogue_id': did,
        'person_id': 16,
        'topic_id': tid,
        'category': 'motive',
        'player_notes': 'Updated note: Still not convinced it was Cole.'
    })
    assert res.status_code == 200
    update_data = res.get_json()
    assert update_data['status'] == 'note_updated'
    assert update_data['is_valid'] is False
    print("TEST 3B PASSED: Repeated unsupported insight updates note without duplicate points.")

    # 3C. Valid canonical breakthrough: Flagging 'suspicious_timing' on Nadia's transmission statement
    res = client.post(f'/api/game/session/{test_session_id}/insight', json={
        'dialogue_id': did,
        'person_id': 16,
        'topic_id': tid,
        'category': 'suspicious_timing',
        'player_notes': 'The transmission timestamp 23:47 does not match the actual recording time.'
    })
    assert res.status_code == 201
    valid_insight = res.get_json()
    assert valid_insight['is_valid'] is True
    assert valid_insight['matched_clue_id'] is not None
    assert valid_insight['points_awarded'] == 10
    valid_insight_id = valid_insight['insight_id']
    clue_c05_id = valid_insight['matched_clue_id']

    # Verify C05 is now discovered in session state!
    c05_post = next(c for c in valid_insight['state']['clues'] if c['clue_key'] == 'C05')
    assert c05_post['discovered'] is True, "C05 must now be unlocked after manual insight recognition"
    print(f"TEST 3C PASSED: Canonical insight validated, Clue C05 unlocked, +10 points awarded.")

    # 3D. Repeated canonical submission: must reject duplicate and award 0 points
    res = client.post(f'/api/game/session/{test_session_id}/insight', json={
        'dialogue_id': did,
        'person_id': 16,
        'topic_id': tid,
        'category': 'suspicious_timing',
        'player_notes': 'Trying to submit again for points.'
    })
    assert res.status_code == 200
    dup_data = res.get_json()
    assert dup_data['status'] == 'already_verified'
    assert dup_data['ok'] is False
    print("TEST 3D PASSED: Duplicate canonical insight rejected with clear message; 0 duplicate points.")

    # -------------------------------------------------------------
    # 4. Multi-Action Official Record Creation to PostgreSQL
    # -------------------------------------------------------------
    # 4A. Action: Evidence -> Saves to public.evidence and visible in Vault
    res = client.post(f'/api/game/session/{test_session_id}/record-official', json={
        'action': 'evidence',
        'title': 'Test Radio Transmission Log (Delayed Queue)',
        'description': 'Radio console buffer proves distress warning was queued at 22:10 and sent at 23:47.',
        'evidence_type': 'digital',
        'verification_status': 'verified',
        'clue_id': clue_c05_id,
        'insight_id': valid_insight_id,
        'people': [{'person_id': 16, 'involvement': 'recorded'}]
    })
    assert res.status_code == 201, f"Record evidence failed: {res.data}"
    ev_data = res.get_json()
    new_evidence_id = ev_data['evidence_id']
    print(f"TEST 4A.1 PASSED: Official evidence record #{new_evidence_id} created.")

    # Verify visible via original dashboard endpoint /api/evidence?case_id=6
    res = client.get('/api/evidence?case_id=6')
    assert res.status_code == 200
    evidence_vault = res.get_json()
    matching_evidence = [e for e in evidence_vault if e['evidence_id'] == new_evidence_id]
    assert len(matching_evidence) == 1, "New evidence must appear immediately in CaseGraph Evidence Vault!"
    assert matching_evidence[0]['title'] == 'Test Radio Transmission Log (Delayed Queue)'
    print("TEST 4A.2 PASSED: Evidence immediately visible in original CaseGraph Evidence Vault.")

    # 4B. Action: Relationship -> Saves to public.person_relationships and visible in Graph
    # Link Nadia (16) and Elias Voss (13)
    res = client.post(f'/api/game/session/{test_session_id}/record-official', json={
        'action': 'relationship',
        'person_id': 16,
        'related_person_id': 13,
        'relationship_type': 'queued transmission for',
        'insight_id': valid_insight_id
    })
    assert res.status_code == 201, f"Record relationship failed: {res.data}"
    rel_data = res.get_json()
    new_rel_id = rel_data['relationship_id']
    print(f"TEST 4B.1 PASSED: Official relationship #{new_rel_id} created.")

    # Verify visible via original dashboard endpoint /api/graph?case_id=6
    res = client.get('/api/graph?case_id=6')
    assert res.status_code == 200
    graph = res.get_json()
    matching_edges = [e for e in graph['edges'] if e['label'] == 'queued transmission for']
    assert len(matching_edges) == 1, "New relationship must appear immediately in CaseGraph Relationship Graph!"
    print("TEST 4B.2 PASSED: Relationship immediately visible in original Cytoscape Graph.")

    # 4C. Action: Timeline -> Saves to public.timeline_events and visible in Timeline & Conflict Analysis
    res = client.post(f'/api/game/session/{test_session_id}/record-official', json={
        'action': 'timeline',
        'person_id': 16,
        'event_time': '2026-10-29 22:10:00',
        'location_name': 'Communications Room',
        'description': 'Nadia queues Dr. Voss warning message into diagnostic buffer.',
        'source_evidence_id': new_evidence_id,
        'is_verified': True,
        'insight_id': valid_insight_id
    })
    assert res.status_code == 201, f"Record timeline failed: {res.data}"
    timeline_data = res.get_json()
    new_event_id = timeline_data['event_id']
    print(f"TEST 4C.1 PASSED: Official timeline event #{new_event_id} created.")

    # Verify visible via original dashboard endpoint /api/timeline?case_id=6
    res = client.get('/api/timeline?case_id=6')
    assert res.status_code == 200
    timeline = res.get_json()
    matching_events = [t for t in timeline if t['event_id'] == new_event_id]
    assert len(matching_events) == 1, "New timeline event must appear immediately in CaseGraph Timeline!"
    print("TEST 4C.2 PASSED: Timeline event immediately visible in original Timeline.")

    # -------------------------------------------------------------
    # 5. Verify Scoring Idempotency and Session Persistence
    # -------------------------------------------------------------
    # Fetch session state again
    res = client.get(f'/api/game/session/{test_session_id}')
    assert res.status_code == 200
    final_state = res.get_json()
    # Initial score + 10 (Nadia discovery) + 10 (insight) + 5 (evidence) + 5 (rel) + 5 (timeline) = +35
    expected_score = initial_score + 10 + 10 + 5 + 5 + 5
    assert final_state['score'] == expected_score, f"Expected score {expected_score}, got {final_state['score']}"
    assert final_state['evidence_count'] == 1
    assert final_state['relationship_count'] == 1
    assert final_state['timeline_count'] == 1
    print(f"TEST 5 PASSED: Session progress persisted with verified score: {final_state['score']}.")

    # -------------------------------------------------------------
    # 6. Re-check Benchmark Solved Session
    # -------------------------------------------------------------
    with db.get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT status, (SELECT count(*) FROM score_events se WHERE se.session_id = gs.session_id) as score_count
            FROM game_sessions gs
            WHERE session_id = 'bddee33b-6e0c-4910-b842-80e5fcd066ca'
        """)
        solved_session = cur.fetchone()
        assert solved_session['status'] == 'solved'
        assert solved_session['score_count'] == 29
    print("TEST 6 PASSED: Benchmark solved session is intact after all operations.")

    print("\n" + "=" * 60)
    print("ALL STAGE 1 AUTOMATED INTEGRATION TESTS PASSED (100% SUCCESS)!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
