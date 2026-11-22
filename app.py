import os
import uuid
from werkzeug.utils import secure_filename
from flask import Flask, render_template, jsonify, request
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import ForeignKeyViolation, CheckViolation, UniqueViolation
from db import get_connection, DatabaseNotConfigured

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'people')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def db():
    return get_connection()


def api_error(message, status=400):
    return jsonify({'error': message}), status


def valid_case_id(raw):
    try:
        value = int(raw)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


@app.get('/')
def dashboard():
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT case_id, title, status FROM cases ORDER BY created_at DESC, case_id DESC')
        cases = cur.fetchall()
    selected = valid_case_id(request.args.get('case_id'))
    if selected is None and cases:
        selected = cases[0]['case_id']
    return render_template('index.html', cases=cases, selected_case_id=selected)


@app.get('/api/cases')
def cases_list():
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT c.case_id, c.title, c.description, c.status, c.created_at,
            (SELECT count(*) FROM case_persons cp WHERE cp.case_id=c.case_id) AS people_count,
            (SELECT count(*) FROM evidence e WHERE e.case_id=c.case_id) AS evidence_count,
            (SELECT count(*) FROM timeline_events t WHERE t.case_id=c.case_id) AS event_count
            FROM cases c ORDER BY c.created_at DESC, c.case_id DESC''')
        return jsonify(cur.fetchall())


@app.get('/api/dashboard')
def dashboard_data():
    case_id = valid_case_id(request.args.get('case_id'))
    if case_id is None:
        return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT case_id, title, description, status, created_at FROM cases WHERE case_id=%s', (case_id,))
        case = cur.fetchone()
        if not case:
            return api_error('Case not found.', 404)
        cur.execute('''SELECT p.person_id, p.full_name, p.occupation, p.gender, p.photo_path, cp.role,
            (SELECT count(*) FROM evidence_people ep JOIN evidence e ON e.evidence_id=ep.evidence_id
             WHERE ep.person_id=p.person_id AND e.case_id=cp.case_id) AS evidence_count
            FROM case_persons cp JOIN persons p ON p.person_id=cp.person_id
            WHERE cp.case_id=%s ORDER BY p.full_name''', (case_id,))
        people = cur.fetchall()
        cur.execute('''SELECT e.evidence_id, e.title, e.description, e.evidence_type,
            e.verification_status, e.recorded_at,
            (SELECT count(*) FROM evidence_people ep WHERE ep.evidence_id=e.evidence_id) AS people_count
            FROM evidence e WHERE e.case_id=%s ORDER BY e.recorded_at DESC, e.evidence_id DESC LIMIT 8''', (case_id,))
        evidence = cur.fetchall()
        cur.execute('SELECT count(*) AS n FROM evidence WHERE case_id=%s', (case_id,)); evidence_count = cur.fetchone()['n']
        cur.execute('SELECT count(*) AS n FROM timeline_events WHERE case_id=%s', (case_id,)); event_count = cur.fetchone()['n']
        cur.execute('SELECT count(*) AS n FROM person_relationships WHERE case_id=%s', (case_id,)); relationship_count = cur.fetchone()['n']
        cur.execute('''SELECT t.event_id, t.event_time, t.description, t.is_verified,
            p.person_id, p.full_name, l.location_name, t.source_evidence_id
            FROM timeline_events t JOIN persons p ON p.person_id=t.person_id
            JOIN locations l ON l.location_id=t.location_id
            WHERE t.case_id=%s ORDER BY t.event_time DESC LIMIT 6''', (case_id,))
        timeline = cur.fetchall()
        cur.execute('''SELECT count(*) AS n FROM (
            SELECT a.person_id, a.event_time FROM timeline_events a JOIN timeline_events b
              ON a.person_id=b.person_id AND a.event_id < b.event_id
             AND a.event_time=b.event_time AND a.location_id<>b.location_id
            WHERE a.case_id=%s AND b.case_id=%s AND a.is_verified=TRUE AND b.is_verified=TRUE
            GROUP BY a.person_id, a.event_time) conflicts''', (case_id, case_id))
        conflict_count = cur.fetchone()['n']
    return jsonify({'case': case, 'people': people, 'evidence': evidence, 'timeline': timeline,
                    'stats': {'people': len(people), 'evidence': evidence_count, 'events': event_count,
                              'relationships': relationship_count, 'contradictions': conflict_count}})


@app.get('/api/person/<int:person_id>')
def person_details(person_id):
    case_id = valid_case_id(request.args.get('case_id'))
    if case_id is None:
        return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT p.person_id, p.full_name, p.occupation, p.gender, p.photo_path, cp.role, cp.case_id
            FROM persons p JOIN case_persons cp ON cp.person_id=p.person_id
            WHERE cp.case_id=%s AND p.person_id=%s''', (case_id, person_id))
        person = cur.fetchone()
        if not person:
            return api_error('Person not found in this case.', 404)
        cur.execute('''SELECT e.evidence_id, e.title, e.description, e.evidence_type,
            e.verification_status, e.recorded_at, ep.involvement
            FROM evidence_people ep JOIN evidence e ON e.evidence_id=ep.evidence_id
            WHERE ep.person_id=%s AND e.case_id=%s ORDER BY e.recorded_at DESC''', (person_id, case_id))
        person['evidence'] = cur.fetchall()
        cur.execute('''SELECT DISTINCT p2.person_id AS connected_person_id, p2.full_name AS connected_person,
            r.relationship_type FROM person_relationships r JOIN persons p2
            ON p2.person_id=CASE WHEN r.person_id=%s THEN r.related_person_id ELSE r.person_id END
            WHERE r.case_id=%s AND (r.person_id=%s OR r.related_person_id=%s)
            AND p2.person_id<>%s ORDER BY p2.full_name''', (person_id, case_id, person_id, person_id, person_id))
        person['connections'] = cur.fetchall()
        cur.execute('''SELECT t.event_id, t.event_time, t.description, t.is_verified, l.location_name
            FROM timeline_events t JOIN locations l ON l.location_id=t.location_id
            WHERE t.case_id=%s AND t.person_id=%s ORDER BY t.event_time''', (case_id, person_id))
        person['timeline'] = cur.fetchall()
    return jsonify(person)


