"""
Initialise la base HydroWatch (SQLite par défaut) : crée les tables et
insère le lac Bin El Ouidane. Peut être relancé sans danger.

Usage (depuis le dossier backend) :  python scripts/init_db.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import models  # noqa: E402
from app.database import DATABASE_URL, Base, SessionLocal, engine  # noqa: E402


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Lake).filter(models.Lake.id == 1).first() is None:
            db.add(models.Lake(id=1, name="Lac Bin El Ouidane",
                               region="Béni Mellal-Khénifra", country="Maroc",
                               altitude_m=691))
            db.commit()
            print("Lac Bin El Ouidane ajouté.")
        else:
            print("Lac déjà présent.")
        print(f"Base prête : {DATABASE_URL}")
        for lake in db.query(models.Lake).all():
            print(f" - [{lake.id}] {lake.name} ({lake.region})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
