-- Q1: What is our overall call center operational baseline (answer/abandon rates, ASA, AHT, FCR, and CSAT)?
SELECT 
    COUNT(*) AS total_calls,
    SUM(CASE WHEN answered = 'Y' THEN 1 ELSE 0 END) AS answered_calls,
    ROUND(100.0 * SUM(CASE WHEN answered = 'Y' THEN 1 ELSE 0 END) / COUNT(*), 2) AS answer_rate,
    ROUND(100.0 * SUM(CASE WHEN answered = 'N' THEN 1 ELSE 0 END) / COUNT(*), 2) AS abandon_rate,
    ROUND(AVG(speed_of_answer_sec)::numeric, 2) AS avg_asa_sec,
    ROUND(AVG(talk_duration_sec)::numeric, 2) AS avg_aht_sec,
    ROUND(100.0 * SUM(CASE WHEN resolved = 'Y' THEN 1 ELSE 0 END) / SUM(CASE WHEN answered = 'Y' THEN 1 ELSE 0 END), 2) AS fcr_rate,
    ROUND(AVG(satisfaction_rating)::numeric, 2) AS avg_csat
FROM fact_calls;


-- Q2a: Which hours of the day experience the highest call volume?
SELECT 
    hour_of_day,
    COUNT(*) AS total_calls,
    SUM(CASE WHEN answered = 'N' THEN 1 ELSE 0 END) AS abandoned_calls,
    ROUND(100.0 * SUM(CASE WHEN answered = 'N' THEN 1 ELSE 0 END) / COUNT(*), 2) AS abandon_rate
FROM fact_calls
GROUP BY hour_of_day
ORDER BY total_calls DESC;


-- Q2b: Which day-and-hour slots exceed our 20% critical abandonment threshold? (min. 50 calls)
SELECT 
    day_of_week,
    hour_of_day,
    COUNT(*) AS total_calls,
    SUM(CASE WHEN answered = 'N' THEN 1 ELSE 0 END) AS abandoned_calls,
    ROUND(100.0 * SUM(CASE WHEN answered = 'N' THEN 1 ELSE 0 END) / COUNT(*), 2) AS abandon_rate
FROM fact_calls
GROUP BY day_of_week, hour_of_day
HAVING COUNT(*) >= 50 
   AND ROUND(100.0 * SUM(CASE WHEN answered = 'N' THEN 1 ELSE 0 END) / COUNT(*), 2) > 20
ORDER BY abandon_rate DESC;


-- Q3: Which call topics struggle most with SLA compliance and unresolved issues?
SELECT 
    t.topic_name,
    t.sla_target_sec,
    COUNT(*) AS answered_calls,
    ROUND(AVG(f.speed_of_answer_sec)::numeric, 2) AS avg_asa_sec,
    ROUND(100.0 * SUM(CASE WHEN f.speed_of_answer_sec <= t.sla_target_sec THEN 1 ELSE 0 END) / COUNT(*), 2) AS sla_compliance,
    ROUND(100.0 * SUM(CASE WHEN f.resolved = 'N' THEN 1 ELSE 0 END) / COUNT(*), 2) AS unresolved_rate
FROM fact_calls f
JOIN dim_topics t ON f.topic_id = t.topic_id
WHERE f.answered = 'Y'
GROUP BY t.topic_name, t.sla_target_sec
ORDER BY sla_compliance ASC;


-- Q4: How do individual agents rank on overall CSAT?
WITH agent_summary AS (
    SELECT 
        a.agent_name,
        a.team_shift,
        COUNT(*) AS answered_calls,
        ROUND(AVG(f.speed_of_answer_sec)::numeric, 2) AS avg_asa_sec,
        ROUND(AVG(f.talk_duration_sec)::numeric, 2) AS avg_aht_sec,
        ROUND(100.0 * SUM(CASE WHEN f.resolved = 'Y' THEN 1 ELSE 0 END) / COUNT(*), 2) AS fcr_rate,
        AVG(f.satisfaction_rating) AS avg_csat_raw
    FROM fact_calls f
    JOIN dim_agents a ON f.agent_id = a.agent_id
    WHERE f.answered = 'Y'
    GROUP BY a.agent_name, a.team_shift
)
SELECT 
    agent_name,
    team_shift,
    answered_calls,
    avg_asa_sec,
    avg_aht_sec,
    fcr_rate,
    ROUND(avg_csat_raw::numeric, 2) AS avg_csat,
    RANK() OVER (ORDER BY avg_csat_raw DESC) AS csat_rank
