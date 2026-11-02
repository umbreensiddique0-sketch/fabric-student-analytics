-- ============================================================================
-- course_submission_rates.sql
-- Question: What is the submission rate per course?
-- ----------------------------------------------------------------------------
-- Denominator (the "eligible-student denominator") = eligible
-- student-assignment pairs that are DUE as of the reference date, i.e.
-- eligible_students x assignments_due. Upcoming assignments (due on/after
-- the reference date) are excluded - a student cannot be expected to have
-- submitted something that is not yet due.
--
-- Numerator = pairs that were actually submitted (on_time or late). Missing
-- pairs lower the rate.
--
-- Source: silver.student_assignment_fact  joined to  silver.courses
--         (for course_name / program labels).
-- ============================================================================
SELECT
    f.course_id,
    c.course_name,
    c.program,
    COUNT(DISTINCT f.student_id)  AS eligible_students,
    COUNT(DISTINCT f.assignment_id) AS assignments_due,
    COUNT(*)                       AS eligible_pairs,
    CAST(SUM(CASE WHEN f.submission_state IN ('on_time', 'late')
             THEN 1 ELSE 0 END) AS BIGINT) AS submitted_pairs,
    ROUND(
        100.0 *
        SUM(CASE WHEN f.submission_state IN ('on_time', 'late')
                 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0),
        2
    ) AS submission_rate_pct
FROM fact f
JOIN courses c ON c.course_id = f.course_id
WHERE NOT f.is_upcoming
GROUP BY f.course_id, c.course_name, c.program
ORDER BY f.course_id;
