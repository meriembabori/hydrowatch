# MISE À JOUR 

La base de données est maintenant un simple fichier SQLite (créé
automatiquement dans backend/hydrowatch.db). **Docker et PostgreSQL ne
sont plus nécessaires.** Ignorez toutes les mentions de `docker compose`
plus bas. Ordre à suivre (Anaconda Prompt) :

```
conda create -n hydrowatch python=3.11 -y
conda activate hydrowatch
conda install -c conda-forge rasterio -y
cd backend
pip install -r requirements.txt
copy .env.example .env
python scripts/init_db.py
python -c "import ee; ee.Authenticate()"
cd scripts
python fetch_sentinel2.py
```
Puis Jour 2 (`python process_indices.py`), et l'API
(`cd .. && uvicorn app.main:app --reload --port 8000`).

---

# HydroWatch — Jour 1 : Setup + acquisition des données

Checklist du jour, dans l'ordre. Comptez 3-4h si tout se passe bien
(le compte GEE peut mettre quelques heures à être approuvé — à lancer
en tout premier).

## 1. Compte Google Earth Engine (à faire EN PREMIER)

1. Aller sur https://earthengine.google.com/ et cliquer "Get Started"
2. Se connecter avec un compte Google, activer Earth Engine pour ce compte
3. Créer (ou réutiliser) un projet Google Cloud lié à Earth Engine
4. Noter le **Project ID** — vous en aurez besoin dans `.env`
5. Vérifier l'accès à l'éditeur de code : https://code.earthengine.google.com

> Cette étape peut nécessiter une validation de quelques minutes à quelques
> heures selon les cas. Lancez-la en premier et enchaînez avec les étapes
> suivantes en parallèle.

## 2. Structure des repos

```
hydrowatch/
├── backend/
│   ├── app/                  # code FastAPI (Jour 3+)
│   ├── scripts/
│   │   ├── init_db.sql
│   │   └── fetch_sentinel2.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # à scaffolder (voir ci-dessous)
├── docker-compose.yml
└── .gitignore
```

Initialiser git :
```bash
cd hydrowatch
git init
git add .
git commit -m "Setup initial HydroWatch"
```

## 3. Base de données PostgreSQL + PostGIS

```bash
docker compose up -d
```

Ceci lance PostGIS et exécute automatiquement `backend/scripts/init_db.sql`
(création de l'extension PostGIS, des tables `lakes` et `satellite_images`,
et insertion du lac Bin El Ouidane).

Vérifier :
```bash
docker exec -it hydrowatch_db psql -U hydrowatch -d hydrowatch -c "SELECT * FROM lakes;"
```

