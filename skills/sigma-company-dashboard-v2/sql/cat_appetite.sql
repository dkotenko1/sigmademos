-- Catastrophe & RDS appetite grid: one row per modelled scenario, for the
-- bespoke "Catastrophe & RDS Appetite Board" plugin on page 1.
--
-- Grounded in what Arch's underwriting teams already run in Sigma (Lloyd's cat
-- exposure management: EP curves, RDS / LRDS, LCM5, Cyber PNAD aggregation
-- monitoring) and in the Sept-2026 training ask: "I could write a whole lot
-- more premium -- but did I write it intelligently?". Net PML vs the board
-- appetite limit is that question for the cat and aggregation perils.
-- All figures are illustrative ($M) and the scenarios are generic industry
-- events, not Arch's actual modelled output.
SELECT
    CAST(scenario     AS VARCHAR)       AS "Scenario",
    CAST(class_name   AS VARCHAR)       AS "Class",
    CAST(gross_pml    AS NUMBER(10,1))  AS "Gross PML",
    CAST(net_pml      AS NUMBER(10,1))  AS "Net PML",
    CAST(appetite     AS NUMBER(10,1))  AS "Appetite",
    CAST(accounts     AS NUMBER)        AS "Accounts"
FROM (
    SELECT 'Florida windstorm (1-in-100)' AS scenario, 'Property & Cat' AS class_name,
           1240.0 AS gross_pml, 412.0 AS net_pml, 450.0 AS appetite, 3150 AS accounts
    UNION ALL SELECT 'Gulf Coast hurricane (1-in-100)',   'Property & Cat',  980.0, 360.0, 340.0, 2710
    UNION ALL SELECT 'California earthquake (1-in-250)',  'Property & Cat',  760.0, 285.0, 330.0, 1480
    UNION ALL SELECT 'Northeast windstorm (1-in-100)',    'Property & Cat',  410.0, 150.0, 240.0, 1920
    UNION ALL SELECT 'Midwest convective storm (agg.)',   'Property & Cat',  520.0, 205.0, 260.0, 2260
    UNION ALL SELECT 'Cyber: cloud-provider outage RDS',  'Cyber',           610.0, 190.0, 200.0, 2900
    UNION ALL SELECT 'Cyber: widespread ransomware RDS',  'Cyber',           540.0, 210.0, 195.0, 3100
    UNION ALL SELECT 'Terrorism: NYC vehicle-borne device','Casualty',       330.0, 120.0, 150.0, 840
    UNION ALL SELECT 'Marine: port accumulation / collision','Marine & Cargo',280.0, 110.0, 160.0, 610
    UNION ALL SELECT 'Construction: wrap-up latent defect','Construction',   350.0, 130.0, 140.0, 1900
    UNION ALL SELECT 'A&H: mass-gathering event accident','Accident & Health',180.0, 70.0, 120.0, 4200
) AS s