@app.get('/api/graph')
def graph_data():
    case_id = valid_case_id(request.args.get('case_id'))
    if case_id is None: return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT p.person_id, p.full_name, p.occupation, cp.role
            FROM case_persons cp JOIN persons p ON p.person_id=cp.person_id
            WHERE cp.case_id=%s ORDER BY p.full_name''', (case_id,))
        people = cur.fetchall()
        cur.execute('''SELECT r.person_id, r.related_person_id, r.relationship_type
            FROM person_relationships r JOIN case_persons a ON a.case_id=r.case_id AND a.person_id=r.person_id
            JOIN case_persons b ON b.case_id=r.case_id AND b.person_id=r.related_person_id
            WHERE r.case_id=%s''', (case_id,))
        relationships = cur.fetchall()
    # Graph is intentionally built from real case_persons/person_relationships rows only.
    edges, seen = [], set()
    for r in relationships:
        left, right = sorted((r['person_id'], r['related_person_id']))
        key = (left, right, r['relationship_type'])
        if key not in seen:
            seen.add(key)
            edges.append({'source': left, 'target': right, 'label': r['relationship_type']})
    return jsonify({'nodes': people, 'edges': edges})


@app.get('/api/timeline')
def timeline_data():
    case_id = valid_case_id(request.args.get('case_id'))
    if case_id is None: return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT t.event_id, t.event_time, t.description, t.is_verified, t.source_evidence_id,
            p.person_id, p.full_name, l.location_id, l.location_name,
            e.title AS source_evidence_title, e.verification_status AS source_evidence_status
            FROM timeline_events t JOIN persons p ON p.person_id=t.person_id
            JOIN locations l ON l.location_id=t.location_id
            LEFT JOIN evidence e ON e.evidence_id=t.source_evidence_id
            WHERE t.case_id=%s ORDER BY t.event_time ASC''', (case_id,))
        return jsonify(cur.fetchall())


