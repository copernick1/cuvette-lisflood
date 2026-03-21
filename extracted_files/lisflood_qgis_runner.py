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

# Tentative d'importation de QGIS pour la réactivité de l'interface
try:
    from qgis.PyQt.QtCore import QCoreApplication
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

# ---------------------------------------------------------------------------
# Configuration — à adapter à votre projet
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "dll_path":    r"C:\lisflood_model\lisflood.dll",
    "par_file":    r"C:\lisflood_model\mon_projet.par",
    "dem_path":    r"C:\lisflood_model\dem.tif",
    "rain_path":   None, # Chemin vers un raster de pluie optionnel
    "output_dir":  r"C:\lisflood_model\outputs",
    "local_temp":  r"C:\temp\lisflood_run",
    "export_vars": ["water depth", "water surface elevation"],
    "export_every_n_steps": 10,
    "checkpoint_every_s": 300, # 5 minutes
    "display_in_qgis": True,
    "qml_style": None,
}

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from lisflood_bmi_ctypes import LisfloodBMI
from raster_io_safe import read_raster_info, write_raster_safe, read_raster_safe

def setup_local_workspace(cfg):
    """Copie les fichiers critiques en local pour améliorer les perfs (réseau V:)."""
    os.makedirs(cfg["local_temp"], exist_ok=True)

    local_cfg = cfg.copy()

    # Copie de la DLL et de l'EXE s'ils existent
    dll_name = os.path.basename(cfg["dll_path"])
    local_dll = os.path.join(cfg["local_temp"], dll_name)
    if not os.path.exists(local_dll) or os.path.getmtime(cfg["dll_path"]) > os.path.getmtime(local_dll):
        print(f"[Runner] Copie de la DLL vers local : {local_dll}")
        shutil.copy2(cfg["dll_path"], local_dll)
    local_cfg["dll_path"] = local_dll

    # Note: On ne copie pas forcément tous les fichiers d'entrée car LISFLOOD
    # les lit via le .par. Idéalement, le .par devrait aussi pointer vers le local.
    return local_cfg

def run(cfg: dict = None):
    if cfg is None: cfg = DEFAULT_CONFIG

    # 1. Setup local
    if cfg.get("local_temp"):
        run_cfg = setup_local_workspace(cfg)
    else:
        run_cfg = cfg

    os.makedirs(run_cfg["output_dir"], exist_ok=True)

    # 2. Initialisation
    print("[Runner] Initialisation du modèle...")
    model = LisfloodBMI(run_cfg["dll_path"])
    model.initialize(run_cfg["par_file"])

    # Gestion de la pluie si fournie
    if run_cfg.get("rain_path"):
        print(f"[Runner] Chargement de la pluie : {run_cfg['rain_path']}")
        rain_arr, _, _, _ = read_raster_safe(run_cfg["rain_path"])
        model.set_value("rain", rain_arr)

    t_start = model.get_start_time()
    t_end   = model.get_end_time()

    print(f"[Runner] Simulation : {t_start} -> {t_end}")

    # 3. Boucle
    step = 0
    last_checkpoint_t = time.time()
    t_wall_start = time.time()
    last_exported = {}

    try:
        while model.get_current_time() < t_end:
            model.update()
            step += 1
            t_now = model.get_current_time()

            # Heartbeat console
            if step % 10 == 0:
                elapsed = time.time() - t_wall_start
                print(f"[HEARTBEAT] t={t_now:.2f} | Pas {step} | Cumulé: {elapsed:.1f}s")

            # Réactivité QGIS
            if HAS_QGIS and step % 5 == 0:
                QCoreApplication.processEvents()

            # Checkpoint périodique (Pickle)
            if time.time() - last_checkpoint_t > run_cfg["checkpoint_every_s"]:
                _save_checkpoint(model, run_cfg, t_now)
                last_checkpoint_t = time.time()

            # Export
            if run_cfg["export_every_n_steps"] > 0 and step % run_cfg["export_every_n_steps"] == 0:
                last_exported = _export_step(model, run_cfg, t_now, step)

    except Exception as e:
        print(f"[ERREUR] Simulation interrompue : {e}")
        _save_checkpoint(model, run_cfg, model.get_current_time(), suffix="_CRASH")
    finally:
        print("[Runner] Finalisation...")
        last_exported = _export_step(model, run_cfg, model.get_current_time(), step, suffix="_FINAL")
        model.finalize()

    if run_cfg.get("display_in_qgis") and last_exported:
        _load_layers_qgis(last_exported, run_cfg.get("qml_style"))

    return last_exported

def _save_checkpoint(model, cfg, t_now, suffix=""):
    """Sauvegarde l'état des variables principales en cas de crash."""
    checkpoint_path = os.path.join(cfg["output_dir"], f"checkpoint_t{t_now:.0f}{suffix}.pkl")
    data = {}
    for var in cfg["export_vars"]:
        try:
            data[var] = model.get_value(var)
        except: pass

    with open(checkpoint_path, "wb") as f:
        pickle.dump(data, f)
    print(f"[CHECKPOINT] Sauvegardé : {checkpoint_path}")

def _export_step(model, cfg, t_now, step, suffix=""):
    exported = {}
    ref_info = read_raster_info(cfg["dem_path"])
    for var in cfg["export_vars"]:
        try:
            arr = model.get_value(var)
            if arr.ndim == 1:
                arr = arr.reshape((ref_info["nrows"], ref_info["ncols"]))

            safe_name = var.replace(" ", "_")
            fname = os.path.join(cfg["output_dir"], f"{safe_name}_t{t_now:010.2f}{suffix}.tif")
            write_raster_safe(fname, arr.astype(np.float32), ref_info["geo"], ref_info["proj"], nodata=-9999.0)
            exported[var] = fname
        except Exception as e:
            print(f"[WARN] Echec export {var}: {e}")
    return exported

def _load_layers_qgis(exported_dict, qml_style=None):
    if not HAS_QGIS: return
    from qgis.core import QgsRasterLayer, QgsProject
    project = QgsProject.instance()
    for var, path in exported_dict.items():
        layer_name = f"LISFLOOD - {var}"
        existing = project.mapLayersByName(layer_name)
        for lyr in existing: project.removeMapLayer(lyr.id())
        layer = QgsRasterLayer(path, layer_name)
        if layer.isValid():
            if qml_style: layer.loadNamedStyle(qml_style)
            project.addMapLayer(layer)

def quick_run(dll, par, dem, out, rain=None):
    cfg = DEFAULT_CONFIG.copy()
    cfg.update({
        "dll_path": dll, "par_file": par, "dem_path": dem,
        "output_dir": out, "rain_path": rain
    })
    return run(cfg)
