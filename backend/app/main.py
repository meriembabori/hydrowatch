from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import comparisons, images, indicators, lakes, ml, reports

app = FastAPI(title="HydroWatch API", version="0.1.0")

# Autorise le frontend React (Vite, port 5173 par défaut) à appeler l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lakes.router)
app.include_router(images.router)
app.include_router(indicators.router)
app.include_router(comparisons.router)
app.include_router(ml.router)
app.include_router(reports.router)


@app.get("/")
def root():
    return {"status": "ok", "app": "HydroWatch API"}
