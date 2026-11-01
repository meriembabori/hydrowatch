"""
HydroWatch — Jour 2 : indices, seuillage Otsu, surface en eau

Ce script :
  1. Lit les GeoTIFF téléchargés depuis Google Drive (dossier data/raw/)
  2. Applique le masque de nuages à partir de la bande QA60
  3. Calcule NDWI = (B3-B8)/(B3+B8) et MNDWI = (B3-B11)/(B3+B11)
  4. Cherche un seuil optimal (Otsu) sur le NDWI pour séparer eau / non-eau
  5. Calcule la surface en eau (pixels classés eau x aire du pixel)
  6. Sauvegarde le masque eau en GeoTIFF + un résumé CSV + insère les
     résultats dans la table `indicators` (traçabilité : méthode, seuil,
     % de nuages, nombre de pixels, source)

Prérequis avant de lancer ce script :
  - Avoir terminé le Jour 1 (metadata CSV généré, exports GeoTIFF lancés)
  - Avoir téléchargé les GeoTIFF depuis le dossier Google Drive
    "HydroWatch_Sentinel2" vers backend/data/raw/
    (nom attendu : s2_bin_el_ouidane_<année>.tif, ex: s2_bin_el_ouidane_2020.tif)

Usage :
  python process_indices.py
"""

import glob
import os

import numpy as np
import pandas as pd
import rasterio
from dotenv import load_dotenv
from skimage.filters import threshold_otsu

load_dotenv()

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
SUMMARY_CSV = "indicators_summary.csv"

PIXEL_AREA_M2 = 10 * 10  # résolution 10 m -> 100 m² par pixel

# Ordre des bandes tel qu'exporté au Jour 1
# (BANDS_TO_EXPORT = ["B2", "B3", "B4", "B8", "B11", "B12", "QA60"])
BAND_INDEX = {"B2": 1, "B3": 2, "B4": 3, "B8": 4, "B11": 5, "B12": 6, "QA60": 7}


def load_bands(path):
    with rasterio.open(path) as src:
        b3 = src.read(BAND_INDEX["B3"]).astype(float)
        b8 = src.read(BAND_INDEX["B8"]).astype(float)
        b11 = src.read(BAND_INDEX["B11"]).astype(float)
        qa60 = src.read(BAND_INDEX["QA60"]).astype(int)
        profile = src.profile
    return b3, b8, b11, qa60, profile


def cloud_free_mask(qa60):
    """QA60 : bit 10 = nuages opaques, bit 11 = cirrus.
    Retourne True pour les pixels SANS nuage (valides)."""
    opaque = (qa60 >> 10) & 1
    cirrus = (qa60 >> 11) & 1
    return (opaque == 0) & (cirrus == 0)


def compute_indices(b3, b8, b11):
    eps = 1e-9
    ndwi = (b3 - b8) / (b3 + b8 + eps)
    mndwi = (b3 - b11) / (b3 + b11 + eps)
    return ndwi, mndwi


def extract_water_mask(index_array, valid_mask):
    """Seuillage Otsu sur les pixels valides (sans nuage) du NDWI."""
    valid_values = index_array[valid_mask]
    valid_values = valid_values[np.isfinite(valid_values)]
    if valid_values.size < 100:
        raise ValueError("Trop peu de pixels valides (nuages ?) pour un seuillage fiable")
    threshold = float(threshold_otsu(valid_values))
    water_mask = (index_array > threshold) & valid_mask
    return water_mask, threshold


def surface_from_mask(water_mask):
    n_water_pixels = int(np.sum(water_mask))
    surface_m2 = n_water_pixels * PIXEL_AREA_M2
    return n_water_pixels, surface_m2 / 10_000, surface_m2 / 1_000_000  # pixels, ha, km²


def save_mask_geotiff(mask, profile, out_path):
    out_profile = profile.copy()
    out_profile.update(dtype=rasterio.uint8, count=1, nodata=0)
    with rasterio.open(out_path, "w", **out_profile) as dst:
        dst.write(mask.astype(np.uint8), 1)


