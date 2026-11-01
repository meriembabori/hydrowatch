"""
Schémas Pydantic — forme des données échangées par l'API.
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel


class LakeOut(BaseModel):
    id: int
    name: str
    region: Optional[str] = None
    country: Optional[str] = None
    altitude_m: Optional[float] = None

    class Config:
        from_attributes = True


class SatelliteImageOut(BaseModel):
    id: int
    scene_id: str
    acquisition_date: date
    satellite: str
    cloud_cover_pct: Optional[float] = None
    tile: Optional[str] = None

    class Config:
        from_attributes = True


class IndicatorOut(BaseModel):
    year: int
    method: str
    threshold: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    surface_ha: float
    surface_km2: float
    n_water_pixels: int

    class Config:
        from_attributes = True


class ComparisonRequest(BaseModel):
    lake_id: int = 1
    year_a: int
    year_b: int
    method: str = "NDWI+Otsu"


class ComparisonOut(BaseModel):
    lake_id: int
    year_a: int
    year_b: int
    method: str
    surface_a_ha: float
    surface_b_ha: float
    variation_absolute_ha: float
    variation_relative_pct: Optional[float] = None
    water_gained_ha: float
    water_lost_ha: float
    water_stable_ha: float
    change_geojson_path: Optional[str] = None

    class Config:
        from_attributes = True
