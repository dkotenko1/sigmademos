-- One row per product: the base book the scenario modeler cross-joins against.
--
-- This has to be genuinely one row per product, NOT a grouped view over the
-- monthly loan book. A cross join operates on the underlying rows, so joining a
-- grouped 144-row table replicates each product once per month and inflates
-- every downstream sum by 24x.
--
-- Re-derives from the same constants as loan_book.sql, aggregated over the
-- trailing twelve months, so the two agree.
--
-- The state fan-out is NOT optional here, even though this table has no state
-- column. loan_book.sql scales every product by `state_share * (1 + tilt)` and
-- sums across the footprint, and FOOTPRINTS shares deliberately do NOT sum to
-- 1.0 (they are a partial footprint -- 0.920 for SimplifyVMS). Omitting the
-- fan-out therefore inflated this baseline by 1/sum(share) -- ~8.7% here --
-- so page 2 opened on a "Baseline net recovered" that disagreed with page 1's
-- headline for the same metric. Cross joining states and then grouping by
-- product keeps the required ONE ROW PER PRODUCT while reproducing
-- loan_book.sql's arithmetic exactly, tilt included.
WITH product AS (
__PRODUCTS__
),
states AS (
__STATES__
),
months AS (
    SELECT DATEADD('month', SEQ4(), DATE '2024-08-01') AS period_month,
           SEQ4() AS month_index
    FROM TABLE(GENERATOR(ROWCOUNT => 24))
),
monthly AS (
    SELECT
        p.product, p.product_order, m.month_index,
        -- identical expressions to loan_book.sql, including the deterministic
        -- per-state tilt, so the two cannot drift
        ROUND(p.bal_base * g.state_share
              * (1 + (MOD(ABS(HASH(g.state || p.product)), 21) - 10) / 100.0)
              * POWER(1 + p.annual_growth / 12, m.month_index)
              * (1 + 0.035 * SIN(2 * PI() * (m.month_index / 12.0) + p.phase)), 4) AS bal,
        ROUND(p.fee_base * g.state_share
              * (1 + (MOD(ABS(HASH(g.state || p.product)), 21) - 10) / 100.0)
              * POWER(1 + p.annual_growth / 12, m.month_index)
              * (1 + 0.035 * SIN(2 * PI() * (m.month_index / 12.0) + p.phase))
              * CASE WHEN p.product = 'Home Loans' AND MONTH(m.period_month) IN (4,5,6) THEN 1.180
                     WHEN p.product = 'Credit Card' AND MONTH(m.period_month) IN (11,12) THEN 1.140
                     ELSE 1.0 END, 5) AS fee,
        p.yield_rate,
        CASE WHEN p.funding_rate > 0
             THEN p.funding_rate - 0.0045 * (m.month_index / 23.0) ELSE 0 END AS funding_eff
    FROM product p CROSS JOIN months m CROSS JOIN states g
    WHERE m.month_index >= 12          -- trailing twelve months
)
SELECT
    product                                                     AS "Product",
    MIN(product_order)                                          AS "Product Order",
    -- 6dp, not 0dp. At whole-$MM precision a company whose spread sits in the
    -- low teens of $MM had every channel quantised by 10-25% (SimplifyVMS's six
    -- channels rounded to 6/3/2/2/1/1 and summed to a baseline 12% above the
    -- real figure). Same class of bug as the product-card NUMBER(12,2)
    -- collision.
    CAST(ROUND(SUM(bal * yield_rate / 12 - bal * funding_eff / 12 + fee), 6)
         AS NUMBER(18,6))                                       AS "Revenue",
    -- SUM over states then AVG over months: AVG(bal) straight over the
    -- month x state grain would return a per-state mean, i.e. ~1/15th of the
    -- book.
    CAST(ROUND(SUM(bal) / COUNT(DISTINCT month_index), 6)
         AS NUMBER(18,6))                                       AS "Balances",
    CAST(ROUND(AVG(yield_rate) * 100, 2) AS NUMBER(6,2))        AS "Yield Pct",
    CAST(ROUND(AVG(funding_eff) * 100, 2) AS NUMBER(6,2))       AS "Funding Pct"
FROM monthly
GROUP BY product