## 4. Environnement Python (backend)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# éditer .env : renseigner GEE_PROJECT_ID avec le Project ID noté à l'étape 1
```

## 5. Authentification Earth Engine

```bash
python -c "import ee; ee.Authenticate()"
```

Ceci ouvre une page web pour autoriser l'accès — à faire une seule fois
par machine.

## 6. Définir/vérifier l'AOI (zone d'intérêt)

Le script `scripts/fetch_sentinel2.py` contient une AOI de départ
(rectangle autour du point central du lac donné dans le rapport,
32.031°N / -6.068°W). **C'est une approximation** — avant de lancer
la récupération définitive :

1. Ouvrir https://code.earthengine.google.com
2. Dessiner ou importer le contour réel du lac (à l'œil sur une image
   Sentinel-2 récente, ou via un shapefile/geojson si vous en trouvez un)
3. Ajuster les coordonnées `AOI = ee.Geometry.Rectangle([...])` dans le
   script en conséquence (ou remplacer par un `ee.Geometry.Polygon` précis)

## 7. Récupérer la série Sentinel-2 2018-2026

```bash
cd backend/scripts
python fetch_sentinel2.py
```

Le script va, pour chaque année :
- chercher la meilleure image Sentinel-2 (niveau 2A, moins nuageuse)
  dans une fenêtre de ±45 jours autour du 20 août
- enregistrer les métadonnées dans `sentinel2_bin_el_ouidane_metadata.csv`
- lancer un export GeoTIFF vers un dossier Google Drive `HydroWatch_Sentinel2`

Les exports GeoTIFF s'exécutent sur les serveurs Google en arrière-plan :
suivez leur avancement dans l'onglet **Tasks** de
https://code.earthengine.google.com — ça peut prendre de quelques minutes
à ~30 min selon la taille de la zone.

## 8. Fin de journée — critères de validation

- [ ] Compte GEE actif, Project ID renseigné dans `.env`
- [ ] `docker compose up -d` fonctionne, table `lakes` peuplée
- [ ] AOI vérifiée visuellement (couvre bien tout le lac)
- [ ] `sentinel2_bin_el_ouidane_metadata.csv` généré avec au moins 7-8
      années sur les 9 (2018-2026) — une année manquante n'est pas
      grave si les nuages sont trop importants cette année-là, notez-le
- [ ] Exports GeoTIFF terminés (ou en cours) dans Google Drive

## 9. Frontend (scaffold rapide, en parallèle si possible)

```bash
cd hydrowatch
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install leaflet react-leaflet recharts
```

Pas besoin d'écrire l'UI aujourd'hui — juste avoir le squelette prêt
pour le Jour 6.

---

# Jour 2 : Prétraitement + indices + surface en eau

## 1. Télécharger les GeoTIFF depuis Google Drive

Les exports du Jour 1 sont dans le dossier Drive `HydroWatch_Sentinel2`.

- Le plus simple : ouvrir Google Drive dans le navigateur, sélectionner
  tous les fichiers `s2_bin_el_ouidane_*.tif`, "Télécharger" (ça les
  zippe automatiquement)
- Décompresser et placer les fichiers `.tif` dans `backend/data/raw/`

Vérifier :
```bash
ls backend/data/raw/
# doit afficher : s2_bin_el_ouidane_2018.tif, s2_bin_el_ouidane_2019.tif, ...
```

> Si l'export d'une année a produit plusieurs fichiers (image divisée en
> tuiles à cause de la taille de l'AOI), il faudra les fusionner avant
> l'étape suivante — dites-le moi si ça arrive, on ajoutera une étape
> de mosaïquage.

## 2. Installer les nouvelles dépendances

```bash
cd backend
source venv/bin/activate   # si pas déjà activé
pip install -r requirements.txt   # ajoute rasterio, scikit-image, numpy
```

## 3. Lancer le traitement

```bash
cd backend/scripts
python process_indices.py
```

Pour chaque image, le script :
- applique le masque de nuages (bande QA60)
- calcule NDWI et MNDWI
- cherche le seuil Otsu optimal sur le NDWI
- extrait le masque eau/non-eau et calcule la surface réelle
- sauvegarde le masque en GeoTIFF (`backend/data/processed/water_mask_<année>.tif`)
- insère le résultat dans la table `indicators` (avec méthode, seuil,
  % nuages, nb pixels — traçabilité complète, cf. rapport section 12)

## 4. Vérifier les résultats

```bash
docker exec -it hydrowatch_db psql -U hydrowatch -d hydrowatch -c "SELECT year, method, threshold, cloud_cover_pct, surface_ha FROM indicators ORDER BY year;"
```

Ou ouvrir `backend/scripts/indicators_summary.csv` directement.

Pour une vérification visuelle rapide d'un masque :
```bash
python -c "
import rasterio, matplotlib.pyplot as plt
with rasterio.open('../data/processed/water_mask_2026.tif') as src:
    plt.imshow(src.read(1), cmap='Blues')
    plt.title('Masque eau 2026')
    plt.savefig('check_mask_2026.png')