@app.get('/api/contradictions')
def contradictions():
    case_id = valid_case_id(request.args.get('case_id'))
    if case_id is None: return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT p.person_id, p.full_name, a.event_time,
            l1.location_name AS location_one, l2.location_name AS location_two,
            a.description AS event_one, b.description AS event_two,
            a.event_id AS event_one_id, b.event_id AS event_two_id
            FROM timeline_events a JOIN timeline_events b
              ON a.person_id=b.person_id AND a.event_id < b.event_id
             AND a.event_time=b.event_time AND a.location_id<>b.location_id
            JOIN persons p ON p.person_id=a.person_id
            JOIN locations l1 ON l1.location_id=a.location_id
            JOIN locations l2 ON l2.location_id=b.location_id
            WHERE a.case_id=%s AND b.case_id=%s AND a.is_verified=TRUE AND b.is_verified=TRUE
            ORDER BY a.event_time''', (case_id, case_id))
        confirmed = cur.fetchall()
        cur.execute('''SELECT p.person_id, p.full_name, a.event_time,
            l1.location_name AS location_one, l2.location_name AS location_two,
            a.description AS event_one, b.description AS event_two,
            a.event_id AS event_one_id, b.event_id AS event_two_id
            FROM timeline_events a JOIN timeline_events b
              ON a.person_id=b.person_id AND a.event_id < b.event_id
             AND a.event_time=b.event_time AND a.location_id<>b.location_id
            JOIN persons p ON p.person_id=a.person_id
            JOIN locations l1 ON l1.location_id=a.location_id
            JOIN locations l2 ON l2.location_id=b.location_id
            LEFT JOIN evidence ea ON ea.evidence_id=a.source_evidence_id
            LEFT JOIN evidence eb ON eb.evidence_id=b.source_evidence_id
            WHERE a.case_id=%s AND b.case_id=%s
              AND NOT (a.is_verified=TRUE AND b.is_verified=TRUE)
            ORDER BY a.event_time''', (case_id, case_id))
        potential = cur.fetchall()
    return jsonify({'confirmed': confirmed, 'potential': potential})


@app.get('/api/search')
def search():
    case_id = valid_case_id(request.args.get('case_id'))
    q = (request.args.get('q') or '').strip()
    if case_id is None: return api_error('Invalid case ID.')
    if len(q) < 2: return jsonify([])
    pattern = f'%{q}%'
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT 'person' AS kind, p.person_id AS id, p.full_name AS title,
            COALESCE(p.occupation,'Person of interest') AS subtitle
            FROM persons p JOIN case_persons cp ON cp.person_id=p.person_id
            WHERE cp.case_id=%s AND (p.full_name ILIKE %s OR p.occupation ILIKE %s)
            UNION ALL
            SELECT 'evidence', e.evidence_id, e.title, e.evidence_type
            FROM evidence e WHERE e.case_id=%s AND (e.title ILIKE %s OR e.description ILIKE %s OR e.evidence_type ILIKE %s)
            UNION ALL
            SELECT 'location', l.location_id, l.location_name, 'Location'
            FROM locations l JOIN timeline_events t ON t.location_id=l.location_id
            WHERE t.case_id=%s AND l.location_name ILIKE %s
            ORDER BY title LIMIT 30''', (case_id, pattern, pattern, case_id, pattern, pattern, pattern, case_id, pattern))
        return jsonify(cur.fetchall())


