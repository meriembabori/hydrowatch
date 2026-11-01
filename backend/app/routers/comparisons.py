from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.post("/", response_model=schemas.ComparisonOut)
def compare(request: schemas.ComparisonRequest, db: Session = Depends(get_db)):
    """Compare deux années : eau gagnée / perdue / stable, variation
    absolue et relative, GeoJSON de la carte de changement."""
    try:
        result = crud.compute_comparison(
            db, request.lake_id, request.year_a, request.year_b, request.method
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
