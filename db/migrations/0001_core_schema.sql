-- 0001: core listings schema.
-- Conventions: timestamps are timestamptz (UTC), money is NUMERIC, enums are created
-- idempotently (PostgreSQL has no CREATE TYPE IF NOT EXISTS).

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$ BEGIN
    CREATE TYPE property_type AS ENUM ('residential', 'commercial', 'industrial', 'land', 'multi_family');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE listing_status AS ENUM ('active', 'pending', 'sold', 'withdrawn', 'expired', 'deleted');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS listings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mls_number      VARCHAR(50)    NOT NULL UNIQUE,
    title           VARCHAR(255)   NOT NULL,
    description     TEXT,
    property_type   property_type  NOT NULL,
    status          listing_status NOT NULL DEFAULT 'active',
    price           NUMERIC(14, 2) NOT NULL CHECK (price > 0),          -- list price
    sale_price      NUMERIC(14, 2)          CHECK (sale_price > 0),     -- closing price
    bedrooms        SMALLINT                CHECK (bedrooms >= 0),
    bathrooms       NUMERIC(3, 1)           CHECK (bathrooms >= 0),
    square_feet     INTEGER                 CHECK (square_feet > 0),
    lot_size_sqft   INTEGER                 CHECK (lot_size_sqft > 0),
    year_built      SMALLINT                CHECK (year_built BETWEEN 1800 AND 2100),
    address         VARCHAR(255)   NOT NULL,
    city            VARCHAR(100)   NOT NULL,
    state           CHAR(2)        NOT NULL,
    zip_code        VARCHAR(10)    NOT NULL,
    latitude        NUMERIC(9, 6)           CHECK (latitude BETWEEN -90 AND 90),
    longitude       NUMERIC(9, 6)           CHECK (longitude BETWEEN -180 AND 180),
    listing_date    DATE           NOT NULL DEFAULT CURRENT_DATE,
    sold_date       DATE,
    agent_name      VARCHAR(100),
    agent_email     VARCHAR(255),
    agent_phone     VARCHAR(30),
    image_url       VARCHAR(500),
    thumbnail_url   VARCHAR(500),
    price_per_sqft  NUMERIC(12, 2) GENERATED ALWAYS AS (
                        CASE WHEN square_feet > 0 THEN round(price / square_feet, 2) END
                    ) STORED,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT sold_requires_outcome
        CHECK (status <> 'sold' OR (sold_date IS NOT NULL AND sale_price IS NOT NULL)),
    CONSTRAINT sold_after_listed
        CHECK (sold_date IS NULL OR sold_date >= listing_date)
);

CREATE INDEX IF NOT EXISTS idx_listings_status_city   ON listings (status, city);
CREATE INDEX IF NOT EXISTS idx_listings_type          ON listings (property_type);
CREATE INDEX IF NOT EXISTS idx_listings_price         ON listings (price);
CREATE INDEX IF NOT EXISTS idx_listings_listing_date  ON listings (listing_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_listings_sold_date     ON listings (city, sold_date) WHERE status = 'sold';
CREATE INDEX IF NOT EXISTS idx_listings_title_trgm    ON listings USING gin (title gin_trgm_ops);

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS listings_touch_updated_at ON listings;
CREATE TRIGGER listings_touch_updated_at
    BEFORE UPDATE ON listings
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