"
```
(installer matplotlib si besoin : `pip install matplotlib`)

## 5. Fin de journée — critères de validation

- [ ] Tous les GeoTIFF du Jour 1 téléchargés dans `backend/data/raw/`
- [ ] `process_indices.py` exécuté sans erreur bloquante
- [ ] `indicators_summary.csv` généré avec une ligne par année disponible
- [ ] Table `indicators` peuplée en base (vérifiable via psql)
- [ ] Au moins un masque eau vérifié visuellement (forme cohérente avec
      un lac, pas un bruit aléatoire)
- [ ] Les années à forte couverture nuageuse sont identifiées et notées
      (surface potentiellement peu fiable pour ces années-là)

## Prochaine étape (Jour 3)

Construire l'API FastAPI : endpoints `/lakes`, `/images`, `/indicators`
(série temporelle), en lisant directement la table `indicators` —
c'est la fonction backend unique qui alimentera ensuite le dashboard,
les graphiques et les rapports PDF (principe d'unification des
statistiques, cf. rapport section 16).

---

# Jour 3 : API FastAPI (cœur du backend)

Le code est déjà écrit (dossier `backend/app/`). Il vous reste juste à
le lancer et le tester.

## 1. Lancer le serveur

```bash
cd backend
source venv/bin/activate   # si pas déjà activé
uvicorn app.main:app --reload --port 8000
```

## 2. Tester

Ouvrir dans le navigateur : **http://localhost:8000/docs**

FastAPI génère automatiquement une interface interactive (Swagger UI)
où vous pouvez tester chaque endpoint sans écrire de code :
- `GET /lakes/` → doit renvoyer le lac Bin El Ouidane (créé au Jour 1)
- `GET /images/?lake_id=1` → vide pour l'instant (pas encore rempli, normal)
- `GET /indicators/?lake_id=1` → la série temporelle calculée au Jour 2
  (si `process_indices.py` a bien tourné)

## 3. Fin de journée — critères de validation

- [ ] `uvicorn` démarre sans erreur
- [ ] `/docs` s'affiche et liste bien les 4 groupes d'endpoints
- [ ] `GET /lakes/` renvoie le lac Bin El Ouidane
- [ ] `GET /indicators/` renvoie vos vraies surfaces calculées au Jour 2
      (si le Jour 2 est fait — sinon la liste est juste vide, pas grave)

## Prochaine étape (Jour 4)

Le module de comparaison temporelle — déjà codé lui aussi
(`crud.compute_comparison`, endpoint `POST /comparisons/`).

---

# Jour 4 : Comparaison temporelle et détection de changement

Là aussi, le code est prêt. Ce module compare deux années déjà
traitées au Jour 2 : il lit les deux masques eau/non-eau, calcule eau
gagnée / perdue / stable, produit un raster de changement et un
GeoJSON vectorisé (pour affichage sur une carte au Jour 6).

## Tester

Dans `/docs` (http://localhost:8000/docs), ouvrir `POST /comparisons/`
→ "Try it out" → remplir :
```json
{
  "lake_id": 1,
  "year_a": 2018,
  "year_b": 2026,
  "method": "NDWI+Otsu"
}
```
→ Execute.

Vous devez obtenir : `surface_a_ha`, `surface_b_ha`,
`variation_absolute_ha`, `variation_relative_pct`, `water_gained_ha`,
`water_lost_ha`, `water_stable_ha`, et le chemin du GeoJSON généré.

**Condition indispensable** : les indicateurs des deux années
(`year_a` et `year_b`) doivent déjà exister en base — donc `process_indices.py`
(Jour 2) doit avoir tourné avec succès pour ces deux années précises.
Si ce n'est pas le cas, l'API renvoie une erreur 400 explicite plutôt
qu'un résultat silencieusement faux.

## Fin de journée — critères de validation

- [ ] `POST /comparisons/` renvoie un résultat cohérent pour deux années
      disponibles
- [ ] Le fichier `change_<A>_<B>.geojson` est bien créé dans
      `backend/data/processed/`
- [ ] La variation absolue = surface_b - surface_a (contrôle de cohérence
      automatique, cf. rapport section 12.4)
- [ ] Tester avec une année manquante → erreur 400 claire, pas de plantage

## Prochaine étape (Jour 5)

Module Machine Learning : constituer un jeu d'échantillons, entraîner
Random Forest et SVM, calculer la vraie matrice de confusion.

---

# Jour 5 : Machine Learning (Random Forest vs SVM)

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt   # ajoute scikit-learn, joblib
cd scripts
python train_ml.py
```

Le script échantillonne des pixels eau/non-eau à partir des masques
Otsu du Jour 2, entraîne les deux modèles avec validation croisée
5-fold, et sauvegarde tout dans `backend/data/models/`.

**Limite assumée** (à mentionner si on vous la demande) : les labels
viennent du masque Otsu lui-même, pas d'une annotation manuelle
indépendante — c'est un raccourci pour tenir le délai d'une semaine,
pas un vrai protocole de validation scientifique (le rapport
section 6.5 recommande des échantillons vérifiés manuellement).

