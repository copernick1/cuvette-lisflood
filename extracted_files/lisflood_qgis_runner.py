# =============================================================================
# lisflood_qgis_runner.py
# Script principal — à lancer depuis la console Python QGIS
# Supporte : DLL (BMI) ou EXE (Standard) — ZÉRO INSTALLATION
# =============================================================================
import os
import sys
import time
import shutil
import pickle
import subprocess
import numpy as np

# Tentative d'importation de QGIS pour l'interface graphique
try:
    from qgis.PyQt.QtCore import QCoreApplication
    from qgis.PyQt.QtWidgets import QFileDialog, QInputDialog, QMessageBox
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from lisflood_bmi_ctypes import LisfloodBMI
from raster_io_safe import read_raster_info, write_raster_safe, read_raster_safe

# ---------------------------------------------------------------------------
# Configuration par défaut
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "solver_path": "", # Chemin vers lisflood.dll OU lisflood.exe
    "par_file":    "",
    "dem_path":    "",
    "rain":        None,
    "output_dir":  "",
    "local_temp":  r"C:\temp\lisflood_run",
    "export_vars": ["water depth", "water surface elevation"],
    "export_every_n_steps": 10,
    "checkpoint_every_s": 300,
    "display_in_qgis": True,
}

def interactive_run():
    """Interface graphique pour choisir les fichiers et lancer le calcul."""
    if not HAS_QGIS:
        print("[ERREUR] Ce mode interactif nécessite QGIS.")
        return

    # 1. Sélection du solveur (.dll ou .exe)
    solver, _ = QFileDialog.getOpenFileName(None, "Sélectionnez lisflood.dll OU lisflood.exe", "", "LISFLOOD (*.dll *.exe)")
    if not solver: return

    # 2. Sélection du fichier .par
    par, _ = QFileDialog.getOpenFileName(None, "Sélectionnez le fichier .par", os.path.dirname(solver), "LISFLOOD-FP Parameters (*.par)")
    if not par: return

    # 3. Sélection du DEM de référence
    dem, _ = QFileDialog.getOpenFileName(None, "Sélectionnez le raster DEM (.tif)", os.path.dirname(par), "GeoTIFF (*.tif)")
    if not dem: return

    # 4. Dossier de sortie
    out = QFileDialog.getExistingDirectory(None, "Sélectionnez le dossier pour les résultats", os.path.dirname(par))
    if not out: return

    # 5. Pluie (15 mm par défaut)
    rain_val, ok = QInputDialog.getDouble(None, "Pluie Uniforme (m)", "Entrez la pluie en mètres (ex: 0.015 pour 15mm)", 0.015, 0, 10, 3)
    rain = rain_val if ok else None

    # Lancement
    cfg = DEFAULT_CONFIG.copy()
    cfg.update({"solver_path": solver, "par_file": par, "dem_path": dem, "output_dir": out, "rain": rain})

    QMessageBox.information(None, "LISFLOOD-FP", "Le calcul va commencer. Surveillez la console Python.")
    return run(cfg)

def run(cfg: dict = None):
    if cfg is None: cfg = DEFAULT_CONFIG

    # Choix du mode : DLL (BMI) ou EXE (Legacy)
    if cfg["solver_path"].lower().endswith(".exe"):
        return run_exe_mode(cfg)
    else:
        return run_bmi_mode(cfg)

def run_bmi_mode(cfg):
    """Lancement via DLL et interface BMI."""
    # (Code BMI déjà existant, optimisé pour QGIS)
    os.makedirs(cfg["output_dir"], exist_ok=True)
    print("[BMI] Initialisation via DLL...")
    try:
        model = LisfloodBMI(cfg["solver_path"])
        model.initialize(cfg["par_file"])

        # Gestion pluie
        if cfg["rain"] is not None:
            shape = model.get_var_shape("rain")
            rain_arr = np.full(shape, float(cfg["rain"]), dtype=np.float64)
            model.set_value("rain", rain_arr)

        t_end = model.get_end_time()
        t_wall_start = time.time()
        while model.get_current_time() < t_end:
            model.update()
            if HAS_QGIS: QCoreApplication.processEvents()
            if int(model.get_current_time()) % 10 == 0:
                print(f"[BMI] t={model.get_current_time():.2f}")

        last_exported = _export_step(model, cfg, model.get_current_time(), 0, suffix="_FINAL")
        model.finalize()
        if HAS_QGIS: _load_layers_qgis(last_exported)
        return last_exported
    except Exception as e:
        print(f"[ERREUR BMI] : {e}")

def run_exe_mode(cfg):
    """Lancement via EXE (subprocess) - Plus robuste car indépendant de Python."""
    print("[EXE] Préparation du lancement de lisflood.exe...")
    os.makedirs(cfg["output_dir"], exist_ok=True)

    # Pour la pluie avec l'EXE, LISFLOOD a besoin d'un fichier .rain référencé dans le .par
    # Si l'utilisateur a donné une valeur numérique, on prévient qu'il faut un .par configuré.
    if cfg["rain"] is not None:
        print(f"[NOTE] Pour l'EXE, assurez-vous que votre .par gère déjà la pluie de {cfg['rain']} m.")

    cmd = [cfg["solver_path"], "-v", cfg["par_file"]]
    print(f"[EXE] Commande : {' '.join(cmd)}")

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=os.path.dirname(cfg["par_file"]))
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None: break
            if line:
                print(f"  [LISFLOOD] {line.strip()}")
                if HAS_QGIS: QCoreApplication.processEvents()

        print("[EXE] Calcul terminé. Cherchez les fichiers dans le dossier de sortie configuré dans votre .par.")
        # Note: L'EXE écrit directement ses fichiers (ex: .wd, .elev).
        # On ne peut pas les charger automatiquement sans parser le .par, mais ils sont sur le disque.
    except Exception as e:
        print(f"[ERREUR EXE] : {e}")

def _export_step(model, cfg, t_now, step, suffix=""):
    exported = {}
    ref_info = read_raster_info(cfg["dem_path"])
    for var in cfg["export_vars"]:
        try:
            arr = model.get_value(var)
            if arr.ndim == 1: arr = arr.reshape((ref_info["nrows"], ref_info["ncols"]))
            fname = os.path.join(cfg["output_dir"], f"{var.replace(' ','_')}_t{t_now:010.2f}{suffix}.tif")
            write_raster_safe(fname, arr.astype(np.float32), ref_info["geo"], ref_info["proj"], nodata=-9999.0)
            exported[var] = fname
        except: pass
    return exported

def _load_layers_qgis(exported_dict):
    from qgis.core import QgsRasterLayer, QgsProject
    project = QgsProject.instance()
    for var, path in exported_dict.items():
        layer_name = f"LISFLOOD - {var}"
        existing = project.mapLayersByName(layer_name)
        for lyr in existing: project.removeMapLayer(lyr.id())
        layer = QgsRasterLayer(path, layer_name)
        if layer.isValid(): project.addMapLayer(layer)

def quick_run(solver, par, dem, out, rain=0.015):
    cfg = DEFAULT_CONFIG.copy()
    cfg.update({"solver_path": solver, "par_file": par, "dem_path": dem, "output_dir": out, "rain": rain})
    return run(cfg)
