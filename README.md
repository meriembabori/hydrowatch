# HydroWatch

Application web pour suivre l'évolution de la surface en eau du lac Bin El Ouidane (Maroc) à partir d'images satellite Sentinel-2.

C'est un projet personnel. Je voulais pouvoir partir d'images satellite et arriver à des chiffres et des cartes comparables d'une année à l'autre, en gardant pour chaque résultat la date de l'image, la méthode et les paramètres utilisés.

## Ce que fait le projet

Pour chaque année entre 2018 et 2026, je récupère une image Sentinel-2 du lac (autour du 20 août, avec peu de nuages). J'en tire un masque eau / non-eau, j'en déduis la surface en hectares, puis je compare deux années pour voir où le lac a gagné ou perdu de la surface. Une petite API expose ces résultats, et un tableau de bord les affiche. J'ai aussi ajouté une comparaison entre Random Forest et SVM pour la classification eau / non-eau.

## Méthode

1. Images Sentinel-2 niveau 2A récupérées avec Google Earth Engine.
2. Masque des nuages avec la bande QA60.
3. Calcul du NDWI (B3 et B8) et du MNDWI (B3 et B11).
4. Seuil automatique par la méthode d'Otsu sur le NDWI pour obtenir le masque d'eau.
5. Surface = nombre de pixels d'eau x 100 m² (résolution de 10 m).
6. Comparaison de deux années : eau gagnée, eau perdue, eau stable.
7. Entraînement de Random Forest et SVM avec validation croisée à 5 plis.

## Technologies

- Python : FastAPI, SQLAlchemy, rasterio, scikit-image, scikit-learn, reportlab
- Base de données : SQLite (un simple fichier), PostgreSQL/PostGIS possible via `DATABASE_URL`
- Données : Google Earth Engine (Sentinel-2)
- Frontend : React, Tailwind CSS, Recharts

## Organisation du dépôt

```
backend/
  app/        API FastAPI (lacs, images, indicateurs, comparaisons, ML, rapports)
  scripts/    récupération Sentinel-2, calcul des indices, entraînement ML
  tests/      quelques tests
frontend/src/ interface React (à copier dans un projet Vite, voir plus bas)
docs/         mes notes de travail
```

## Installation

Avec Anaconda :

```
conda create -n hydrowatch python=3.11 -y
conda activate hydrowatch
conda install -c conda-forge rasterio -y
cd backend
pip install -r requirements.txt
copy .env.example .env
python scripts/init_db.py
```

Dans `.env`, renseigner `GEE_PROJECT_ID` avec l'identifiant de son projet Google Cloud inscrit à Earth Engine. Ensuite :

```
python -c "import ee; ee.Authenticate()"
cd scripts
python fetch_sentinel2.py      # lance les exports vers Google Drive
python process_indices.py      # après avoir copié les .tif dans backend/data/raw
cd ..
uvicorn app.main:app --reload --port 8000
```

La documentation de l'API est ensuite sur http://localhost:8000/docs.

Pour le frontend, il faut créer un projet Vite (`npm create vite@latest frontend-app -- --template react`), installer Tailwind 3 et Recharts, puis copier le contenu de `frontend/src` dedans.

## État du projet

Le code est écrit, mais je suis encore en train de le tester sur de vraies images. Je n'ai pas encore de résultats validés à présenter, donc je ne donne aucun chiffre ici.

## Limites connues

- La zone d'étude est un rectangle approximatif autour du lac, pas son contour exact.
- Une seule image par an : la comparaison dépend de la qualité de cette image.
- Pour le machine learning, les étiquettes viennent du masque d'Otsu et non d'un échantillonnage fait à la main. La comparaison Random Forest / SVM montre donc surtout à quel point ils reproduisent ce masque, ce n'est pas une validation indépendante.
- Le niveau d'eau et le taux de remplissage ne se calculent pas à partir de la surface seule : il faudrait des données hydrométriques, que je n'ai pas intégrées.
- Pas de pente ni d'altitude parmi les variables du modèle.

## Auteure

Meriem Babori, projet personnel, 2026.
