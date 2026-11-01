"""
Modèles SQLAlchemy.

`Lake`, `SatelliteImage`, `Indicator` reflètent les tables créées aux
Jours 1 et 2 (init_db.sql, process_indices.py). `Comparison` est
nouvelle (Jour 4) et met en cache les résultats de comparaison
temporelle pour ne pas les recalculer à chaque appel.
"""
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from .database import Base


class Lake(Base):
    __tablename__ = "lakes"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    region = Column(String)
    country = Column(String)
    altitude_m = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class SatelliteImage(Base):
    __tablename__ = "satellite_images"

    id = Column(Integer, primary_key=True)
    lake_id = Column(Integer, ForeignKey("lakes.id"))
    scene_id = Column(String, unique=True)
    acquisition_date = Column(Date)
    satellite = Column(String)
    resolution_m = Column(Float)
    cloud_cover_pct = Column(Float)
    tile = Column(String)
    storage_path = Column(String)
    status = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class Indicator(Base):
    __tablename__ = "indicators"

    id = Column(Integer, primary_key=True)
    lake_id = Column(Integer, ForeignKey("lakes.id"), default=1)
    year = Column(Integer)
    method = Column(String)
    threshold = Column(Float)
    cloud_cover_pct = Column(Float)
    n_water_pixels = Column(Integer)
    surface_ha = Column(Float)
    surface_km2 = Column(Float)
    mask_path = Column(String)
    computed_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("lake_id", "year", "method"),)


class Comparison(Base):
    __tablename__ = "comparisons"

    id = Column(Integer, primary_key=True)
    lake_id = Column(Integer, ForeignKey("lakes.id"), default=1)
    year_a = Column(Integer)
    year_b = Column(Integer)
    method = Column(String)
    surface_a_ha = Column(Float)
    surface_b_ha = Column(Float)
    variation_absolute_ha = Column(Float)
    variation_relative_pct = Column(Float)
    water_gained_ha = Column(Float)
    water_lost_ha = Column(Float)
    water_stable_ha = Column(Float)
    change_raster_path = Column(String)
    change_geojson_path = Column(String)
    computed_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("lake_id", "year_a", "year_b", "method"),)
