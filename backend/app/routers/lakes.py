from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/lakes", tags=["lakes"])


@router.get("/", response_model=list[schemas.LakeOut])
def list_lakes(db: Session = Depends(get_db)):
    return crud.get_lakes(db)


@router.get("/{lake_id}", response_model=schemas.LakeOut)
def get_lake(lake_id: int, db: Session = Depends(get_db)):
    lake = crud.get_lake(db, lake_id)
    if lake is None:
        raise HTTPException(status_code=404, detail="Lac introuvable")
    return lake