Vérifier : `GET http://localhost:8000/ml/metrics` (une fois le backend
relancé) doit renvoyer les métriques réelles.

## Fin de journée — critères de validation

- [ ] `train_ml.py` termine sans erreur
- [ ] `ml_metrics.json` contient des valeurs cohérentes entre elles
      (accuracy/précision/rappel/F1/kappa calculés depuis LA MÊME
      matrice de confusion — pas de valeurs affichées différentes comme
      dans la maquette section 6.6)
- [ ] L'importance des variables (Random Forest) semble plausible
      (NDWI/MNDWI généralement dominants)

---

# Jour 6 : Frontend connecté à l'API

Le code React est fourni (`frontend/src/`), mais il vous faut d'abord
scaffolder le projet Vite (si pas déjà fait au Jour 1) puis copier ces
fichiers par-dessus.

```bash
cd frontend
npm create vite@latest . -- --template react   # si pas déjà fait, répondre "Ignore files and continue" si le dossier n'est pas vide
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install leaflet react-leaflet recharts
```

Puis vérifier que `tailwind.config.js` et `src/index.css` fournis sont
bien en place, et que `src/main.jsx` importe `./index.css` (par défaut
avec Vite, c'est déjà le cas — juste vérifier le nom du fichier).

Lancer :
```bash
npm run dev
```

Ouvrir http://localhost:5173 — le dashboard doit se connecter à l'API
sur `http://localhost:8000` (le backend doit tourner en parallèle).

**Composants fournis** :
- `src/api.js` — un seul endroit pour tous les appels backend
- `src/App.jsx` — dashboard principal (indicateurs clés + graphique)
- `src/components/TimeSeriesChart.jsx` — évolution de la surface (recharts)
- `src/components/ComparisonPanel.jsx` — comparaison de deux années

**Non fourni** (par manque de temps, à ajouter si le temps le permet) :
la carte Leaflet interactive et la page Machine Learning dédiée — le
endpoint `/ml/metrics` existe déjà côté backend, il ne reste qu'à
l'appeler depuis un composant React similaire à `ComparisonPanel.jsx`.

## Fin de journée — critères de validation

- [ ] `npm run dev` démarre sans erreur
- [ ] Le dashboard affiche le vrai nom du lac (pas de texte statique)
- [ ] Le graphique affiche les vraies surfaces du Jour 2
- [ ] Le panneau de comparaison fonctionne et affiche un vrai résultat

---

# Jour 7 : Rapports, exports, tests et finition

## 1. Rapport PDF et exports (déjà codés côté backend)

Une fois le backend relancé (`uvicorn app.main:app --reload`) :
- `GET http://localhost:8000/reports/1/pdf` → télécharge un PDF avec
  la série temporelle complète et la traçabilité (méthode, seuil,
  nuages)
- `GET http://localhost:8000/reports/1/export.csv` → export CSV brut

## 2. Lancer les tests

```bash
cd backend
pytest tests/ -v
```

Ces tests couvrent une partie des cas limites du rapport (section 14.1) :
masque manquant, deux masques de dimensions incompatibles, logique
eau gagnée/perdue/stable, division par zéro sur la variation relative.

## 3. Dernière passe de cohérence (section 12 du rapport)

- [ ] Le dashboard, le graphique et le PDF affichent-ils exactement
      les mêmes surfaces pour une même année ? (ils doivent tous passer
      par `crud.get_indicators_timeseries` — vérifier qu'aucun composant
      ne recalcule une surface de son côté)
- [ ] Les années à forte couverture nuageuse sont-elles visibles/signalées
      quelque part dans l'interface ?
- [ ] Le README et le code sont-ils cohérents avec ce qui a réellement
      été testé (pas seulement écrit) ?

## Ce qui reste volontairement hors scope de cette semaine

Pour respecter le délai d'une semaine, ont été laissés de côté :
authentification multi-rôles, alertes automatiques, planification des
mises à jour, validation hydrologique croisée avec des données ONEE,
carte Leaflet interactive, page ML dédiée dans le frontend. Ce sont
les prochaines étapes naturelles une fois le MVP validé.

