-- ============================================================================
-- overdue_assignments.sql
-- Question: Which students have overdue assignments, and how many?
-- ----------------------------------------------------------------------------
-- Overdue = (NOT is_upcoming) AND submission_state = 'missing'. That is, the
-- due date has passed (relative to the fixed reference date) AND the student
-- never submitted. A *late* submission is NOT overdue - it was eventually
-- handed in, so it is reported separately (submission_state = 'late').
--
-- Output: one row per student with their overdue count and the list of
-- overdue assignment ids / titles.
--
-- Source: silver.student_assignment_fact  joined to  silver.students
--         (for the student's name).
-- ============================================================================
SELECT
    f.student_id,
    s.name,
    f.student_program                           AS program,
    f.student_status                            AS status,
    COUNT(*)                                    AS overdue_count,
    LIST(f.assignment_id ORDER BY f.assignment_id) AS overdue_assignment_ids,
    LIST(f.title        ORDER BY f.assignment_id) AS overdue_assignment_titles,
    MIN(f.due_date)                             AS earliest_overdue_due
FROM fact f
JOIN students s ON s.student_id = f.student_id
WHERE f.is_overdue
GROUP BY f.student_id, s.name, f.student_program, f.student_status
ORDER BY overdue_count DESC, f.student_id;
