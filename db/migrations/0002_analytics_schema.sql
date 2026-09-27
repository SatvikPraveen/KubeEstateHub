-- 0002: analytics outputs with provenance.
-- Every derived row references the model_runs row that produced it, so any number
-- shown on a dashboard can be traced to code version, seed, parameters and metrics.

CREATE TABLE IF NOT EXISTS model_runs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline        VARCHAR(64) NOT NULL,
    code_version    VARCHAR(64) NOT NULL,
    random_seed     BIGINT      NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'succeeded', 'failed')),
    n_observations  INTEGER,
    parameters      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    metrics         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    error           TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_model_runs_pipeline_started ON model_runs (pipeline, started_at DESC);

CREATE TABLE IF NOT EXISTS market_trends (
    id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_run_id              UUID          NOT NULL REFERENCES model_runs (id) ON DELETE CASCADE,
    city                      VARCHAR(100)  NOT NULL,
    state                     CHAR(2)       NOT NULL,
    property_type             property_type,             -- NULL = all types
    period_start              DATE          NOT NULL,
    period_end                DATE          NOT NULL,
    n_sales                   INTEGER       NOT NULL,
    n_active                  INTEGER       NOT NULL,
    median_sale_price         NUMERIC(14, 2),
    median_sale_price_ci_low  NUMERIC(14, 2),
    median_sale_price_ci_high NUMERIC(14, 2),
    median_price_per_sqft     NUMERIC(12, 2),
    median_days_on_market     NUMERIC(8, 2),
    sale_to_list_ratio        NUMERIC(6, 4),
    months_of_supply          NUMERIC(8, 2),
    absorption_rate           NUMERIC(6, 4),
    trend_slope_pct_per_month NUMERIC(8, 4),             -- Theil-Sen slope of log median price
    trend_slope_ci_low        NUMERIC(8, 4),
    trend_slope_ci_high       NUMERIC(8, 4),
    mann_kendall_tau          NUMERIC(6, 4),
    mann_kendall_p            NUMERIC(8, 6),
    trend_direction           VARCHAR(20)   NOT NULL,
    computed_at               TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT market_trends_period CHECK (period_end >= period_start),
    CONSTRAINT market_trends_unique UNIQUE NULLS NOT DISTINCT
        (city, state, property_type, period_start, period_end)
);
CREATE INDEX IF NOT EXISTS idx_market_trends_city ON market_trends (city, period_end DESC);

CREATE TABLE IF NOT EXISTS price_index (
    model_run_id UUID          NOT NULL REFERENCES model_runs (id) ON DELETE CASCADE,
    period       DATE          NOT NULL,                  -- first day of month
    index_value  NUMERIC(10, 4) NOT NULL,                 -- base period = 100
    std_error    NUMERIC(10, 6),
    n_sales      INTEGER       NOT NULL,
    PRIMARY KEY (model_run_id, period)
);

CREATE TABLE IF NOT EXISTS property_valuations (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    listing_id       BIGINT        NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    model_run_id     UUID          NOT NULL REFERENCES model_runs (id) ON DELETE CASCADE,
    method           VARCHAR(32)   NOT NULL,
    estimated_value  NUMERIC(14, 2) NOT NULL CHECK (estimated_value > 0),
    interval_low     NUMERIC(14, 2),
    interval_high    NUMERIC(14, 2),
    confidence_level NUMERIC(4, 3) CHECK (confidence_level > 0 AND confidence_level < 1),
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT property_valuations_interval CHECK (interval_low IS NULL OR interval_low <= interval_high),
    CONSTRAINT property_valuations_unique UNIQUE (listing_id, model_run_id, method)
);
CREATE INDEX IF NOT EXISTS idx_property_valuations_listing ON property_valuations (listing_id, created_at DESC);
