# PLAN D'ARCHITECTURE — LISFLOOD-FP BMI dans QGIS
## Sans installation, sans conflit NumPy
### Environnement : QGIS 3.28 / Python 3.9 embarqué / Windows 10-11 / NumPy 2.0.2

---

## 1. PROBLÈME RÉSOLU

| Problème | Cause | Solution retenue |
|---|---|---|
| `gdal_array` crashe | NumPy 2.0.2 vs NumPy 1.x QGIS | ReadRaster ligne par ligne + `np.frombuffer()` |
| `bmi-python` non installable | Pas de pip dans QGIS embarqué | Wrapper ctypes pur (zéro dépendance) |
| `matplotlib` crashe | Même conflit NumPy | Non utilisé — sorties GeoTIFF + QGIS natif |
| DLL introuvable | PATH Windows | Injection automatique dans `os.environ["PATH"]` |

---

## 2. STRUCTURE DES FICHIERS

```
C:\lisflood_qgis\              ← Dossier de travail (à créer)
  ├── lisflood_bmi_ctypes.py   ← Wrapper BMI ctypes PUR (fourni)
  ├── raster_io_safe.py        ← Lecture/écriture GDAL sans gdal_array (fourni)
  ├── lisflood_qgis_runner.py  ← Orchestrateur principal (fourni)
  └── diagnostic_qgis.py       ← Test de l'environnement (fourni)

C:\lisflood_model\             ← Votre projet LISFLOOD
  ├── lisflood.dll             ← DLL du modèle (depuis le repo GitHub)
  ├── lisflood.exe             ← Exécutable (doit être dans le même dossier)
  ├── mon_projet.par           ← Fichier paramètre LISFLOOD-FP
  ├── dem.tif                  ← DEM de référence
  ├── bci_file.bci             ← Conditions aux limites
  └── outputs\                 ← Sorties GeoTIFF (créé automatiquement)
```

---

## 3. OBTENIR lisflood.dll

### Option A — Binaire précompilé (recommandé, rapide)
Le repo GitHub `openearth/lisflood-fp-bmi` ne fournit PAS de DLL précompilée.
Vous devez compiler avec **MinGW** sous Windows :

```bash
# Dans Git Bash / MSYS2 :
git clone https://github.com/openearth/lisflood-fp-bmi.git
cd lisflood-fp-bmi/lisflood-fp-bmi-v5.9
mingw32-make -f makefile_win
# → génère lisflood.dll et lisflood.exe dans le même dossier
```