@app.get('/api/report')
def report_data():
    case_id = valid_case_id(request.args.get('case_id'))
    if case_id is None: return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT case_id, title, description, status, created_at FROM cases WHERE case_id=%s', (case_id,))
        case = cur.fetchone()
        if not case: return api_error('Case not found.', 404)
        cur.execute('''SELECT p.full_name, p.occupation, cp.role FROM case_persons cp JOIN persons p ON p.person_id=cp.person_id
            WHERE cp.case_id=%s ORDER BY p.full_name''', (case_id,)); people=cur.fetchall()
        cur.execute('SELECT title, evidence_type, verification_status, description, recorded_at FROM evidence WHERE case_id=%s ORDER BY recorded_at', (case_id,)); evidence=cur.fetchall()
        cur.execute('''SELECT t.event_time, p.full_name, l.location_name, t.description, t.is_verified
            FROM timeline_events t JOIN persons p ON p.person_id=t.person_id JOIN locations l ON l.location_id=t.location_id
            WHERE t.case_id=%s ORDER BY t.event_time''', (case_id,)); timeline=cur.fetchall()
    return jsonify({'case':case,'people':people,'evidence':evidence,'timeline':timeline})


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith('/api/'): return api_error('Endpoint or record not found.', 404)
    return 'Page not found', 404


@app.errorhandler(500)
def internal_error(_):
    app.logger.exception('Unhandled application error')
    if request.path.startswith('/api/'): return api_error('An unexpected server error occurred. Check the server terminal.', 500)
    return 'An unexpected server error occurred. Check the server terminal.', 500



# ---------------- Functional CRUD and analysis endpoints ----------------
def payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def required_text(data, key, limit, label=None):
    value = str(data.get(key, '') or '').strip()
    if not value:
        raise ValueError(f'{label or key.replace("_", " ").title()} is required.')
    if len(value) > limit:
        raise ValueError(f'{label or key.replace("_", " ").title()} must be {limit} characters or fewer.')
    return value


