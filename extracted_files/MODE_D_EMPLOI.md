# MODE D'EMPLOI — LISFLOOD-FP DANS QGIS (SANS INSTALLATION)

Ce guide est conçu pour vous permettre de lancer LISFLOOD-FP sans rien installer et sans compiler de code.

## 1. Ce qu'il vous faut
- Vos fichiers de modèle (`.par`, `.tif`, etc.).
- Le fichier **`lisflood.exe`** (ou `lisflood.dll` si vous l'avez déjà).
- Les scripts Python fournis (`lisflood_qgis_runner.py`, `lisflood_bmi_ctypes.py`, `raster_io_safe.py`).

## 2. Lancement simple (Interface graphique)
1. Décompressez les scripts dans un dossier, par exemple `C:\Scripts\`.
2. Ouvrez la **Console Python** de QGIS (`Plugins` -> `Python Console`).
3. Copiez et collez ces 4 lignes en adaptant votre chemin :

```python
import sys
sys.path.insert(0, r"C:\Scripts") # Mettez votre dossier ici
import lisflood_qgis_runner as lfr
lfr.interactive_run()
```

## 3. Utilisation de l'interface
Des fenêtres vont s'ouvrir l'une après l'autre :
1. **Choisir le moteur** : Sélectionnez votre fichier `lisflood.exe` (ou DLL).
2. **Choisir le projet** : Sélectionnez votre fichier `.par`.
3. **Choisir le terrain** : Sélectionnez votre fichier `.tif` (DEM).
4. **Choisir la sortie** : Sélectionnez le dossier où enregistrer les résultats.
5. **Choisir la pluie** : Entrez la valeur (ex: `0.015` pour 15 mm).

## 4. Résultats
- Le calcul va tourner et afficher les messages dans la console QGIS.
- Si vous utilisez une DLL, les cartes s'ajouteront toutes seules dans QGIS.
- Si vous utilisez un EXE, les fichiers de résultats (`.wd`, `.elev`) seront écrits dans votre dossier de sortie.

## 5. Pourquoi c'est mieux ?
- **Aucune installation** : Pas besoin de droits administrateur ou de MSYS2.
- **Zéro crash** : Le script évite les conflits NumPy de QGIS.
- **Simple** : Pas besoin de modifier le code, tout se fait via des fenêtres.
