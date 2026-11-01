"""
Logique métier centralisée.

RÈGLE IMPORTANTE (cf. rapport section 16, "Unifier les statistiques") :
chaque statistique affichée dans l'application — dashboard, graphiques,
rapports PDF — doit passer par les fonctions de ce fichier. Ne JAMAIS
recalculer une surface ou une variation directement dans le frontend
ou dans un routeur : ça garantit que le dashboard, la carte et le PDF
afficheront toujours exactement les mêmes chiffres.
"""
import json
import os

import numpy as np
import rasterio
from rasterio.features import shapes
from shapely.geometry import mapping, shape
from sqlalchemy.orm import Session

from . import models

PIXEL_AREA_M2 = 10 * 10  # résolution Sentinel-2 : 10 m


# ------------------------------------------------------------------
# Lacs / images (Jour 3)
# ------------------------------------------------------------------

def get_lakes(db: Session):
    return db.query(models.Lake).all()


def get_lake(db: Session, lake_id: int):
    return db.query(models.Lake).filter(models.Lake.id == lake_id).first()


def get_images(db: Session, lake_id: int):
    return (
        db.query(models.SatelliteImage)
        .filter(models.SatelliteImage.lake_id == lake_id)
        .order_by(models.SatelliteImage.acquisition_date)
        .all()
    )


def get_indicators_timeseries(db: Session, lake_id: int = 1, method: str = "NDWI+Otsu"):
    """Série temporelle des surfaces — fonction UNIQUE utilisée par le
    dashboard, la page Évolution temporelle et les rapports PDF."""
    return (
        db.query(models.Indicator)
        .filter(models.Indicator.lake_id == lake_id, models.Indicator.method == method)
        .order_by(models.Indicator.year)
        .all()
    )


# ------------------------------------------------------------------
# Comparaison temporelle (Jour 4)
# ------------------------------------------------------------------

def _load_water_mask(mask_path: str):
    if not os.path.exists(mask_path):
        raise FileNotFoundError(
            f"Masque introuvable : {mask_path} — avez-vous bien lancé "
            f"process_indices.py (Jour 2) pour cette année ?"
        )
    with rasterio.open(mask_path) as src:
        mask = src.read(1).astype(bool)
        profile = src.profile
        transform = src.transform
        crs = src.crs
    return mask, profile, transform, crs


def compute_comparison(
    db: Session,
    lake_id: int,
    year_a: int,
    year_b: int,
    method: str = "NDWI+Otsu",
    output_dir: str = None,
):
    """Fonction UNIQUE de comparaison temporelle (cf. rapport section 5).

    Compare les masques eau/non-eau de deux années déjà traitées au
    Jour 2, calcule eau gagnée / perdue / stable, produit un raster de
    changement et un GeoJSON vectorisé, et met le résultat en cache
    dans la table `comparisons`.
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

    ind_a = (
        db.query(models.Indicator)
        .filter(
            models.Indicator.lake_id == lake_id,
            models.Indicator.year == year_a,
            models.Indicator.method == method,
        )
        .first()
    )
    ind_b = (
        db.query(models.Indicator)
        .filter(
            models.Indicator.lake_id == lake_id,
            models.Indicator.year == year_b,
            models.Indicator.method == method,
        )
        .first()
    )
    if ind_a is None or ind_b is None:
        annee_manquante = year_a if ind_a is None else year_b
        raise ValueError(
            f"Aucun indicateur trouvé pour {annee_manquante} (méthode {method}). "
            f"Lancez d'abord process_indices.py (Jour 2) pour cette année."
        )

    mask_a, profile_a, transform, crs = _load_water_mask(ind_a.mask_path)
    mask_b, _, _, _ = _load_water_mask(ind_b.mask_path)

    if mask_a.shape != mask_b.shape:
        raise ValueError(
            f"Les masques {year_a} ({mask_a.shape}) et {year_b} ({mask_b.shape}) "
            f"n'ont pas la même dimension — impossible de comparer pixel à pixel. "
            f"Vérifiez que la même AOI/emprise a été utilisée pour les deux exports."
        )

    water_gained = mask_b & ~mask_a   # non-eau -> eau
    water_lost = mask_a & ~mask_b     # eau -> non-eau
    water_stable = mask_a & mask_b    # eau aux deux dates

    def px_to_ha(mask):
        return round(int(np.sum(mask)) * PIXEL_AREA_M2 / 10_000, 2)

    surface_a_ha = ind_a.surface_ha
    surface_b_ha = ind_b.surface_ha
    variation_absolute_ha = round(surface_b_ha - surface_a_ha, 2)
    variation_relative_pct = (
        round(100 * variation_absolute_ha / surface_a_ha, 2) if surface_a_ha else None
    )

    # Raster de changement : 0 = pas d'eau, 1 = stable, 2 = gagnée, 3 = perdue
    change_raster = np.zeros(mask_a.shape, dtype=np.uint8)
    change_raster[water_stable] = 1
    change_raster[water_gained] = 2
    change_raster[water_lost] = 3

    os.makedirs(output_dir, exist_ok=True)
    change_raster_path = os.path.join(output_dir, f"change_{year_a}_{year_b}.tif")
    out_profile = profile_a.copy()
    out_profile.update(dtype=rasterio.uint8, count=1, nodata=0)
    with rasterio.open(change_raster_path, "w", **out_profile) as dst:
        dst.write(change_raster, 1)

    # Vectorisation en GeoJSON (uniquement eau gagnée/perdue — le "stable"
    # n'est en général pas ce qu'on veut visualiser comme changement)
    labels = {2: "eau_gagnee", 3: "eau_perdue"}
    features = []
    for geom, value in shapes(change_raster, mask=(change_raster > 1), transform=transform):
        value = int(value)
        if value in labels:
            features.append(
                {
                    "type": "Feature",
                    "properties": {"classe": labels[value]},
                    "geometry": mapping(shape(geom)),
                }
            )

    geojson = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": str(crs)}},
        "features": features,
    }
    change_geojson_path = os.path.join(output_dir, f"change_{year_a}_{year_b}.geojson")
    with open(change_geojson_path, "w") as f:
        json.dump(geojson, f)

    result = {
        "lake_id": lake_id,
        "year_a": year_a,
        "year_b": year_b,
        "method": method,
        "surface_a_ha": surface_a_ha,
        "surface_b_ha": surface_b_ha,
        "variation_absolute_ha": variation_absolute_ha,
        "variation_relative_pct": variation_relative_pct,
        "water_gained_ha": px_to_ha(water_gained),
        "water_lost_ha": px_to_ha(water_lost),
        "water_stable_ha": px_to_ha(water_stable),
        "change_raster_path": change_raster_path,
        "change_geojson_path": change_geojson_path,
    }

    # Mise en cache en base (évite de recalculer à chaque appel identique)
    existing = (
        db.query(models.Comparison)
        .filter(
            models.Comparison.lake_id == lake_id,
            models.Comparison.year_a == year_a,
            models.Comparison.year_b == year_b,
            models.Comparison.method == method,
        )
        .first()
    )
    if existing:
        for k, v in result.items():
            if k != "lake_id":
                setattr(existing, k, v)
    else:
        db.add(models.Comparison(**result))
    db.commit()

    return result
