"""
HydroWatch — Jour 1 : acquisition des images Sentinel-2 (lac Bin El Ouidane)

Ce script :
  1. Initialise l'API Earth Engine
  2. Recherche, pour chaque année 2018-2026, la meilleure image Sentinel-2
     (niveau 2A, corrigé atmosphériquement) proche du 20 août, sous un
     seuil de nuages donné
  3. Sauvegarde les métadonnées (date, scene_id, % nuages, tuile) dans un CSV
  4. Lance l'export GeoTIFF de chaque image vers Google Drive

Prérequis :
  - pip install -r requirements.txt
  - Un compte Google Earth Engine activé (https://code.earthengine.google.com)
  - Un projet Google Cloud associé à Earth Engine (GEE_PROJECT_ID)

Usage :
  python fetch_sentinel2.py
"""

import os
from datetime import datetime, timedelta

import ee
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

GEE_PROJECT_ID = os.getenv("GEE_PROJECT_ID", "your-gee-project-id")

# AOI autour du lac Bin El Ouidane (Béni Mellal-Khénifra, Maroc), corrigée
# et vérifiée par recherche web (les coordonnées de la maquette du rapport
# étaient erronées) :
#   - Barrage : 32.10667°N, -6.46361°W (source : Wikipedia)
#   - Le lac s'étend sur ~15-25 km au sud de Ouaouizerth (32.15861°N, -6.35500°W)
#   - Superficie réelle ~37 km² (cohérent avec le 38 km² affiché dans la maquette,
#     contrairement à son point de coordonnées qui, lui, était faux)
#
# Le lac a une forme en Y (deux bras : oued El Abid et assif Ahansal) —
# ce rectangle est encore une approximation englobante, pas le contour exact.
# Avant le calcul définitif du Jour 2, vérifiez visuellement sur
# code.earthengine.google.com que le polygone couvre bien toute la retenue.
AOI = ee.Geometry.Rectangle([-6.65, 31.98, -6.25, 32.20])

TARGET_MONTH = 8
TARGET_DAY = 20
WINDOW_DAYS = 45           # fenêtre de recherche autour de la date cible
MAX_CLOUD_PERCENT = 30     # seuil de rejet (on garde la meilleure image sous ce seuil)
YEARS = range(2018, 2027)  # 2018 à 2026 inclus

BANDS_TO_EXPORT = ["B2", "B3", "B4", "B8", "B11", "B12", "QA60"]

OUTPUT_CSV = "sentinel2_bin_el_ouidane_metadata.csv"
DRIVE_EXPORT_FOLDER = "HydroWatch_Sentinel2"


def init_gee():
    """Initialise (ou authentifie si nécessaire) la session Earth Engine."""
    try:
        ee.Initialize(project=GEE_PROJECT_ID)
    except Exception:
        ee.Authenticate()  # ouvre le flux d'authentification dans le navigateur
        ee.Initialize(project=GEE_PROJECT_ID)


def get_best_image_for_year(year: int, aoi: ee.Geometry):
    """Retourne (métadonnées, image) pour la meilleure scène Sentinel-2
    trouvée autour du 20 août de `year`, ou None si aucune image ne
    satisfait le seuil de nuages."""

    target_date = datetime(year, TARGET_MONTH, TARGET_DAY)
    start = (target_date - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    end = (target_date + timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")  # niveau 2A
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PERCENT))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    count = collection.size().getInfo()
    if count == 0:
        return None

    best = collection.first()
    props = best.toDictionary([
        "system:index",
        "system:time_start",
        "CLOUDY_PIXEL_PERCENTAGE",
        "SPACECRAFT_NAME",
        "MGRS_TILE",
    ]).getInfo()

    meta = {
        "year": year,
        "scene_id": props.get("system:index"),
        "date": datetime.utcfromtimestamp(
            props["system:time_start"] / 1000
        ).strftime("%Y-%m-%d"),
        "cloud_cover_pct": round(props.get("CLOUDY_PIXEL_PERCENTAGE", -1), 2),
        "satellite": props.get("SPACECRAFT_NAME", "Sentinel-2"),
        "tile": props.get("MGRS_TILE"),
        "resolution_m": 10,
        "n_candidates_in_window": count,
    }
    return meta, best


def main():
    print("Initialisation Earth Engine...")
    init_gee()

    rows = []
    for year in YEARS:
        result = get_best_image_for_year(year, AOI)
        if result is None:
            print(f"[!] {year} : aucune image sous {MAX_CLOUD_PERCENT}% de nuages "
                  f"dans la fenêtre ±{WINDOW_DAYS}j — élargir WINDOW_DAYS ou MAX_CLOUD_PERCENT")
            continue

        meta, image = result
        rows.append(meta)
        print(f"[OK] {year} -> {meta['scene_id']} "
              f"({meta['date']}, nuages {meta['cloud_cover_pct']}%)")

        # Export GeoTIFF vers Google Drive — bandes utiles au calcul
        # NDWI/MNDWI (B3, B8, B11) + contexte (B2, B4, B12) + masque nuages (QA60)
        export_task = ee.batch.Export.image.toDrive(
            image=image.select(BANDS_TO_EXPORT),
            description=f"hydrowatch_s2_{year}",
            folder=DRIVE_EXPORT_FOLDER,
            fileNamePrefix=f"s2_bin_el_ouidane_{year}",
            region=AOI,
            scale=10,
            crs="EPSG:32629",  # UTM 29N — cohérent avec le rapport
            maxPixels=1e9,
        )
        export_task.start()
        print("    -> export GeoTIFF lancé "
              "(suivre l'avancement dans l'onglet Tasks de code.earthengine.google.com)")

    if not rows:
        print("\nAucune image récupérée — vérifier l'AOI, les dates ou le seuil de nuages.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n{len(df)} image(s) référencée(s). Métadonnées sauvegardées dans {OUTPUT_CSV}")
    print("\nProchaine étape (Jour 2) : télécharger les GeoTIFF depuis Drive, "
          "puis calculer NDWI/MNDWI + seuillage Otsu.")


if __name__ == "__main__":
    main()
