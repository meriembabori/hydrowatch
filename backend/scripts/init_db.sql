-- Initialisation base HydroWatch — schéma minimal pour le Jour 1
-- (les tables analyses, comparisons, indicators, alerts, reports
--  seront ajoutées au Jour 3-4 quand le backend API sera construit)

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS lakes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    region VARCHAR(255),
    country VARCHAR(100) DEFAULT 'Maroc',
    geom GEOMETRY(Polygon, 4326),
    altitude_m FLOAT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS satellite_images (
    id SERIAL PRIMARY KEY,
    lake_id INTEGER REFERENCES lakes(id),
    scene_id VARCHAR(255) UNIQUE NOT NULL,
    acquisition_date DATE NOT NULL,
    satellite VARCHAR(100) DEFAULT 'Sentinel-2',
    resolution_m FLOAT DEFAULT 10,
    cloud_cover_pct FLOAT,
    tile VARCHAR(50),
    storage_path VARCHAR(500),
    status VARCHAR(50) DEFAULT 'metadata_only', -- metadata_only | downloaded | preprocessed
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_satellite_images_lake_date
    ON satellite_images (lake_id, acquisition_date);

-- Lac de référence du projet
INSERT INTO lakes (name, region, country, altitude_m)
VALUES ('Lac Bin El Ouidane', 'Béni Mellal-Khénifra', 'Maroc', 691)
ON CONFLICT DO NOTHING;
