-- Outcome marking (spec §72) and backtest runs (spec §86).
ALTER TABLE engine_run ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'LIVE' CHECK (kind IN ('LIVE', 'BACKTEST'));

-- Each signal and stance is marked at fixed horizons after its as-of date once prices for that
-- horizon exist: absolute return, excess return over the priced universe's median return for the
-- same window, maximum drawdown inside the window. Append-only; a (signal, horizon) is marked once.
CREATE TABLE IF NOT EXISTS signal_outcome (
    signal_id        text NOT NULL REFERENCES signal (signal_id),
    horizon_days     smallint NOT NULL CHECK (horizon_days IN (21, 63, 126, 252, 504)),
    as_of            date NOT NULL,
    end_date         date NOT NULL,
    price_at         numeric(14, 4) NOT NULL,
    price_end        numeric(14, 4) NOT NULL,
    return_pct       numeric(10, 4) NOT NULL,
    excess_pct       numeric(10, 4) NOT NULL,
    max_drawdown_pct numeric(10, 4) NOT NULL,
    marked_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (signal_id, horizon_days)
);
CREATE INDEX IF NOT EXISTS signal_outcome_horizon_idx ON signal_outcome (horizon_days);

CREATE TABLE IF NOT EXISTS stance_outcome (
    stance_id        text NOT NULL REFERENCES stance (stance_id),
    horizon_days     smallint NOT NULL CHECK (horizon_days IN (21, 63, 126, 252, 504)),
    as_of            date NOT NULL,
    end_date         date NOT NULL,
    return_pct       numeric(10, 4) NOT NULL,
    excess_pct       numeric(10, 4) NOT NULL,
    max_drawdown_pct numeric(10, 4) NOT NULL,
    marked_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (stance_id, horizon_days)
);
