import os, sys
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql://postgres:Ak%40160606@localhost:5432/casegraph"
sys.path.insert(0, r"C:\Users\aksha\Downloads\casegraph")

import db
from app import app

client = app.test_client()

def test_full_loop():
    print("=" * 60)
    print("RUNNING FULL INVESTIGATION GAME END-TO-END ACCEPTANCE TEST")
    print("=" * 60)

    # 1. Solved benchmark session check
    with db.get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM game_sessions WHERE session_id = 'bddee33b-6e0c-4910-b842-80e5fcd066ca'")
        bench = cur.fetchone()
        assert bench and bench['status'] == 'solved', "Benchmark solved session missing"
        cur.execute("SELECT count(*) as n FROM score_events WHERE session_id = 'bddee33b-6e0c-4910-b842-80e5fcd066ca'")
        assert cur.fetchone()['n'] == 29, "Benchmark score count must be 29"
    print("STEP 1 PASSED: Benchmark solved session is intact.")

    # 2. Get Case 001 Briefing
    res = client.get('/api/game/001/briefing')
    assert res.status_code == 200, f"Briefing failed: {res.data}"
    briefing = res.get_json()
    assert 'Blackridge' in briefing['briefing']
    print("STEP 2 PASSED: Incident briefing fetched successfully.")

    # 3. Start a new test investigation session
    res = client.post('/api/game/001/start', json={'player_label': 'Live Demo Investigator'})
    assert res.status_code == 201, f"Start failed: {res.data}"
    start_data = res.get_json()
    sid = start_data['session']['session_id']
    assert sid != 'bddee33b-6e0c-4910-b842-80e5fcd066ca'
    print(f"STEP 3 PASSED: Session started ({sid}). Initial score: {start_data['score']}.")

    # 4. Check available characters and dynamic topics
    nadia = next(c for c in start_data['characters'] if c['character_key'] == 'nadia_rahman')
    cole = next(c for c in start_data['characters'] if c['character_key'] == 'adrian_cole')
    theo = next(c for c in start_data['characters'] if c['character_key'] == 'theo_pike')
    shaw = next(c for c in start_data['characters'] if c['character_key'] == 'evelyn_shaw')

    assert len(nadia['topics']) >= 2, "Nadia must have available topics"
    assert len(cole['topics']) >= 3, "Cole must have available topics"
    assert len(theo['topics']) >= 2, "Theo must have available topics"
    print("STEP 4 PASSED: Dynamic character inquiry topics populated correctly.")

    # 5. Question Nadia on Transmission
    res = client.post(f'/api/game/session/{sid}/interview', json={
        'person_id': nadia['person_id'],
        'question': 'When was the transmission sent?'
    })
    assert res.status_code == 200
    nadia_data = res.get_json()
    assert 'not spoken at 23:47' in nadia_data['response']
    print("STEP 5 PASSED: Nadia questioned on transmission.")

    # 6. Flag Insight: Suspicious Timing on Nadia's transmission statement -> Unlocks C05
    res = client.post(f'/api/game/session/{sid}/insight', json={
        'person_id': nadia['person_id'],
        'dialogue_id': nadia_data['dialogue_id'],
        'topic_id': nadia_data['topic_id'],
        'category': 'suspicious_timing',
        'player_notes': 'The 23:47 broadcast was queued at 22:10.'
    })
    assert res.status_code == 201
    ins_nadia = res.get_json()
    assert ins_nadia['is_valid'] is True
    assert ins_nadia['points_awarded'] == 10
    c05_id = ins_nadia['matched_clue_id']
    print(f"STEP 6 PASSED: Insight validated (+10 pts). Clue C05 unlocked.")

    # 7. File C05 as official evidence record in PostgreSQL DBMS
    res = client.post(f'/api/game/session/{sid}/record-official', json={
        'action': 'evidence',
        'title': 'Radio Console Buffer Log (C05)',
        'description': 'Radio queue diagnostics confirm warning message was stored at 22:10 and sent at 23:47.',
        'evidence_type': 'digital',
        'verification_status': 'verified',
        'clue_id': c05_id,
        'people': [{'person_id': nadia['person_id'], 'involvement': 'operator'}]
    })
    assert res.status_code == 201
    print("STEP 7 PASSED: Clue C05 filed into real PostgreSQL public.evidence table (+5 pts).")

    # 8. Question Theo Pike on Service Hatch
    res = client.post(f'/api/game/session/{sid}/interview', json={
        'person_id': theo['person_id'],
        'question': 'Tell me about the service hatch.'
    })
    assert res.status_code == 200
    theo_data = res.get_json()
    assert 'cable-service hatch' in theo_data['response'].lower()

    # 9. Flag Insight on Theo: Access to Location -> Unlocks C07
    res = client.post(f'/api/game/session/{sid}/insight', json={
        'person_id': theo['person_id'],
        'dialogue_id': theo_data['dialogue_id'],
        'topic_id': theo_data['topic_id'],
        'category': 'access_location',
        'player_notes': 'Cable hatch behind communications room console bypasses locked door.'
    })
    assert res.status_code == 201
    ins_theo = res.get_json()
    assert ins_theo['is_valid'] is True
    print("STEP 9 PASSED: Theo hatch insight validated (+10 pts). Clue C07 unlocked.")

    # 10. Question Dr. Evelyn Shaw on Time of Death
    res = client.post(f'/api/game/session/{sid}/interview', json={
        'person_id': shaw['person_id'],
        'question': 'What was the estimated time of death?'
    })
    assert res.status_code == 200
    shaw_data = res.get_json()
    assert '22:15' in shaw_data['response']

    # 11. Flag Contradiction on Shaw: Time of Death Contradicts Broadcast -> Unlocks C06
    res = client.post(f'/api/game/session/{sid}/insight', json={
        'person_id': shaw['person_id'],
        'dialogue_id': shaw_data['dialogue_id'],
        'topic_id': shaw_data['topic_id'],
        'category': 'contradiction',
        'player_notes': 'Medical examination places death between 22:15 and 22:35, before the broadcast.'
    })
    assert res.status_code == 201
    ins_shaw = res.get_json()
    assert ins_shaw['is_valid'] is True
    print("STEP 11 PASSED: Shaw medical contradiction validated (+10 pts). Clue C06 unlocked.")

    # 12. Test Incorrect Accusation: Accusing Dr. Evelyn Shaw
    res = client.post(f'/api/game/session/{sid}/submit', json={
        'accused_person_id': shaw['person_id'],
        'motive_key': 'academic_rivalry',
        'method_key': 'poisoning',
        'explanation': 'I suspect Dr. Shaw poisoned Dr. Voss.'
    })
    assert res.status_code == 200
    wrong_acc = res.get_json()
    assert wrong_acc['correct'] is False
    assert wrong_acc['state']['session']['status'] == 'active'
    print("STEP 12 PASSED: Incorrect accusation properly rejected (-10 pts penalty).")

    # 13. Test Final Correct Accusation: Accusing Adrian Cole
    # First discover Cole by interviewing him
    client.post(f'/api/game/session/{sid}/interview', json={
        'person_id': cole['person_id'],
        'question': 'Where were you that night?'
    })

    res = client.post(f'/api/game/session/{sid}/submit', json={
        'accused_person_id': cole['person_id'],
        'motive_key': 'compliance_coverup',
        'method_key': 'service_hatch_and_calibration_weight',
        'explanation': 'Cole killed Voss to conceal falsified antenna safety records, struck him with the brass weight, and escaped via the cable-service hatch.'
    })
    assert res.status_code == 200
    solved_res = res.get_json()
    assert solved_res['correct'] is True
    assert solved_res['motive_correct'] is True
    assert solved_res['method_correct'] is True
    assert solved_res['solution'] is not None
    assert solved_res['solution']['culprit'] == 'Adrian Cole'
    assert solved_res['state']['session']['status'] == 'solved'
    print(f"STEP 13 PASSED: Case solved! Final Score: {solved_res['state']['score']} pts.")

    # 14. Verify Session Persistence & Solved State from Database
    res = client.get(f'/api/game/session/{sid}')
    assert res.status_code == 200
    persisted = res.get_json()
    assert persisted['session']['status'] == 'solved'
    assert persisted['solution'] is not None
    assert len(persisted['score_events']) >= 5
    print("STEP 14 PASSED: Solved session state, canonical solution, and score events fully persisted in PostgreSQL.")

    # 15. Benchmark check after all tests
    with db.get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM game_sessions WHERE session_id = 'bddee33b-6e0c-4910-b842-80e5fcd066ca'")
        bench = cur.fetchone()
        assert bench and bench['status'] == 'solved'
        cur.execute("SELECT count(*) as n FROM score_events WHERE session_id = 'bddee33b-6e0c-4910-b842-80e5fcd066ca'")
        assert cur.fetchone()['n'] == 29
    print("STEP 15 PASSED: Benchmark solved session is intact.")

    print("\n" + "=" * 60)
    print("ALL FULL INVESTIGATION GAME ACCEPTANCE TESTS PASSED (100%)!")
    print("=" * 60)

if __name__ == '__main__':
    test_full_loop()
