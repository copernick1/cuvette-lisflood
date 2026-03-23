# =============================================================================
# lisflood_qgis_runner.py
# Script principal — à lancer depuis la console Python QGIS
# Orchestre : initialisation → boucle → sorties → affichage QGIS
# =============================================================================
import os
import sys
import time
import shutil
import pickle
import numpy as np

# Tentative d'importation de QGIS pour l'interface graphique
try:
    from qgis.PyQt.QtCore import QCoreApplication
    from qgis.PyQt.QtWidgets import QFileDialog, QInputDialog, QMessageBox
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

# ---------------------------------------------------------------------------
# Configuration par défaut
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "dll_path":    "",
    "par_file":    "",
    "dem_path":    "",
    "rain":        None,
    "output_dir":  "",
    "local_temp":  r"C:\temp\lisflood_run",
    "export_vars": ["water depth", "water surface elevation"],
    "export_every_n_steps": 10,
    "checkpoint_every_s": 300,
    "display_in_qgis": True,
    "qml_style": None,
}

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from lisflood_bmi_ctypes import LisfloodBMI
from raster_io_safe import read_raster_info, write_raster_safe, read_raster_safe

def interactive_run():
    """
    Lance une interface graphique dans QGIS pour choisir les fichiers et lancer le calcul.
    """
    if not HAS_QGIS:
        print("[ERREUR] Ce mode interactif nécessite QGIS.")
        return

    # 1. Sélection de la DLL
    dll, _ = QFileDialog.getOpenFileName(None, "Sélectionnez lisflood.dll", "", "DLL (*.dll)")
    if not dll: return

    # 2. Sélection du fichier .par
    par, _ = QFileDialog.getOpenFileName(None, "Sélectionnez le fichier .par", os.path.dirname(dll), "LISFLOOD-FP Parameters (*.par)")
    if not par: return

    # 3. Sélection du DEM de référence (pour la géométrie)
    dem, _ = QFileDialog.getOpenFileName(None, "Sélectionnez le raster DEM (.tif)", os.path.dirname(par), "GeoTIFF (*.tif)")
    if not dem: return

    # 4. Dossier de sortie
    out = QFileDialog.getExistingDirectory(None, "Sélectionnez le dossier pour les résultats", os.path.dirname(par))
    if not out: return

    # 5. Option Pluie (15 mm par défaut)
    rain_val, ok = QInputDialog.getDouble(None, "Pluie Uniforme (m)", "Entrez la pluie en mètres (ex: 0.015 pour 15mm)", 0.015, 0, 10, 3)
    rain = rain_val if ok else None

    # Lancement
    cfg = DEFAULT_CONFIG.copy()
    cfg.update({
        "dll_path": dll,
        "par_file": par,
        "dem_path": dem,
        "output_dir": out,
        "rain": rain
    })

    QMessageBox.information(None, "LISFLOOD-FP", "Le calcul va commencer. Surveillez la console Python pour le suivi.")
    return run(cfg)

def setup_local_workspace(cfg):
    """Copie la DLL en local si nécessaire."""
    if not cfg["dll_path"]: return cfg
    os.makedirs(cfg["local_temp"], exist_ok=True)
    local_cfg = cfg.copy()
    dll_name = os.path.basename(cfg["dll_path"])
    local_dll = os.path.join(cfg["local_temp"], dll_name)
    try:
        if not os.path.exists(local_dll) or os.path.getmtime(cfg["dll_path"]) > os.path.getmtime(local_dll):
            shutil.copy2(cfg["dll_path"], local_dll)
        local_cfg["dll_path"] = local_dll
    except: pass
    return local_cfg

def run(cfg: dict = None):
    if cfg is None: cfg = DEFAULT_CONFIG
    run_cfg = setup_local_workspace(cfg) if cfg.get("local_temp") else cfg
    os.makedirs(run_cfg["output_dir"], exist_ok=True)

    print("[Runner] Initialisation du modèle...")
    try:
        model = LisfloodBMI(run_cfg["dll_path"])
        model.initialize(run_cfg["par_file"])

        rain = run_cfg.get("rain")
        if rain is not None:
            if isinstance(rain, str) and os.path.isfile(rain):
                rain_arr, _, _, _ = read_raster_safe(rain)
                model.set_value("rain", rain_arr)
            elif isinstance(rain, (int, float)):
                shape = model.get_var_shape("rain")
                rain_arr = np.full(shape, float(rain), dtype=np.float64)
                model.set_value("rain", rain_arr)

        t_end = model.get_end_time()
        step = 0
        last_checkpoint_t = time.time()
        t_wall_start = time.time()
        last_exported = {}

        while model.get_current_time() < t_end:
            model.update()
            step += 1
            t_now = model.get_current_time()
            if step % 10 == 0:
                print(f"[HEARTBEAT] t={t_now:.2f} | Pas {step} | Cumulé: {(time.time()-t_wall_start):.1f}s")
            if HAS_QGIS: QCoreApplication.processEvents()
            if time.time() - last_checkpoint_t > run_cfg["checkpoint_every_s"]:
                _save_checkpoint(model, run_cfg, t_now)
                last_checkpoint_t = time.time()
            if run_cfg["export_every_n_steps"] > 0 and step % run_cfg["export_every_n_steps"] == 0:
                last_exported = _export_step(model, run_cfg, t_now, step)

        last_exported = _export_step(model, run_cfg, model.get_current_time(), step, suffix="_FINAL")
        model.finalize()
        print("[Runner] Terminé avec succès.")
        if HAS_QGIS and run_cfg.get("display_in_qgis"):
            _load_layers_qgis(last_exported)
        return last_exported

    except Exception as e:
        print(f"[ERREUR] : {e}")
        if HAS_QGIS: QMessageBox.critical(None, "Erreur LISFLOOD", str(e))

def _save_checkpoint(model, cfg, t_now):
    checkpoint_path = os.path.join(cfg["output_dir"], f"checkpoint_t{t_now:.0f}.pkl")
    data = {}
    for var in cfg["export_vars"]:
        try: data[var] = model.get_value(var)
        except: pass
    with open(checkpoint_path, "wb") as f:
        pickle.dump(data, f)

def _export_step(model, cfg, t_now, step, suffix=""):
    exported = {}
    ref_info = read_raster_info(cfg["dem_path"])
    for var in cfg["export_vars"]:
        try:
            arr = model.get_value(var)
            if arr.ndim == 1:
                arr = arr.reshape((ref_info["nrows"], ref_info["ncols"]))
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

def quick_run(dll, par, dem, out, rain=None):
    cfg = DEFAULT_CONFIG.copy()
    cfg.update({"dll_path": dll, "par_file": par, "dem_path": dem, "output_dir": out, "rain": rain})
    return run(cfg)
