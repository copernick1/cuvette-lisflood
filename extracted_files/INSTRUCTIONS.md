# INSTRUCTIONS DE COMPILATION - LISFLOOD-FP DLL (WINDOWS)

Pour utiliser LISFLOOD-FP dans QGIS sans conflit NumPy, vous devez compiler la DLL avec MinGW.

## 1. Prérequis
- Installez [MSYS2](https://www.msys2.org/).
- Dans le terminal MSYS2 (MinGW 64-bit), installez GCC :
  `pacman -S mingw-w64-x86_64-gcc`

## 2. Compilation
1. Allez dans le dossier `lisflood-fp-bmi-v5.9`.
2. Lancez la commande suivante :
   `mingw32-make -f makefile_win`

Cela générera deux fichiers importants :
- `lisflood.dll` : La bibliothèque à charger dans le script Python.
- `lisflood.exe` : L'exécutable (doit rester dans le même dossier).

## 3. Utilisation dans QGIS
1. Ouvrez la console Python de QGIS.
2. Ajoutez le chemin des scripts :
   ```python
   import sys
   sys.path.insert(0, r"C:\chemin\vers\scripts_extraits")
   import lisflood_qgis_runner as lfr
   ```
3. Lancez la simulation :
   ```python
   lfr.quick_run(
       dll = r"C:\model\lisflood.dll",
       par = r"C:\model\votre_projet.par",
       dem = r"C:\model\dem.tif",
       out = r"C:\model\outputs",
       rain = r"C:\model\pluie.tif" # Optionnel
   )
   ```

## 4. Notes sur le conflit NumPy
Les scripts `raster_io_safe.py` et `lisflood_bmi_ctypes.py` ont été conçus pour fonctionner même si vous avez NumPy 2.0.2 installé dans votre AppData, en utilisant uniquement des appels à `np.frombuffer` et des accès mémoire directs via `ctypes`.
