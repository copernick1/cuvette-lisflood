# GUIDE D'UTILISATION - LISFLOOD-FP DANS QGIS

Ce guide explique comment lancer une simulation LISFLOOD-FP graphiquement dans QGIS 3.28.

## 1. Installation des fichiers
1. Décompressez tous les fichiers `.py` dans un dossier (ex: `C:\lisflood_scripts\`).
2. **IMPORTANT - La DLL** : Vous devez d'abord compiler `lisflood.dll`.
   - Allez dans le dossier `lisflood-fp-bmi-v5.9`.
   - Ouvrez un terminal **MSYS2 (MinGW 64-bit)**.
   - Tapez la commande : `mingw32-make -f makefile_win`.
   - Cela va créer `lisflood.dll` et `lisflood.exe`.

## 2. Lancement Interactif (Simple)
Dans la **Console Python** de QGIS, collez ces 3 lignes :

```python
import sys
sys.path.insert(0, r"C:\lisflood_scripts") # Mettez votre chemin ici
import lisflood_qgis_runner as lfr
lfr.interactive_run()
```

## 3. Ce que le script va vous demander :
1. **Choisir lisflood.dll** : Allez chercher le fichier que vous venez de compiler.
2. **Choisir le fichier .par** : Votre fichier de configuration du modèle.
3. **Choisir le raster DEM** : Le fichier `.tif` qui sert de base au calcul.
4. **Choisir le dossier de sortie** : Là où vous voulez enregistrer les résultats.
5. **Choisir la pluie** : Une fenêtre s'ouvre pour entrer la valeur (ex: `0.015` pour 15 mm).

## 4. Résultats
- Le calcul tourne en affichant la progression dans la console.
- QGIS reste utilisable (ne gèle pas).
- À la fin, les cartes de hauteur d'eau s'ajoutent automatiquement à votre projet QGIS.

## 5. Pourquoi utiliser ce script ?
- **Compatible NumPy 2.x** : Évite les crashs de QGIS.
- **V:\ Drive** : Copie automatiquement la DLL en local pour la rapidité.
- **Auto-chargement** : Pas besoin d'importer les rasters manuellement.
