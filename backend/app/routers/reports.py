import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from .. import crud
from ..database import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{lake_id}/pdf")
def generate_pdf_report(lake_id: int, db: Session = Depends(get_db)):
    """Génère un rapport PDF avec traçabilité complète (date, méthode,
    seuil, source — cf. rapport section 12.1)."""
    lake = crud.get_lake(db, lake_id)
    if lake is None:
        raise HTTPException(status_code=404, detail="Lac introuvable")

    indicators = crud.get_indicators_timeseries(db, lake_id)
    if not indicators:
        raise HTTPException(
            status_code=400,
            detail="Aucun indicateur calculé — lancez process_indices.py (Jour 2) d'abord.",
        )

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, f"HydroWatch — Rapport : {lake.name}")
    y -= 0.8 * cm
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, y, f"Généré le {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Région : {lake.region or 'N/A'} — Altitude : {lake.altitude_m or 'N/A'} m")
    y -= 1.2 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Série temporelle des surfaces en eau")
    y -= 0.7 * cm
    c.setFont("Helvetica-Bold", 8)
    headers = ["Année", "Méthode", "Seuil", "Nuages (%)", "Surface (ha)", "Surface (km²)"]
    x_positions = [2 * cm, 3.5 * cm, 6.5 * cm, 8.5 * cm, 11 * cm, 14 * cm]
    for x, h in zip(x_positions, headers):
        c.drawString(x, y, h)
    y -= 0.4 * cm
    c.line(2 * cm, y, 18 * cm, y)
    y -= 0.4 * cm

    c.setFont("Helvetica", 8)
    for ind in indicators:
        if y < 2 * cm:
            c.showPage()
            y = height - 2 * cm
            c.setFont("Helvetica", 8)
        row = [
            str(ind.year),
            ind.method,
            f"{ind.threshold:.3f}" if ind.threshold is not None else "N/A",
            f"{ind.cloud_cover_pct:.1f}" if ind.cloud_cover_pct is not None else "N/A",
            f"{ind.surface_ha:.2f}",
            f"{ind.surface_km2:.2f}",
        ]
        for x, val in zip(x_positions, row):
            c.drawString(x, y, val)
        y -= 0.4 * cm

    y -= 0.8 * cm
    c.setFont("Helvetica-Oblique", 7)
    c.drawString(
        2 * cm, y,
        "Traçabilité : chaque surface est calculée depuis un masque NDWI + seuillage Otsu "
        "appliqué à une image Sentinel-2 filtrée par couverture nuageuse (cf. méthode ci-dessus)."
    )

    c.showPage()
    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=hydrowatch_rapport_lac{lake_id}.pdf"},
    )


@router.get("/{lake_id}/export.csv")
def export_csv(lake_id: int, db: Session = Depends(get_db)):
    """Export CSV brut des indicateurs — pour analyse SIG externe
    (cf. rapport 2.3, exigence d'export)."""
    indicators = crud.get_indicators_timeseries(db, lake_id)
    if not indicators:
        raise HTTPException(status_code=400, detail="Aucun indicateur disponible")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["year", "method", "threshold", "cloud_cover_pct", "surface_ha", "surface_km2", "n_water_pixels"]
    )
    for ind in indicators:
        writer.writerow(
            [ind.year, ind.method, ind.threshold, ind.cloud_cover_pct,
             ind.surface_ha, ind.surface_km2, ind.n_water_pixels]
        )
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=indicators_lac{lake_id}.csv"},
    )
