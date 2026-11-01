"""
HydroWatch — Jour 5 : Machine Learning (Random Forest vs SVM)

Principe : le masque Otsu du Jour 2 sert de "vérité terrain" (labels
eau/non-eau) pour entraîner un classificateur qui utilise PLUSIEURS
variables spectrales — l'idée du rapport section 6.1 est de ne plus
dépendre d'un seuil unique sur un seul indice.

Ce script :
  1. Pour chaque année déjà traitée (Jour 2), échantillonne N pixels
     aléatoires eau + N pixels non-eau à partir du masque Otsu
  2. Extrait les features (B2,B3,B4,B8,B11,B12,NDWI,MNDWI,NDVI) à ces pixels
  3. Regroupe tous les échantillons de toutes les années disponibles
  4. Entraîne Random Forest et SVM avec validation croisée (S-Fold, cf.
     rapport 6.5)
  5. Calcule accuracy/précision/rappel/F1/kappa à partir de LA MÊME
     matrice de confusion pour les deux (cf. rapport 6.6 / 12.5)
  6. Sauvegarde les modèles (joblib) + les métriques (JSON) + l'importance
     des variables (RF)

Limite connue : pente et altitude (mentionnées dans le rapport comme
variables possibles) nécessitent un MNT (ex. SRTM) non intégré dans ce
MVP — les features utilisées ici sont uniquement spectrales.

Usage : python train_ml.py
"""

import glob
import json
import os

import numpy as np
import rasterio
from joblib import dump
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.svm import SVC

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "models")

N_SAMPLES_PER_CLASS_PER_YEAR = 800
N_SPLITS = 5  # S-Fold Cross Validation, cf. rapport 6.5

BAND_INDEX = {"B2": 1, "B3": 2, "B4": 3, "B8": 4, "B11": 5, "B12": 6, "QA60": 7}
FEATURE_NAMES = ["B2", "B3", "B4", "B8", "B11", "B12", "NDWI", "MNDWI", "NDVI"]


def compute_features(b2, b3, b4, b8, b11, b12):
    eps = 1e-9
    ndwi = (b3 - b8) / (b3 + b8 + eps)
    mndwi = (b3 - b11) / (b3 + b11 + eps)
    ndvi = (b8 - b4) / (b8 + b4 + eps)
    return np.stack([b2, b3, b4, b8, b11, b12, ndwi, mndwi, ndvi], axis=-1)


def sample_year(raw_path, mask_path, rng):
    with rasterio.open(raw_path) as src:
        b2 = src.read(BAND_INDEX["B2"]).astype(float)
        b3 = src.read(BAND_INDEX["B3"]).astype(float)
        b4 = src.read(BAND_INDEX["B4"]).astype(float)
        b8 = src.read(BAND_INDEX["B8"]).astype(float)
        b11 = src.read(BAND_INDEX["B11"]).astype(float)
        b12 = src.read(BAND_INDEX["B12"]).astype(float)
        qa60 = src.read(BAND_INDEX["QA60"]).astype(int)

    with rasterio.open(mask_path) as src:
        water_mask = src.read(1).astype(bool)

    valid = ((qa60 >> 10) & 1 == 0) & ((qa60 >> 11) & 1 == 0)
    features = compute_features(b2, b3, b4, b8, b11, b12)

    water_idx = np.argwhere(water_mask & valid)
    nonwater_idx = np.argwhere((~water_mask) & valid)

    n = min(N_SAMPLES_PER_CLASS_PER_YEAR, len(water_idx), len(nonwater_idx))
    if n < 20:
        return None, None

    water_sel = water_idx[rng.choice(len(water_idx), n, replace=False)]
    nonwater_sel = nonwater_idx[rng.choice(len(nonwater_idx), n, replace=False)]

    X_water = features[water_sel[:, 0], water_sel[:, 1]]
    X_nonwater = features[nonwater_sel[:, 0], nonwater_sel[:, 1]]

    X = np.vstack([X_water, X_nonwater])
    y = np.concatenate([np.ones(n), np.zeros(n)])
    return X, y


