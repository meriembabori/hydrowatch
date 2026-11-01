from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("/", response_model=list[schemas.IndicatorOut])
def get_timeseries(
    lake_id: int = 1, method: str = "NDWI+Otsu", db: Session = Depends(get_db)
):
    """Série temporelle des surfaces en eau — source unique réutilisée
    par le dashboard, le graphique d'évolution temporelle et les rapports."""
    return crud.get_indicators_timeseries(db, lake_id, method)
