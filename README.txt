CASEGRAPH — FUNCTIONAL DBMS PROJECT BUILD

This build prioritizes real database workflows and analysis over UI redesign.

CONTENTS
- app.py: Flask app, PostgreSQL-backed CRUD APIs, validation, health endpoint, conflict analysis, recursive relationship path finder.
- templates/index.html / static/: dashboard and working controls.
- seed_demo.py: creates a complete fictional investigation case once; safe to run repeatedly and never drops/resets data.
- dbms_demo_queries.sql: demonstration queries for joins, aggregation, HAVING, recursive CTE, contradiction detection, integrity check, and transaction/rollback.
- schema.sql: schema export supplied with your project. Do not rerun it on an existing database unless you intend to restore the schema separately.

DATABASE CONNECTION (PowerShell)
Set DATABASE_URL in the same PowerShell window used to start Flask. For a password containing @, encode it as %40 in the URL.
Example only:
$env:DATABASE_URL = "postgresql://postgres:YOUR_URL_ENCODED_PASSWORD@localhost:5432/casegraph"

SEED THE FICTIONAL CASE
1. Open PowerShell in this project directory.
2. Set DATABASE_URL as above.
3. Run: python seed_demo.py
4. It creates "The Missing Prototype — Complete Demonstration Case" with five people, six evidence records, six relationship edges, and eight timeline events. One deliberate conflict places Rahul Sharma in the Applied Systems Lab and University Library at the exact same verified timestamp. The case and all people/events are fictional.
5. Running it again detects the case title and avoids duplicating the demo records.

RUN APP
python app.py
Open http://127.0.0.1:5000 and select the new demo case from the case selector.

FUNCTIONALITY
- PostgreSQL-backed case dashboard and case selector.
- Add people, add evidence (optional person links), change evidence verification status, delete evidence with foreign-key protection.
- Add timeline events with location and optional source evidence; validates case membership.
- Add relationship edges and find a shortest recorded path using a recursive CTE.
- Relationship graph, timeline, global search, strict/potential conflict analysis, and print-ready report use database records.
- /api/health reports database connection status.

API QUICK REFERENCE
GET  /api/health
GET  /api/cases
GET  /api/dashboard?case_id=ID
GET  /api/people?case_id=ID
POST /api/people                 JSON: case_id, full_name, occupation, role
GET  /api/evidence?case_id=ID
POST /api/evidence               JSON: case_id, title, description, evidence_type, verification_status, people:[{person_id,involvement}]
PATCH /api/evidence/ID           JSON: case_id, verification_status
DELETE /api/evidence/ID?case_id=ID
GET  /api/relationships?case_id=ID
POST /api/relationships          JSON: case_id, person_id, related_person_id, relationship_type
GET  /api/timeline?case_id=ID
POST /api/timeline               JSON: case_id, person_id, event_time, location_name, description, source_evidence_id, is_verified
GET  /api/analysis/paths?case_id=ID&from_person=ID&to_person=ID&max_depth=6
GET  /api/contradictions?case_id=ID
GET  /api/report?case_id=ID

DBMS DEMO CHECKLIST
1. Show schema.sql / ER diagram and explain PKs, FKs, CHECK constraints, and junction tables.
2. Add a person and evidence in the app; refresh and show it persists.
3. Change evidence verification status; show conflict analysis updates as applicable.
4. Add a timeline event with a source evidence record.
5. Add a relationship and use Find path to demonstrate recursive SQL.
6. Run dbms_demo_queries.sql in pgAdmin or psql to demonstrate JOIN, LEFT JOIN, GROUP BY/HAVING, recursive CTE, contradiction detection, and rollback.
7. Explain that the conflict detector finds a data inconsistency; it does not prove guilt or determine which account is true.

SAFETY / LIMITATIONS
- Fictional training data only. Do not enter real personal or sensitive data.
- No operation drops tables or resets the existing database.
- Cases and people are not deleted by the UI, to avoid accidental loss of linked records.
- This is a local educational Flask development server, not a production deployment.
- A record marked verified is a user-entered status; the app does not independently authenticate evidence.


PERSON AVATARS AND PHOTO UPLOAD
1. Back up your project folder.
2. Open pgAdmin, select the existing casegraph database, open Query Tool, and run gender_photo_migration.sql once. This adds nullable gender/photo_path columns and preserves existing data.
3. Install dependencies already listed in your project's setup (Flask and psycopg).
4. Set DATABASE_URL as you normally do, then run: python app.py
5. Open People and select a person. Use Upload / Change Photo or Remove Photo in the dossier. New or edited people can use male, female, or blank gender; blank shows initials. A custom photo overrides the default avatar.
Photos are stored under static/uploads/people; the database stores only their relative paths. Upload limit is 5 MB.
