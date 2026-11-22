-- CaseGraph DBMS demonstration queries (PostgreSQL)
-- Run after seed_demo.py. These are read-only examples except the explicitly marked transaction.

-- 1. INNER JOIN: people linked to a case and their roles
SELECT c.title, p.full_name, p.occupation, cp.role
FROM cases c
JOIN case_persons cp ON cp.case_id = c.case_id
JOIN persons p ON p.person_id = cp.person_id
WHERE c.title = 'The Missing Prototype — Complete Demonstration Case'
ORDER BY cp.role, p.full_name;

-- 2. LEFT JOIN + aggregation: evidence and number of linked people
SELECT e.title, e.evidence_type, e.verification_status,
       COUNT(ep.person_id) AS linked_people
FROM cases c
JOIN evidence e ON e.case_id = c.case_id
LEFT JOIN evidence_people ep ON ep.evidence_id = e.evidence_id
WHERE c.title = 'The Missing Prototype — Complete Demonstration Case'
GROUP BY e.evidence_id
ORDER BY e.recorded_at;

-- 3. GROUP BY / HAVING: people connected to at least two evidence items
SELECT p.full_name, COUNT(DISTINCT ep.evidence_id) AS evidence_count
FROM cases c
JOIN case_persons cp ON cp.case_id = c.case_id
JOIN persons p ON p.person_id = cp.person_id
JOIN evidence_people ep ON ep.person_id = p.person_id
JOIN evidence e ON e.evidence_id = ep.evidence_id AND e.case_id = c.case_id
WHERE c.title = 'The Missing Prototype — Complete Demonstration Case'
GROUP BY p.person_id, p.full_name
HAVING COUNT(DISTINCT ep.evidence_id) >= 2
ORDER BY evidence_count DESC;

-- 4. Recursive CTE: discover people reachable through recorded relationships
WITH RECURSIVE case_edges AS (
  SELECT r.case_id, r.person_id AS source_id, r.related_person_id AS target_id, r.relationship_type
  FROM person_relationships r JOIN cases c ON c.case_id=r.case_id
  WHERE c.title = 'The Missing Prototype — Complete Demonstration Case'
  UNION ALL
  SELECT r.case_id, r.related_person_id, r.person_id, r.relationship_type
  FROM person_relationships r JOIN cases c ON c.case_id=r.case_id
  WHERE c.title = 'The Missing Prototype — Complete Demonstration Case'
), walk(node, path, depth) AS (
  SELECT cp.person_id, ARRAY[cp.person_id], 0
  FROM case_persons cp JOIN cases c ON c.case_id=cp.case_id
  WHERE c.title = 'The Missing Prototype — Complete Demonstration Case'
    AND (SELECT p.full_name FROM persons p WHERE p.person_id=cp.person_id) = 'Rahul Sharma'
  UNION ALL
  SELECT e.target_id, w.path || e.target_id, w.depth+1
  FROM walk w JOIN case_edges e ON e.source_id=w.node
  WHERE w.depth < 6 AND NOT e.target_id = ANY(w.path)
)
SELECT w.depth, p.full_name, w.path
FROM walk w JOIN persons p ON p.person_id=w.node
ORDER BY w.depth, p.full_name;

-- 5. Conflict detection: same person, exact same timestamp, different locations, both verified
SELECT p.full_name, a.event_time,
       la.location_name AS location_a, lb.location_name AS location_b,
       a.description AS account_a, b.description AS account_b
FROM timeline_events a
JOIN timeline_events b ON b.person_id=a.person_id AND b.event_id>a.event_id
  AND b.event_time=a.event_time AND b.location_id<>a.location_id
JOIN persons p ON p.person_id=a.person_id
JOIN locations la ON la.location_id=a.location_id
JOIN locations lb ON lb.location_id=b.location_id
JOIN cases c ON c.case_id=a.case_id
WHERE a.case_id=b.case_id AND c.title='The Missing Prototype — Complete Demonstration Case'
  AND a.is_verified AND b.is_verified;

-- 6. Referential integrity check: timeline source evidence must belong to the same case
SELECT t.event_id, t.case_id, t.source_evidence_id, e.case_id AS evidence_case_id
FROM timeline_events t JOIN evidence e ON e.evidence_id=t.source_evidence_id
WHERE t.case_id <> e.case_id;
-- Expected result: zero rows. The app validates this before insertion.

-- 7. Transaction example (safe rollback demonstration): no data remains after ROLLBACK.
BEGIN;
UPDATE evidence SET verification_status='disputed'
WHERE evidence_id = -999999; -- intentionally matches no record
SELECT COUNT(*) AS still_valid_statuses FROM evidence
WHERE verification_status IN ('unverified','verified','disputed');
ROLLBACK;