def build_dataset():
    rng = np.random.default_rng(42)
    raw_files = sorted(glob.glob(os.path.join(RAW_DIR, "s2_bin_el_ouidane_*.tif")))

    all_X, all_y = [], []
    years_used = []
    for raw_path in raw_files:
        base = os.path.basename(raw_path)
        year = base.replace("s2_bin_el_ouidane_", "").replace(".tif", "")
        mask_path = os.path.join(PROCESSED_DIR, f"water_mask_{year}.tif")
        if not os.path.exists(mask_path):
            print(f"[!] Pas de masque pour {year} (lancez process_indices.py) — ignoré")
            continue

        X, y = sample_year(raw_path, mask_path, rng)
        if X is None:
            print(f"[!] Trop peu de pixels valides pour {year} — ignoré")
            continue

        all_X.append(X)
        all_y.append(y)
        years_used.append(year)
        print(f"[OK] {year} : {len(y)} échantillons ajoutés")

    if not all_X:
        return None, None, []

    return np.vstack(all_X), np.concatenate(all_y), years_used


def evaluate_with_cv(model, X, y):
    """Prédictions out-of-fold via validation croisée S-Fold — garantit
    que chaque métrique vient de LA MÊME matrice de confusion
    (cf. rapport 6.6 / 12.5, incohérence à éviter)."""
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42)
    y_pred = cross_val_predict(model, X, y, cv=skf)
    cm = confusion_matrix(y, y_pred)
    metrics = {
        "accuracy": round(float(accuracy_score(y, y_pred)), 4),
        "precision": round(float(precision_score(y, y_pred)), 4),
        "recall": round(float(recall_score(y, y_pred)), 4),
        "f1_score": round(float(f1_score(y, y_pred)), 4),
        "kappa": round(float(cohen_kappa_score(y, y_pred)), 4),
        "confusion_matrix": cm.tolist(),  # [[TN, FP], [FN, TP]]
    }
    return metrics


def main():
    print("Construction du jeu d'échantillons à partir des masques Otsu...")
    X, y, years_used = build_dataset()
    if X is None:
        print(
            "\nAucune donnée disponible. Assurez-vous d'avoir terminé le Jour 1 "
            "(GeoTIFF dans data/raw/) et le Jour 2 (masques dans data/processed/)."
        )
        return

    print(f"\nJeu total : {len(y)} échantillons ({int(y.sum())} eau, "
          f"{int((y == 0).sum())} non-eau) sur les années {years_used}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    results = {}

    print("\n--- Random Forest ---")
    rf = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1)
    rf_metrics = evaluate_with_cv(rf, X, y)
    rf.fit(X, y)  # entraînement final sur tout le jeu pour la sauvegarde du modèle
    rf_metrics["feature_importance"] = {
        name: round(float(imp), 4) for name, imp in zip(FEATURE_NAMES, rf.feature_importances_)
    }
    results["random_forest"] = rf_metrics
    dump(rf, os.path.join(MODELS_DIR, "rf_model.joblib"))
    print(json.dumps({k: v for k, v in rf_metrics.items() if k != "confusion_matrix"}, indent=2))

    print("\n--- SVM ---")
    svm = SVC(kernel="rbf", C=1.0, gamma="scale", random_state=42)
    svm_metrics = evaluate_with_cv(svm, X, y)
    svm.fit(X, y)
    results["svm"] = svm_metrics
    dump(svm, os.path.join(MODELS_DIR, "svm_model.joblib"))
    print(json.dumps({k: v for k, v in svm_metrics.items() if k != "confusion_matrix"}, indent=2))

    metadata = {
        "trained_at": __import__("datetime").datetime.now().isoformat(),
        "years_used": years_used,
        "n_samples": int(len(y)),
        "n_splits": N_SPLITS,
        "features": FEATURE_NAMES,
        "results": results,
    }
    metrics_path = os.path.join(MODELS_DIR, "ml_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nModèles sauvegardés dans {MODELS_DIR}/")
    print(f"Métriques sauvegardées dans {metrics_path}")
    print(
        "\nRappel important : ces métriques viennent d'un jeu d'entraînement "
        "généré à partir du masque Otsu lui-même (pas d'annotation manuelle "
        "indépendante). C'est un raccourci acceptable pour un MVP en 1 semaine, "
        "mais le rapport (6.5) recommande des échantillons vérifiés manuellement "
        "pour un vrai protocole de validation — à noter comme limite connue."
    )


if __name__ == "__main__":
    main()
