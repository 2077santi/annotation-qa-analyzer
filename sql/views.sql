-- QA data model. Raw CSVs are loaded as tables: items, labels, gold, annotators.

-- How many votes each label got on each item.
CREATE OR REPLACE VIEW item_votes AS
SELECT item_id, label, COUNT(*) AS votes
FROM labels
GROUP BY item_id, label;

-- Majority label per item and how strong the majority is (agreement = share of raters).
CREATE OR REPLACE VIEW item_consensus AS
WITH ranked AS (
    SELECT
        item_id,
        label,
        votes,
        SUM(votes) OVER (PARTITION BY item_id) AS raters,
        RANK() OVER (PARTITION BY item_id ORDER BY votes DESC) AS rnk,
        COUNT(*) OVER (PARTITION BY item_id, votes) AS tied
    FROM item_votes
)
SELECT
    r.item_id,
    i.week,
    i.edge_case,
    CASE WHEN r.tied = 1 THEN r.label END AS majority_label,  -- NULL on a tie
    r.votes AS majority_votes,
    r.votes::DOUBLE / r.raters AS agreement
FROM ranked r
JOIN items i USING (item_id)
WHERE r.rnk = 1
QUALIFY ROW_NUMBER() OVER (PARTITION BY r.item_id ORDER BY r.label) = 1;

-- Leave-one-out reference: for each label, the majority of the OTHER raters.
-- Judging an annotator against a consensus that includes their own vote would flatter them.
CREATE OR REPLACE VIEW label_reference AS
WITH others AS (
    SELECT
        l.label_id,
        v.label AS candidate,
        v.votes - CASE WHEN v.label = l.label THEN 1 ELSE 0 END AS other_votes
    FROM labels l
    JOIN item_votes v USING (item_id)
),
ranked AS (
    SELECT
        label_id,
        candidate,
        other_votes,
        RANK() OVER (PARTITION BY label_id ORDER BY other_votes DESC) AS rnk,
        COUNT(*) OVER (PARTITION BY label_id, other_votes) AS tied
    FROM others
    WHERE other_votes > 0
)
SELECT
    l.*,
    i.week,
    i.edge_case,
    r.candidate AS reference_label,
    l.label = r.candidate AS agrees
FROM labels l
JOIN items i USING (item_id)
JOIN ranked r USING (label_id)
WHERE r.rnk = 1 AND r.tied = 1 AND r.other_votes >= 3;  -- at least 3 of the 4 others agree

-- Weekly scorecard per annotator.
CREATE OR REPLACE VIEW annotator_weekly AS
SELECT
    annotator_id,
    week,
    COUNT(*) AS labels_scored,
    AVG(agrees::INT) AS agreement_rate,
    AVG(handle_time_sec) AS avg_handle_time_sec
FROM label_reference
GROUP BY annotator_id, week;

-- Accuracy against the expert gold set.
CREATE OR REPLACE VIEW annotator_gold AS
SELECT
    l.annotator_id,
    COUNT(*) AS gold_labels,
    AVG((l.label = g.gold_label)::INT) AS gold_accuracy
FROM labels l
JOIN gold g USING (item_id)
GROUP BY l.annotator_id;

-- How each annotator's labels map against the reference (for bias detection).
CREATE OR REPLACE VIEW annotator_confusion AS
SELECT annotator_id, reference_label, label, COUNT(*) AS n
FROM label_reference
GROUP BY annotator_id, reference_label, label;
