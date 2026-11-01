from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/", response_model=list[schemas.SatelliteImageOut])
def list_images(lake_id: int = 1, db: Session = Depends(get_db)):
    return crud.get_images(db, lake_id)
