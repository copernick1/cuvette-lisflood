# GUIDE D'UTILISATION - LISFLOOD-FP DANS QGIS

Ce guide explique comment lancer une simulation LISFLOOD-FP directement dans QGIS 3.28, en contournant les conflits NumPy et en gérant la pluie.

## 1. Installation des fichiers
1. Copiez tous les fichiers `.py` (`lisflood_qgis_runner.py`, `lisflood_bmi_ctypes.py`, `raster_io_safe.py`) dans un dossier accessible, par exemple `C:\lisflood_scripts\`.
2. Assurez-vous d'avoir votre `lisflood.dll` compilée (voir section Compilation plus bas).

## 2. Lancement depuis QGIS
1. Ouvrez QGIS et la **Console Python** (`Plugins` -> `Python Console`).
2. Copiez et collez le code suivant en adaptant les chemins :

```python
import sys
import os

# 1. Ajouter le chemin des scripts
script_dir = r"C:\lisflood_scripts"
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import lisflood_qgis_runner as lfr

# 2. Définir les fichiers
dll = r"C:\lisflood_model\lisflood.dll"
par = r"C:\lisflood_model\mon_projet.par"
dem = r"C:\lisflood_model\dem.tif"
out = r"C:\lisflood_model\outputs"

# 3. Lancer avec 15 mm de pluie uniforme (0.015 mètres)
lfr.quick_run(dll, par, dem, out, rain=0.015)

# OU Lancer avec un fichier de pluie spécifique (.tif)
# lfr.quick_run(dll, par, dem, out, rain=r"C:\lisflood_model\pluie_15mm.tif")
```

## 3. Ce qui se passe pendant le calcul
- **Heartbeat** : Des messages s'affichent dans la console toutes les 10 itérations pour montrer que le calcul avance.
- **Réactivité** : L'interface QGIS ne devrait pas geler ("Ne répond pas"), vous pouvez bouger la fenêtre.
- **Checkpoints** : Toutes les 5 minutes, l'état est sauvegardé dans un fichier `.pkl` dans le dossier `outputs`.
- **Affichage** : À la fin (ou périodiquement), les rasters de hauteur d'eau sont automatiquement chargés dans votre projet QGIS.

## 4. Compilation de lisflood.dll (Rappel)
Si vous n'avez pas la DLL, utilisez **MSYS2 (MinGW 64-bit)** :
1. `cd` vers le dossier source `lisflood-fp-bmi-v5.9`.
2. Lancez `mingw32-make -f makefile_win`.

## 5. Gestion des erreurs
- Si vous avez un message `AttributeError: _ARRAY_API not found`, c'est que vous utilisez `ReadAsArray()` au lieu de `raster_io_safe.py`. Mes scripts utilisent la méthode sécurisée.
- Si la DLL ne charge pas, vérifiez que `lisflood.exe` est bien présent dans le même dossier que `lisflood.dll`.