@app.get('/api/people')
def list_people():
    case_id = valid_case_id(request.args.get('case_id'))
    if not case_id: return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT p.person_id,p.full_name,p.occupation,p.gender,p.photo_path,cp.role,
            (SELECT count(*) FROM evidence_people ep JOIN evidence e USING(evidence_id) WHERE ep.person_id=p.person_id AND e.case_id=cp.case_id) evidence_count
            FROM case_persons cp JOIN persons p USING(person_id) WHERE cp.case_id=%s ORDER BY p.full_name''',(case_id,))
        return jsonify(cur.fetchall())


@app.post('/api/people')
def create_person():
    data=payload(); case_id=valid_case_id(data.get('case_id'))
    if not case_id: return api_error('A valid case_id is required.')
    try:
        name=required_text(data,'full_name',100,'Full name')
        occupation=str(data.get('occupation','') or '').strip()[:100] or None
        gender=str(data.get('gender','') or '').strip().lower() or None
        if gender not in (None, 'male', 'female'): raise ValueError('Gender must be male, female, or blank.')
        role=str(data.get('role','other') or 'other').strip().lower()
        if role not in ('suspect','witness','investigator','other'): raise ValueError('Role must be suspect, witness, investigator, or other.')
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT 1 FROM cases WHERE case_id=%s',(case_id,))
            if not cur.fetchone(): return api_error('Case not found.',404)
            cur.execute('INSERT INTO persons(full_name,occupation,gender) VALUES(%s,%s,%s) RETURNING person_id',(name,occupation,gender)); pid=cur.fetchone()['person_id']
            cur.execute('INSERT INTO case_persons(case_id,person_id,role) VALUES(%s,%s,%s)',(case_id,pid,role))
        return jsonify({'ok':True,'person_id':pid,'message':'Person created and linked to case.'}),201
    except ValueError as e: return api_error(str(e))
    except (CheckViolation,UniqueViolation,ForeignKeyViolation) as e: return api_error(f'Database constraint: {e.diag.message_primary}')


@app.patch('/api/people/<int:person_id>')
def update_person(person_id):
    data = payload()
    case_id = valid_case_id(data.get('case_id'))
    if not case_id:
        return api_error('A valid case_id is required.')
    try:
        name = required_text(data, 'full_name', 100, 'Full name')
        occupation = str(data.get('occupation', '') or '').strip()[:100] or None
        gender = str(data.get('gender', '') or '').strip().lower() or None
        role = str(data.get('role', 'other') or 'other').strip().lower()
        if gender not in (None, 'male', 'female'):
            raise ValueError('Gender must be male, female, or blank.')
        if role not in ('suspect', 'witness', 'investigator', 'other'):
            raise ValueError('Role must be suspect, witness, investigator, or other.')
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT 1 FROM case_persons WHERE case_id=%s AND person_id=%s', (case_id, person_id))
            if not cur.fetchone():
                return api_error('Person not found in this case.', 404)
            cur.execute('UPDATE persons SET full_name=%s, occupation=%s, gender=%s WHERE person_id=%s', (name, occupation, gender, person_id))
            cur.execute('UPDATE case_persons SET role=%s WHERE case_id=%s AND person_id=%s', (role, case_id, person_id))
        return jsonify({'ok': True, 'message': 'Person updated.'})
    except ValueError as e:
        return api_error(str(e))


@app.delete('/api/people/<int:person_id>')
def remove_person_from_case(person_id):
    case_id = valid_case_id(request.args.get('case_id'))
    if not case_id:
        return api_error('A valid case_id is required.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT 1 FROM case_persons WHERE case_id=%s AND person_id=%s', (case_id, person_id))
        if not cur.fetchone():
            return api_error('Person not found in this case.', 404)
        cur.execute('''SELECT
            EXISTS(SELECT 1 FROM person_relationships WHERE case_id=%s AND (person_id=%s OR related_person_id=%s)) OR
            EXISTS(SELECT 1 FROM timeline_events WHERE case_id=%s AND person_id=%s) OR
            EXISTS(SELECT 1 FROM evidence_people ep JOIN evidence e USING(evidence_id) WHERE e.case_id=%s AND ep.person_id=%s) AS has_records''',
            (case_id, person_id, person_id, case_id, person_id, case_id, person_id))
        if cur.fetchone()['has_records']:
            return api_error('This person has linked timeline, relationship, or evidence records. Remove those links first.', 409)
        cur.execute('DELETE FROM case_persons WHERE case_id=%s AND person_id=%s', (case_id, person_id))
    return jsonify({'ok': True, 'message': 'Person removed from case.'})


def _valid_photo_file(file):
    if not file or not file.filename:
        return None
    safe = secure_filename(file.filename)
    if '.' not in safe:
        return None
    ext = safe.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        return None
    return ext


@app.post('/api/people/<int:person_id>/photo')
def upload_person_photo(person_id):
    photo = request.files.get('photo')
    ext = _valid_photo_file(photo)
    if not ext:
        return api_error('Choose a PNG, JPG, JPEG, or WEBP image.')
    filename = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    relative_path = f'uploads/people/{filename}'
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT photo_path FROM persons WHERE person_id=%s', (person_id,))
            person = cur.fetchone()
            if not person:
                return api_error('Person not found.', 404)
            photo.save(filepath)
            cur.execute('UPDATE persons SET photo_path=%s WHERE person_id=%s', (relative_path, person_id))
        old_path = person['photo_path']
        if old_path:
            old_file = os.path.normpath(os.path.join(app.root_path, 'static', old_path))
            if old_file.startswith(os.path.normpath(UPLOAD_FOLDER) + os.sep) and os.path.isfile(old_file):
                try: os.remove(old_file)
                except OSError: app.logger.warning('Could not remove replaced person photo: %s', old_file)
        return jsonify({'ok': True, 'photo_path': relative_path})
    except Exception:
        if os.path.isfile(filepath):
            try: os.remove(filepath)
            except OSError: pass
        app.logger.exception('Person photo upload failed')
        return api_error('Photo upload failed. Check the Flask log.', 500)


@app.delete('/api/people/<int:person_id>/photo')
def delete_person_photo(person_id):
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT photo_path FROM persons WHERE person_id=%s', (person_id,))
        person = cur.fetchone()
        if not person:
            return api_error('Person not found.', 404)
        cur.execute('UPDATE persons SET photo_path=NULL WHERE person_id=%s', (person_id,))
    old_path = person['photo_path']
    if old_path:
        old_file = os.path.normpath(os.path.join(app.root_path, 'static', old_path))
        if old_file.startswith(os.path.normpath(UPLOAD_FOLDER) + os.sep) and os.path.isfile(old_file):
            try: os.remove(old_file)
            except OSError: app.logger.warning('Could not remove person photo: %s', old_file)
    return jsonify({'ok': True, 'message': 'Person photo removed.'})


@app.get('/api/evidence')
def list_evidence():
    case_id=valid_case_id(request.args.get('case_id'))
    if not case_id: return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT e.evidence_id,e.case_id,e.title,e.description,e.evidence_type,e.verification_status,e.recorded_at,
          COALESCE(json_agg(json_build_object('person_id',p.person_id,'full_name',p.full_name,'involvement',ep.involvement)) FILTER(WHERE p.person_id IS NOT NULL),'[]') linked_people
          FROM evidence e LEFT JOIN evidence_people ep USING(evidence_id) LEFT JOIN persons p USING(person_id)
          WHERE e.case_id=%s GROUP BY e.evidence_id ORDER BY e.recorded_at DESC,e.evidence_id DESC''',(case_id,))
        return jsonify(cur.fetchall())


