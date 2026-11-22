"""Seed a complete fictional CaseGraph investigation. Safe to run repeatedly.
Uses DATABASE_URL from the environment; does not drop or reset existing data."""
import os
import psycopg
from psycopg.rows import dict_row

from db import database_url
DB = database_url()
CASE_TITLE = 'The Missing Prototype — Complete Demonstration Case'

with psycopg.connect(DB, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute('SELECT case_id FROM cases WHERE title=%s', (CASE_TITLE,))
    existing = cur.fetchone()
    if existing:
        print(f'Demo case already exists (case_id={existing["case_id"]}); no duplicate data added.')
        raise SystemExit(0)

    cur.execute('''INSERT INTO cases(title,description,status) VALUES(%s,%s,'investigating') RETURNING case_id''', (
        CASE_TITLE,
        'A prototype sensor module disappeared from the Northbridge University Applied Systems Lab on 23 October 2026. This fictional training case combines access records, witness statements, messages, and timeline analysis. All people and events are invented.'
    ))
    case_id = cur.fetchone()['case_id']

    people_data = [
        ('Rahul Sharma','Prototype Researcher','suspect'),
        ('Priya Mehta','Laboratory Assistant','suspect'),
        ('Arjun Verma','Campus Security Guard','witness'),
        ('Neha Kapoor','Research Intern','witness'),
        ('Dr. Kavita Rao','Principal Investigator','investigator'),
    ]
    people = {}
    for name, occupation, role in people_data:
        cur.execute('INSERT INTO persons(full_name,occupation) VALUES(%s,%s) RETURNING person_id',(name,occupation))
        pid=cur.fetchone()['person_id']; people[name]=pid
        cur.execute('INSERT INTO case_persons(case_id,person_id,role) VALUES(%s,%s,%s)',(case_id,pid,role))

    evidence_data = [
        ('Research Lab Access Log','Electronic access log records Rahul Sharma entering the lab at 20:00. The export was obtained from the building access system.','access_log','verified',['Rahul Sharma']),
        ('Library Witness Statement','Neha Kapoor states that she saw Rahul Sharma in the library at 20:00. Statement is recorded, but the account has not been independently corroborated.','statement','verified',['Neha Kapoor','Rahul Sharma']),
        ('Main Entrance Keycard Record','A keycard registered to the shared lab pool was used at the main entrance at 19:42. The card holder is not established by this record alone.','access_log','unverified',['Priya Mehta']),
        ('Message Exchange: Prototype Transfer','A fictional message exchange discusses moving a test unit after closing. Context and authorship require review.','message','verified',['Priya Mehta','Arjun Verma']),
        ('Inventory Photograph','A signed inventory photograph from 17:30 shows the prototype inside cabinet B-04 before the reported disappearance.','photograph','verified',['Dr. Kavita Rao']),
        ('Maintenance Note','A maintenance note records that the cabinet sensor was intermittently offline that evening.','document','disputed',['Arjun Verma']),
    ]
    evidence={}
    for title,desc,kind,status,names in evidence_data:
        cur.execute('''INSERT INTO evidence(case_id,title,description,evidence_type,verification_status)
          VALUES(%s,%s,%s,%s,%s) RETURNING evidence_id''',(case_id,title,desc,kind,status))
        eid=cur.fetchone()['evidence_id']; evidence[title]=eid
        for name in names:
            cur.execute('INSERT INTO evidence_people(evidence_id,person_id,involvement) VALUES(%s,%s,%s)',(eid,people[name],'mentioned / associated'))

    relation_data=[
        ('Rahul Sharma','Priya Mehta','worked with'),
        ('Priya Mehta','Arjun Verma','messaged'),
        ('Arjun Verma','Neha Kapoor','witnessed conversation with'),
        ('Rahul Sharma','Neha Kapoor','research colleague'),
        ('Dr. Kavita Rao','Rahul Sharma','supervisor of'),
        ('Dr. Kavita Rao','Priya Mehta','supervisor of'),
    ]
    for a,b,kind in relation_data:
        cur.execute('INSERT INTO person_relationships(case_id,person_id,related_person_id,relationship_type) VALUES(%s,%s,%s,%s)',(case_id,people[a],people[b],kind))

    location_names=['Applied Systems Lab','University Library','Main Entrance','Research Office','Security Desk']
    locations={}
    for name in location_names:
        cur.execute('INSERT INTO locations(location_name) VALUES(%s) ON CONFLICT(location_name) DO UPDATE SET location_name=EXCLUDED.location_name RETURNING location_id',(name,))
        locations[name]=cur.fetchone()['location_id']

    events=[
        ('2026-10-23 17:30:00','Dr. Kavita Rao','Research Office','Inventory check: prototype is documented in cabinet B-04.',evidence['Inventory Photograph'],True),
        ('2026-10-23 19:42:00','Priya Mehta','Main Entrance','A shared pool keycard is recorded at the main entrance.',evidence['Main Entrance Keycard Record'],False),
        ('2026-10-23 19:55:00','Arjun Verma','Security Desk','Guard notes the cabinet sensor status is intermittent.',evidence['Maintenance Note'],False),
        ('2026-10-23 20:00:00','Rahul Sharma','Applied Systems Lab','Electronic access log records entry to the lab.',evidence['Research Lab Access Log'],True),
        ('2026-10-23 20:00:00','Rahul Sharma','University Library','Witness statement places Rahul in the library at the same timestamp.',evidence['Library Witness Statement'],True),
        ('2026-10-23 20:05:00','Neha Kapoor','University Library','Neha records seeing Rahul near the library reading area.',evidence['Library Witness Statement'],False),
        ('2026-10-23 20:12:00','Priya Mehta','Applied Systems Lab','Message context suggests a possible after-hours transfer; location is not independently confirmed.',evidence['Message Exchange: Prototype Transfer'],False),
        ('2026-10-23 20:30:00','Arjun Verma','Applied Systems Lab','End-of-shift check notes prototype is missing from cabinet B-04.',evidence['Maintenance Note'],False),
    ]
    for when,person,loc,desc,source,verified in events:
        cur.execute('''INSERT INTO timeline_events(case_id,person_id,location_id,event_time,description,source_evidence_id,is_verified)
          VALUES(%s,%s,%s,%s,%s,%s,%s)''',(case_id,people[person],locations[loc],when,desc,source,verified))

    print(f'Created fictional demo case case_id={case_id}')
    print(f'People: {len(people_data)} | Evidence: {len(evidence_data)} | Relationships: {len(relation_data)} | Timeline events: {len(events)}')
    print('Expected analysis: 1 confirmed exact-time location conflict for Rahul Sharma at 20:00.')
