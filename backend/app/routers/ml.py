import json
import os

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/ml", tags=["ml"])

METRICS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "models", "ml_metrics.json"
)


@router.get("/metrics")
def get_ml_metrics():
    """Renvoie les métriques Random Forest / SVM calculées par train_ml.py
    (Jour 5). Erreur 404 explicite si le script n'a pas encore tourné —
    pas de chiffres inventés en attendant."""
    if not os.path.exists(METRICS_PATH):
        raise HTTPException(
            status_code=404,
            detail="Aucune métrique ML disponible — lancez scripts/train_ml.py (Jour 5) d'abord.",
        )
    with open(METRICS_PATH) as f:
        return json.load(f)