@app.post('/api/evidence')
def create_evidence():
    data=payload(); case_id=valid_case_id(data.get('case_id'))
    if not case_id: return api_error('A valid case_id is required.')
    try:
        title=required_text(data,'title',150,'Title'); description=required_text(data,'description',10000,'Description')
        evidence_type=required_text(data,'evidence_type',40,'Evidence type').lower().replace(' ','_')
        status=str(data.get('verification_status','unverified') or 'unverified').lower()
        if status not in ('unverified','verified','disputed'): raise ValueError('Status must be unverified, verified, or disputed.')
        linked=data.get('people',[])
        if not isinstance(linked,list): raise ValueError('people must be a list of person IDs.')
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT 1 FROM cases WHERE case_id=%s',(case_id,))
            if not cur.fetchone(): return api_error('Case not found.',404)
            cur.execute('INSERT INTO evidence(case_id,title,description,evidence_type,verification_status) VALUES(%s,%s,%s,%s,%s) RETURNING evidence_id',(case_id,title,description,evidence_type,status)); eid=cur.fetchone()['evidence_id']
            for item in linked:
                pid=int(item.get('person_id') if isinstance(item,dict) else item)
                involvement=(str(item.get('involvement','associated')) if isinstance(item,dict) else 'associated').strip()[:50] or 'associated'
                cur.execute('SELECT 1 FROM case_persons WHERE case_id=%s AND person_id=%s',(case_id,pid))
                if not cur.fetchone(): raise ValueError(f'Person {pid} is not linked to this case.')
                cur.execute('INSERT INTO evidence_people(evidence_id,person_id,involvement) VALUES(%s,%s,%s)',(eid,pid,involvement))
        return jsonify({'ok':True,'evidence_id':eid,'message':'Evidence saved to PostgreSQL.'}),201
    except ValueError as e: return api_error(str(e))
    except (CheckViolation,UniqueViolation,ForeignKeyViolation) as e: return api_error(f'Database constraint: {e.diag.message_primary}')


