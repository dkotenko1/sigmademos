-- SoFi loan book & fee businesses: 6 product lines x 24 months.
-- Pure generated SQL (no source tables) so it compiles on any Snowflake
-- connection. Amounts in $MM. Calibrated to SoFi's real scale: ~$3.5-3.9B
-- annual adjusted net revenue, ~$33B average balances, ~14M members.
-- Balance type matters to the economics: only lending products carry an asset
-- yield and a funding cost. SoFi Money holds DEPOSITS -- a funding source, not an
-- earning asset -- so it earns fee/interchange revenue and bears no interest
-- expense of its own; the cheap funding it provides is already reflected in the
-- lending products' low cost of funds. Modelling deposits as a 0%-yield asset
-- would book a large phantom interest expense against them.
WITH product AS (
__PRODUCTS__
),
states AS (
__STATES__
),
months AS (
    -- 24 complete months ending 2026-07
    SELECT DATEADD('month', SEQ4(), DATE '2024-08-01') AS period_month,
           SEQ4() AS month_index
    FROM TABLE(GENERATOR(ROWCOUNT => 24))
),
grid AS (
    SELECT
        p.*,
        g.state,
        g.state_share,
        -- deterministic per-state tilt so each state has its own story
        (MOD(ABS(HASH(g.state || p.product)), 21) - 10) / 100.0 AS state_tilt,
        m.period_month,
        m.month_index,
        POWER(1 + p.annual_growth / 12, m.month_index) AS trend,
        1 + 0.035 * SIN(2 * PI() * (m.month_index / 12.0) + p.phase) AS seasonal,
        -- Home lending is rate-sensitive: originations spike in the spring.
        CASE WHEN p.product = 'Home Loans' AND MONTH(m.period_month) IN (4, 5, 6) THEN 1.180
             WHEN p.product = 'Credit Card' AND MONTH(m.period_month) IN (11, 12) THEN 1.140
             ELSE 1.0 END AS event_factor
    FROM product p CROSS JOIN months m CROSS JOIN states g
),
calc AS (
    SELECT
        product, product_order, balance_type, state, state_tilt, period_month, month_index, delinq_rate,
        yield_rate, funding_rate,
        ROUND(bal_base * state_share * (1 + state_tilt) * trend * seasonal, 4) AS avg_balances,
        ROUND(fee_base * state_share * (1 + state_tilt) * trend * seasonal * event_factor, 5) AS fee_income,
        ROUND(members_base * state_share * POWER(1 + 0.075 / 12, month_index), 0) AS members_k,
        -- Originations run roughly 6% of balances a month for lending products.
        ROUND(bal_base * state_share * 0.060 * trend * seasonal * event_factor, 1) AS originations,
        provision_rate, opex_ratio,
        -- Funding cost eases ~45bps over the two years as rates come down.
        funding_rate - 0.0045 * (month_index / 23.0)            AS funding_eff
    FROM grid
),
fin AS (
    SELECT
        c.*,
        -- 6dp, NOT 2dp. These are per-state-per-month figures in $MM, so
        -- rounding to cents quantises them at $10K. That is immaterial for a
        -- lender whose monthly interest per row runs into the $MMs, but for a
        -- business whose spread rate is 1-3% the per-row figure is only
        -- ~$0.03MM and cents rounding is a 17%-per-row quantum. Measured on
        -- SimplifyVMS's invoice-exception build: it inflated the headline by
        -- +8.5% and distorted individual channels by -30% to +38%, and it was
        -- also why the page-2 modeler baseline could not be reconciled with
        -- the page-1 headline for the same metric.
        ROUND(avg_balances * yield_rate / 12, 6)                        AS interest_income,
        ROUND(avg_balances * funding_eff / 12, 6)                       AS interest_expense,
        ROUND(avg_balances * provision_rate / 12, 6)                    AS provision
    FROM calc c
)
SELECT
    product                                                    AS "Product",
    product_order                                              AS "Product Order",
    balance_type                                               AS "Balance Type",
    state                                                      AS "State",
    ROUND(1 + state_tilt * 1.6, 3)                             AS "Performance Index",
    period_month                                               AS "Period",
    YEAR(period_month)                                         AS "Year",
    'Q' || QUARTER(period_month)                               AS "Quarter",
    CASE WHEN month_index >= 12 THEN 'Current Period'
         ELSE 'Prior Period' END                               AS "Period Name",
    members_k                                                  AS "Members (K)",
    originations                                               AS "Originations",
    avg_balances                                               AS "Avg Balances",
    interest_income                                            AS "Interest Income",
    interest_expense                                           AS "Interest Expense",
    -- 6dp throughout, for the same reason the `fin` CTE uses it: these are
    -- per-state-per-month $MM figures, so cents rounding quantises them at
    -- $10K. Raising precision only in `fin` was not enough -- this second
    -- rounding layer re-quantised the very columns the KPIs and the ranked
    -- table read, and it is what kept the lowest-spread channel (Direct
    -- Sourcing, $0.82M real) reporting $0.50M on page 1. Display formatting,
    -- not storage, is where rounding belongs.
    ROUND(interest_income - interest_expense, 6)               AS "Net Interest Income",
    fee_income                                                 AS "Fee Income",
    ROUND(interest_income - interest_expense + fee_income, 6)  AS "Net Revenue",
    provision                                                  AS "Provision",
    ROUND((interest_income - interest_expense + fee_income) * opex_ratio, 6) AS "Opex",
    ROUND(interest_income - interest_expense + fee_income
          - provision
          - (interest_income - interest_expense + fee_income) * opex_ratio, 6)
                                                               AS "Contribution Profit",
    ROUND(delinq_rate, 4)                                      AS "Delinquency Rate",
    ROUND(yield_rate * 100, 2)                                 AS "Yield Pct",
    ROUND(funding_eff * 100, 2)                                AS "Funding Cost Pct",
    ROUND((yield_rate - funding_eff) * 100, 2)                 AS "Spread Pct"
FROM fin