**Prérequis compilation :**
- [MSYS2](https://www.msys2.org/) avec `pacman -S mingw-w64-x86_64-gcc`
- Ou TDM-GCC / MinGW-w64

### Option B — Utiliser le GLOFRIM repository
```bash
git clone https://github.com/openearth/glofrim.git
# Le repo GLOFRIM contient parfois des binaires précompilés
```

### Option C — Contact University of Bristol
Pour un binaire officiel, contacter : paul.bates@Bristol.ac.uk

---

## 4. MISE EN PLACE ÉTAPE PAR ÉTAPE

### Étape 1 — Copier les fichiers Python
```
Copiez les 4 fichiers .py dans C:\lisflood_qgis\
(ou tout autre dossier accessible, y compris V:\ réseau)
```

### Étape 2 — Diagnostic (console Python QGIS)
```python
import sys
sys.path.insert(0, r"C:\lisflood_qgis")

import diagnostic_qgis as diag
diag.run_diagnostic(r"C:\lisflood_model\lisflood.dll")
```
→ Tous les ✅ doivent passer avant de continuer.

### Étape 3 — Simulation complète
```python
import sys
sys.path.insert(0, r"C:\lisflood_qgis")

import lisflood_qgis_runner as lfr

lfr.quick_run(
    dll_path   = r"C:\lisflood_model\lisflood.dll",
    par_file   = r"C:\lisflood_model\mon_projet.par",
    dem_path   = r"C:\lisflood_model\dem.tif",
    output_dir = r"C:\lisflood_model\outputs",
    export_vars    = ["water depth", "water surface elevation"],
    export_every   = 10,        # exporter tous les 10 pas de temps
)
```
→ Les rasters GeoTIFF s'ouvrent automatiquement dans QGIS.

### Étape 4 — Mode interactif (pas-à-pas)
```python
# Initialisation manuelle
model = lfr.step_by_step(
    dll_path = r"C:\lisflood_model\lisflood.dll",
    par_file = r"C:\lisflood_model\mon_projet.par"
)

# Avancer manuellement
model.update()

# Lire une variable
import numpy as np
depth = model.get_value("water depth")
print(f"Profondeur max : {np.nanmax(depth):.3f} m")

# Modifier une variable (couplage)
model.set_value("n", manning_array)

# Terminer
model.finalize()
```

---

## 5. VARIABLES BMI LISFLOOD-FP v5.9

| Nom BMI | Description | Unité |
|---|---|---|
| `water depth` | Hauteur d'eau | m |
| `water surface elevation` | Cote de la surface libre | m |
| `qx` | Débit en X | m²/s |
| `qy` | Débit en Y | m²/s |
| `dem` | Modèle numérique de terrain | m |
| `n` | Coefficient de Manning | — |

---

## 6. LECTURE RASTER SÉCURISÉE (rappel technique)

```python
# ✅ MÉTHODE SÛRE — utilisée dans raster_io_safe.py
from osgeo import gdal
import numpy as np

ds   = gdal.Open("fichier.tif")
band = ds.GetRasterBand(1)
nrows, ncols = ds.RasterYSize, ds.RasterXSize
arr  = np.empty((nrows, ncols), dtype=np.float32)

for row in range(nrows):
    raw = band.ReadRaster(0, row, ncols, 1,
                          ncols, 1, gdal.GDT_Float32)
    arr[row, :] = np.frombuffer(raw, dtype=np.float32)

# ❌ À ÉVITER absolument dans cet environnement :
# arr = band.ReadAsArray()          → crashe avec NumPy 2.x
# from osgeo import gdal_array      → AttributeError
# import matplotlib.pyplot as plt   → crashe
```

---

## 7. RÉSEAU V:\ — POINTS D'ATTENTION

- Tous les chemins fonctionnent en UNC : `r"V:\projet\lisflood_model\"`
- La DLL doit être **locale** ou sur un lecteur réseau mappé (pas UNC pur)
- Si `lisflood.dll` est sur V:\, copier localement pour éviter les timeouts :
  ```python
  import shutil
  shutil.copy(r"V:\modeles\lisflood.dll", r"C:\temp\lisflood.dll")
  ```

---

## 8. DÉPANNAGE FRÉQUENT

| Erreur | Cause probable | Solution |
|---|---|---|
| `OSError: [WinError 126]` | DLL introuvable ou dépendances manquantes | Mettre `lisflood.exe` dans le même dossier que `lisflood.dll` |
| `OSError: [WinError 193]` | DLL 32-bit vs Python 64-bit | Recompiler en 64-bit avec `mingw64` |
| `AttributeError: initialize` | Mauvaise DLL (pas BMI) | Utiliser la DLL du repo `lisflood-fp-bmi` |
| `RuntimeError: initialize() code 1` | Fichier .par introuvable | Vérifier le chemin et que tous les fichiers du modèle sont présents |
| `get_value` retourne des NaN | Variable non initialisée | Appeler `model.update()` avant `get_value()` |

---

## 9. ARCHITECTURE DES MODULES

```
diagnostic_qgis.py
    └── vérifie : Python, NumPy, GDAL, ctypes, DLL, QGIS

lisflood_bmi_ctypes.py          raster_io_safe.py
    ├── LisfloodBMI                 ├── read_raster_safe()
    │   ├── initialize()            ├── read_raster_window_safe()
    │   ├── update()                ├── write_raster_safe()
    │   ├── get_value()  ──────────►├── write_raster_from_bmi()
    │   ├── set_value()             ├── coords_to_pixel()
    │   └── finalize()              └── reproject_array()
    │
    └── lisflood_qgis_runner.py
            ├── run()         ← simulation complète
            ├── quick_run()   ← interface simplifiée
            └── step_by_step() ← mode interactif
```