@app.patch('/api/evidence/<int:evidence_id>')
def update_evidence(evidence_id):
    data=payload(); status=str(data.get('verification_status','')).lower()
    if status not in ('unverified','verified','disputed'): return api_error('Status must be unverified, verified, or disputed.')
    case_id=valid_case_id(data.get('case_id'))
    if not case_id: return api_error('A valid case_id is required.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('UPDATE evidence SET verification_status=%s WHERE evidence_id=%s AND case_id=%s RETURNING evidence_id',(status,evidence_id,case_id))
        row=cur.fetchone()
        if not row: return api_error('Evidence not found in this case.',404)
    return jsonify({'ok':True,'message':f'Evidence marked {status}.'})


@app.delete('/api/evidence/<int:evidence_id>')
def delete_evidence(evidence_id):
    case_id=valid_case_id(request.args.get('case_id'))
    if not case_id: return api_error('A valid case_id is required.')
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute('DELETE FROM evidence WHERE evidence_id=%s AND case_id=%s RETURNING evidence_id',(evidence_id,case_id))
            if not cur.fetchone(): return api_error('Evidence not found in this case.',404)
        return jsonify({'ok':True,'message':'Evidence deleted.'})
    except ForeignKeyViolation:
        return api_error('Cannot delete this evidence because a timeline event cites it. Remove or update the source reference first.',409)


@app.get('/api/relationships')
def list_relationships():
    case_id=valid_case_id(request.args.get('case_id'))
    if not case_id: return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT r.relationship_id,r.person_id,p.full_name person_name,r.related_person_id,p2.full_name related_person,r.relationship_type
          FROM person_relationships r JOIN persons p ON p.person_id=r.person_id JOIN persons p2 ON p2.person_id=r.related_person_id
          WHERE r.case_id=%s ORDER BY p.full_name,p2.full_name''',(case_id,))
        return jsonify(cur.fetchall())


@app.delete('/api/relationships/<int:relationship_id>')
def delete_relationship(relationship_id):
    case_id = valid_case_id(request.args.get('case_id'))
    if not case_id:
        return api_error('A valid case_id is required.')
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            '''DELETE FROM person_relationships
               WHERE relationship_id=%s AND case_id=%s
               RETURNING relationship_id''',
            (relationship_id, case_id)
        )
        deleted = cur.fetchone()
        if not deleted:
            return api_error('Relationship not found in this case.', 404)
    return jsonify({'ok': True, 'message': 'Relationship deleted.'})


@app.post('/api/relationships')
def create_relationship():
    data=payload(); case_id=valid_case_id(data.get('case_id'))
    if not case_id: return api_error('A valid case_id is required.')
    try:
        person_id=int(data.get('person_id')); related_id=int(data.get('related_person_id'))
        relation=required_text(data,'relationship_type',50,'Relationship type')
        if person_id==related_id: raise ValueError('A person cannot be related to themselves.')
        with db() as conn, conn.cursor() as cur:
            for pid in (person_id,related_id):
                cur.execute('SELECT 1 FROM case_persons WHERE case_id=%s AND person_id=%s',(case_id,pid))
                if not cur.fetchone(): raise ValueError(f'Person {pid} is not linked to this case.')
            cur.execute('INSERT INTO person_relationships(case_id,person_id,related_person_id,relationship_type) VALUES(%s,%s,%s,%s) RETURNING relationship_id',(case_id,person_id,related_id,relation))
            rid=cur.fetchone()['relationship_id']
        return jsonify({'ok':True,'relationship_id':rid,'message':'Relationship recorded.'}),201
    except (TypeError,ValueError) as e: return api_error(str(e) or 'Person IDs must be integers.')
    except (CheckViolation,ForeignKeyViolation) as e: return api_error(f'Database constraint: {e.diag.message_primary}')


@app.post('/api/timeline')
def create_timeline_event():
    data=payload(); case_id=valid_case_id(data.get('case_id'))
    if not case_id: return api_error('A valid case_id is required.')
    try:
        person_id=int(data.get('person_id')); event_time=required_text(data,'event_time',40,'Event time')
        description=required_text(data,'description',10000,'Description'); location=required_text(data,'location_name',100,'Location')
        source=data.get('source_evidence_id') or None; verified=bool(data.get('is_verified',False))
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT 1 FROM case_persons WHERE case_id=%s AND person_id=%s',(case_id,person_id))
            if not cur.fetchone(): raise ValueError('Person is not linked to this case.')
            if source:
                cur.execute('SELECT 1 FROM evidence WHERE case_id=%s AND evidence_id=%s',(case_id,int(source)))
                if not cur.fetchone(): raise ValueError('Source evidence must belong to this case.')
            cur.execute('INSERT INTO locations(location_name) VALUES(%s) ON CONFLICT(location_name) DO UPDATE SET location_name=EXCLUDED.location_name RETURNING location_id',(location,)); lid=cur.fetchone()['location_id']
            cur.execute('''INSERT INTO timeline_events(case_id,person_id,location_id,event_time,description,source_evidence_id,is_verified)
              VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING event_id''',(case_id,person_id,lid,event_time,description,source,verified))
            eid=cur.fetchone()['event_id']
        return jsonify({'ok':True,'event_id':eid,'message':'Timeline event recorded.'}),201
    except (TypeError,ValueError) as e: return api_error(str(e) or 'Invalid event data.')
    except (CheckViolation,ForeignKeyViolation) as e: return api_error(f'Database constraint: {e.diag.message_primary}')


@app.get('/api/analysis/paths')
def relationship_paths():
    case_id=valid_case_id(request.args.get('case_id'))
    try: start=int(request.args.get('from_person')); target=int(request.args.get('to_person')); max_depth=min(8,max(1,int(request.args.get('max_depth',6))))
    except (TypeError,ValueError): return api_error('Provide from_person and to_person integer IDs.')
    if not case_id: return api_error('Invalid case ID.')
    with db() as conn, conn.cursor() as cur:
        cur.execute('''WITH RECURSIVE edges(a,b,relationship_type) AS (
          SELECT person_id,related_person_id,relationship_type FROM person_relationships WHERE case_id=%s
          UNION ALL SELECT related_person_id,person_id,relationship_type FROM person_relationships WHERE case_id=%s
        ), paths(node,path,labels,depth) AS (
          SELECT %s::int, ARRAY[%s::int], ARRAY[]::text[], 0
          UNION ALL SELECT e.b, p.path || e.b, p.labels || e.relationship_type, p.depth+1
          FROM paths p JOIN edges e ON e.a=p.node WHERE p.depth<%s AND NOT e.b=ANY(p.path)
        ) SELECT path,labels,depth FROM paths WHERE node=%s ORDER BY depth LIMIT 1''',(case_id,case_id,start,start,max_depth,target))
        result=cur.fetchone()
        if not result: return jsonify({'found':False,'message':'No relationship path found within the selected depth.'})
        cur.execute('SELECT person_id,full_name FROM persons WHERE person_id=ANY(%s)',(result['path'],)); names={r['person_id']:r['full_name'] for r in cur.fetchall()}
        return jsonify({'found':True,'depth':result['depth'],'path':result['path'],'names':[names.get(pid,f'Person {pid}') for pid in result['path']],'relationships':result['labels']})


@app.get('/api/health')
def health():
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT current_database() AS database, current_user AS username, version() AS version')
            info=cur.fetchone()
        return jsonify({'ok':True,**info})
    except (psycopg.OperationalError, DatabaseNotConfigured) as e:
        return api_error('PostgreSQL connection failed. Check DATABASE_URL in this terminal window.',503)


from game_routes import game_bp
app.register_blueprint(game_bp)

from advanced_features import advanced_bp
app.register_blueprint(advanced_bp)


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1')