FROM agent_summary
ORDER BY csat_rank ASC;


-- Q5: Which 5 agent-topic pairs have the lowest CSAT and need targeted coaching?
SELECT 
    a.agent_name,
    t.topic_name,
    COUNT(*) AS answered_calls,
    ROUND(100.0 * SUM(CASE WHEN f.resolved = 'Y' THEN 1 ELSE 0 END) / COUNT(*), 2) AS fcr_rate,
    ROUND(AVG(f.satisfaction_rating)::numeric, 2) AS avg_csat
FROM fact_calls f
JOIN dim_agents a ON f.agent_id = a.agent_id
JOIN dim_topics t ON f.topic_id = t.topic_id
WHERE f.answered = 'Y'
GROUP BY a.agent_name, t.topic_name
ORDER BY avg_csat ASC, fcr_rate ASC
LIMIT 5;


-- Q6: Does longer wait time hurt customer satisfaction (CSAT)?
SELECT 
    CASE 
        WHEN speed_of_answer_sec <= 30 THEN '0-30s'
        WHEN speed_of_answer_sec <= 60 THEN '31-60s'
        WHEN speed_of_answer_sec <= 90 THEN '61-90s'
        ELSE '90s+'
    END AS wait_time_group,
    COUNT(*) AS answered_calls,
    ROUND(AVG(satisfaction_rating)::numeric, 2) AS avg_csat,
    ROUND(AVG(talk_duration_sec)::numeric, 2) AS avg_aht_sec
FROM fact_calls
WHERE answered = 'Y'
GROUP BY wait_time_group
ORDER BY wait_time_group;


-- Q7: How stable are service quality and abandonment rates across months?
SELECT 
    DATE_TRUNC('month', call_date::date)::date AS call_month,
    COUNT(*) AS total_calls,
    SUM(CASE WHEN answered = 'N' THEN 1 ELSE 0 END) AS abandoned_calls,
    ROUND(100.0 * SUM(CASE WHEN answered = 'N' THEN 1 ELSE 0 END) / COUNT(*), 2) AS abandon_rate,
    ROUND(AVG(speed_of_answer_sec)::numeric, 2) AS avg_asa_sec,
    ROUND(AVG(satisfaction_rating)::numeric, 2) AS avg_csat
FROM fact_calls
GROUP BY call_month
ORDER BY call_month ASC;


-- Q8: Is workload and service quality balanced across Morning and Afternoon shifts?
SELECT 
    a.team_shift,
    COUNT(*) AS total_calls,
    SUM(CASE WHEN f.answered = 'Y' THEN 1 ELSE 0 END) AS answered_calls,
    ROUND(100.0 * SUM(CASE WHEN f.answered = 'N' THEN 1 ELSE 0 END) / COUNT(*), 2) AS abandon_rate,
    ROUND(AVG(f.speed_of_answer_sec)::numeric, 2) AS avg_asa_sec,
    ROUND(AVG(f.talk_duration_sec)::numeric, 2) AS avg_aht_sec,
    ROUND(100.0 * SUM(CASE WHEN f.resolved = 'Y' THEN 1 ELSE 0 END) / SUM(CASE WHEN f.answered = 'Y' THEN 1 ELSE 0 END), 2) AS fcr_rate,
    ROUND(AVG(f.satisfaction_rating)::numeric, 2) AS avg_csat
FROM fact_calls f
JOIN dim_agents a ON f.agent_id = a.agent_id
GROUP BY a.team_shift
ORDER BY total_calls DESC;

