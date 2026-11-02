-- ============================================================================
-- missing_submissions.sql
-- Question: Which students are missing Assignment_101?
-- ----------------------------------------------------------------------------
-- "Missing" = an *eligible* student (their program matches the course's
-- program) who has no submission row for the assignment. Assignment_101
-- belongs to course 1 (Data Science), so only DS students are eligible.
--
-- `student_status` is returned for governance / downstream filtering
-- (e.g., excluding inactive students) rather than silently dropping rows.
--
-- Source: silver.student_assignment_fact (one row per eligible
--         student-assignment pair, LEFT JOINed to submissions).
-- ============================================================================
SELECT
    student_id,
    name,
    email,
    student_program       AS program,
    student_status        AS status,
    cohort,
    course_id,
    assignment_id,
    title                 AS assignment_title,
    due_date,
    submission_state
FROM fact
WHERE assignment_id = 101
  AND submission_state = 'missing'
ORDER BY student_id;