def process_file(path, year):
    print(f"\n--- Traitement {year} ({os.path.basename(path)}) ---")
    b3, b8, b11, qa60, profile = load_bands(path)

    valid = cloud_free_mask(qa60)
    cloud_pct = 100 * (1 - valid.mean())

    ndwi, mndwi = compute_indices(b3, b8, b11)

    # Indice principal : NDWI + Otsu (cf. rapport section 4.4/4.5).
    # Le MNDWI est calculé mais pas utilisé pour le seuillage ici —
    # à activer si le NDWI confond l'eau avec des zones bâties/sol nu.
    water_mask, threshold = extract_water_mask(ndwi, valid)
    n_pixels, surface_ha, surface_km2 = surface_from_mask(water_mask)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    mask_path = os.path.join(OUTPUT_DIR, f"water_mask_{year}.tif")
    save_mask_geotiff(water_mask, profile, mask_path)

    result = {
        "year": year,
        "method": "NDWI+Otsu",
        "threshold": round(threshold, 4),
        "cloud_cover_pct_in_aoi": round(float(cloud_pct), 2),
        "n_water_pixels": n_pixels,
        "surface_ha": round(surface_ha, 2),
        "surface_km2": round(surface_km2, 2),
        "mask_path": mask_path,
    }
    print(
        f"    seuil Otsu = {result['threshold']} | "
        f"nuages AOI = {result['cloud_cover_pct_in_aoi']}% | "
        f"surface = {result['surface_ha']} ha"
    )
    if result["cloud_cover_pct_in_aoi"] > 15:
        print("    [!] Couverture nuageuse élevée sur l'AOI — "
              "surface potentiellement peu fiable pour cette année (cf. rapport 12.2)")
    return result


def save_to_db(results):
    """Enregistre les résultats dans la table `indicators` (SQLite par
    défaut, ou PostgreSQL si DATABASE_URL est défini dans .env)."""
    import sys

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from app import models
    from app.database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Lake).filter(models.Lake.id == 1).first() is None:
            db.add(models.Lake(id=1, name="Lac Bin El Ouidane",
                               region="Béni Mellal-Khénifra", country="Maroc",
                               altitude_m=691))
        for r in results:
            values = dict(
                threshold=r["threshold"],
                cloud_cover_pct=r["cloud_cover_pct_in_aoi"],
                n_water_pixels=r["n_water_pixels"],
                surface_ha=r["surface_ha"],
                surface_km2=r["surface_km2"],
                mask_path=r["mask_path"],
            )
            existing = (
                db.query(models.Indicator)
                .filter_by(lake_id=1, year=r["year"], method=r["method"])
                .first()
            )
            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
            else:
                db.add(models.Indicator(lake_id=1, year=r["year"],
                                        method=r["method"], **values))
        db.commit()
    finally:
        db.close()
    print(f"\n{len(results)} résultat(s) enregistré(s)/mis à jour dans la table 'indicators'.")


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "s2_bin_el_ouidane_*.tif")))
    if not files:
        print(
            f"Aucun fichier trouvé dans {os.path.abspath(RAW_DIR)}/\n"
            "-> Téléchargez d'abord les GeoTIFF depuis le dossier Google Drive "
            "'HydroWatch_Sentinel2' généré au Jour 1, et placez-les dans backend/data/raw/ "
            "(nom attendu : s2_bin_el_ouidane_<année>.tif)"
        )
        return

    results = []
    for path in files:
        base = os.path.basename(path)
        year_str = base.replace("s2_bin_el_ouidane_", "").replace(".tif", "")
        try:
            year = int(year_str)
        except ValueError:
            print(f"[!] Nom de fichier inattendu, année non détectée : {base} — ignoré")
            continue
        try:
            results.append(process_file(path, year))
        except Exception as e:
            print(f"[!] Erreur sur {base} : {e}")

    if not results:
        print("\nAucun résultat produit — vérifier les fichiers d'entrée.")
        return

    pd.DataFrame(results).sort_values("year").to_csv(SUMMARY_CSV, index=False)
    print(f"\nRésumé sauvegardé dans {SUMMARY_CSV}")

    save_to_db(results)

    print(
        "\nContrôle de plausibilité (le rapport section 5.4 donnait, pour la maquette, "
        "3032 ha en 2018 et 3116 ha en 2026 — vos vraies valeurs peuvent différer, "
        "c'est attendu, mais un écart énorme peut indiquer un souci d'AOI ou de nuages)."
    )


if __name__ == "__main__":
    main()
