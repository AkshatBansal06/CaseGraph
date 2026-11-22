import os, sys
if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'postgresql://postgres:Ak%40160606@localhost:5432/casegraph'
sys.path.insert(0, r'C:\Users\aksha\Downloads\casegraph')
from app import app
import db

client = app.test_client()

def run_tests():
    print("=" * 60)
    print("RUNNING ADVANCED FEATURES AUTOMATED TEST SUITE")
    print("=" * 60)

    # 1. Start a session
    res = client.post('/api/game/001/start', json={'player_label': 'Feature Tester'})
    assert res.status_code == 201, res.data
    sid = res.get_json()['session']['session_id']
    print(f"TEST 1 PASSED: Session started ({sid}).")

    # 2. Test Evidence Board GET
    res = client.get(f'/api/game/board?case_id=6&session_id={sid}')
    assert res.status_code == 200, res.data
    board = res.get_json()
    assert 'entities' in board and 'connections' in board
    p_cnt = len(board['entities']['persons'])
    off_cnt = len(board['connections']['official'])
    print(f"TEST 2 PASSED: Board loaded ({p_cnt} persons, {off_cnt} official connections).")

    # 3. Test Evidence Board POST connection
    res = client.post('/api/game/board/connection', json={
        'session_id': sid,
        'case_id': 6,
        'source_entity_type': 'person',
        'source_entity_id': 15,
        'target_entity_type': 'evidence',
        'target_entity_id': 4,
        'connection_type': 'has_access_to',
        'player_notes': 'Cole director override at 22:14'
    })
    assert res.status_code == 201, res.data
    conn_data = res.get_json()
    assert conn_data['ok'] is True
    assert conn_data['evaluation_status'] == 'supported'
    cid = conn_data['connection_id']
    print(f"TEST 3 PASSED: Board theory connection created (id={cid}, status={conn_data['evaluation_status']}).")

    # 4. Test Search Terminal
    res = client.get(f'/api/game/search-terminal?case_id=6&session_id={sid}&q=override')
    assert res.status_code == 200, res.data
    search_data = res.get_json()
    assert search_data['total'] > 0
    print(f"TEST 4 PASSED: Search terminal for 'override' found {search_data['total']} real database items.")

    # 5. Test Search Terminal does NOT leak undiscovered secret clues
    res = client.get(f'/api/game/search-terminal?case_id=6&session_id={sid}&q=hatch')
    assert res.status_code == 200, res.data
    hatch_search = res.get_json()
    # Theo hatch clue (C07) is initially locked and undiscovered in this new session
    clue_results = [r for r in hatch_search['results'] if r['kind'] == 'clue']
    c07_found = any('C07' in r['title'] for r in clue_results)
    assert not c07_found, "Undiscovered clue C07 must NOT be leaked in search!"
    print("TEST 5 PASSED: Search terminal strictly protects undiscovered case secrets.")

    # 6. Test DBMS Tables List
    res = client.get('/api/dbms/tables')
    assert res.status_code == 200, res.data
    tables_data = res.get_json()
    assert tables_data['total'] >= 25
    print(f"TEST 6 PASSED: DBMS Lab lists {tables_data['total']} application tables.")

    # 7. Test DBMS Table inspect
    res = client.get('/api/dbms/table/evidence')
    assert res.status_code == 200, res.data
    tbl = res.get_json()
    assert len(tbl['columns']) > 0
    print(f"TEST 7 PASSED: DBMS inspect 'evidence': {len(tbl['columns'])} cols, {tbl['sample_count']} sample rows.")

    # 8. Test DBMS Predefined Analytical Query
    res = client.post('/api/dbms/execute-predefined', json={'query_id': 'evidence_per_person', 'case_id': 6})
    assert res.status_code == 200, res.data
    qres = res.get_json()
    assert len(qres['rows']) > 0
    print(f"TEST 8 PASSED: DBMS Predefined Query '{qres['name']}' returned {qres['row_count']} rows in {qres['execution_time_ms']} ms.")

    # 9. Test Safe Custom SQL
    res = client.post('/api/dbms/execute-custom', json={'sql': 'SELECT person_id, full_name, occupation FROM persons ORDER BY person_id LIMIT 5'})
    assert res.status_code == 200, res.data
    cres = res.get_json()
    assert len(cres['rows']) == 5
    print(f"TEST 9 PASSED: Safe Custom SQL executed ({cres['row_count']} rows, {cres['execution_time_ms']} ms).")

    # 10. Test SQL Mutation Safety Rejections
    res = client.post('/api/dbms/execute-custom', json={'sql': 'DROP TABLE persons'})
    assert res.status_code == 400
    res = client.post('/api/dbms/execute-custom', json={'sql': 'DELETE FROM persons WHERE person_id = 1'})
    assert res.status_code == 400
    res = client.post('/api/dbms/execute-custom', json={'sql': 'SELECT 1; DROP TABLE persons'})
    assert res.status_code == 400
    print("TEST 10 PASSED: SQL mutation attempts (DROP, DELETE, multi-statement) were blocked safely.")

    # 11. Test Schema Graph
    res = client.get('/api/dbms/schema-graph')
    assert res.status_code == 200, res.data
    graph_data = res.get_json()
    assert len(graph_data['nodes']) > 0 and len(graph_data['edges']) > 0
    print(f"TEST 11 PASSED: Schema Graph returned {len(graph_data['nodes'])} table nodes and {len(graph_data['edges'])} FK edges.")

    # 12. Test Deleting Board Theory Connection
    res = client.delete(f'/api/game/board/connection/{cid}?session_id={sid}')
    assert res.status_code == 200
    print(f"TEST 12 PASSED: Board connection #{cid} deleted safely.")

    # 13. Verify Benchmark Solved Session is 100% Intact
    with db.get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM game_sessions WHERE session_id = 'bddee33b-6e0c-4910-b842-80e5fcd066ca'")
        bench = cur.fetchone()
        assert bench and bench['status'] == 'solved'
        cur.execute("SELECT count(*) as n FROM score_events WHERE session_id = 'bddee33b-6e0c-4910-b842-80e5fcd066ca'")
        assert cur.fetchone()['n'] == 29
    print("TEST 13 PASSED: Benchmark solved session is 100% intact with 29 score events.")

    print("\n" + "=" * 60)
    print("ALL ADVANCED FEATURES TESTS PASSED (100% SUCCESS)!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
