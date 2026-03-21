# =============================================================================
# diagnostic_qgis.py
# À lancer EN PREMIER depuis la console Python QGIS
# Vérifie que l'environnement est compatible avant de lancer LISFLOOD
# =============================================================================
import sys, os, ctypes, struct, platform

def run_diagnostic(dll_path: str = None):
    """
    Lance une série de tests d'environnement.
    Appelez avec le chemin de votre DLL pour tester aussi le chargement.
    """
    print("=" * 65)
    print("  DIAGNOSTIC ENVIRONNEMENT LISFLOOD-QGIS")
    print("=" * 65)

    # ------------------------------------------------------------------
    # 1. Python
    # ------------------------------------------------------------------
    print(f"\n[1] Python : {sys.version}")
    print(f"    Platform : {platform.platform()}")
    print(f"    Arch     : {platform.architecture()[0]}")
    _ok("Python >= 3.8" , sys.version_info >= (3, 8))

    # ------------------------------------------------------------------
    # 2. NumPy — détection du conflit 1.x vs 2.x
    # ------------------------------------------------------------------
    print("\n[2] NumPy")
    try:
        import numpy as np
        version = np.__version__
        print(f"    Version NumPy : {version}")
        print(f"    Emplacement   : {np.__file__}")

        # Test frombuffer (méthode utilisée dans nos modules)
        raw = struct.pack("4f", 1.0, 2.0, 3.0, 4.0)
        arr = np.frombuffer(raw, dtype=np.float32)
        _ok("np.frombuffer()", len(arr) == 4 and abs(arr[2] - 3.0) < 1e-5)

        # Test de gdal_array (optionnel — on s'attend à ce qu'il échoue)
        print("    Test gdal_array (optionnel) :", end=" ")
        try:
            from osgeo import gdal_array
            print("OK (disponible)")
        except Exception as e:
            print(f"ABSENT/CONFLIT — OK, contournement actif ({e})")

    except ImportError as e:
        print(f"    ❌ NumPy indisponible : {e}")

    # ------------------------------------------------------------------
    # 3. GDAL
    # ------------------------------------------------------------------
    print("\n[3] GDAL")
    try:
        from osgeo import gdal
        gdal.UseExceptions()
        print(f"    Version GDAL : {gdal.__version__}")
        _ok("GDAL importé", True)

        # Test ReadRaster sans gdal_array
        print("    Test ReadRaster ligne par ligne :", end=" ")
        _test_readraster_safe()

    except ImportError:
        try:
            import gdal
            print(f"    GDAL (import direct) : {gdal.__version__}")
            _ok("GDAL importé", True)
        except Exception as e:
            print(f"    ❌ GDAL indisponible : {e}")

    # ------------------------------------------------------------------
    # 4. ctypes (critique pour la DLL)
    # ------------------------------------------------------------------
    print("\n[4] ctypes")
    _ok("ctypes disponible", True)  # toujours présent en Python std
    # Test d'un appel ctypes basique
    try:
        buf = ctypes.create_string_buffer(32)
        ctypes.memset(buf, 0, 32)
        _ok("ctypes.create_string_buffer", True)
    except Exception as e:
        _ok("ctypes.create_string_buffer", False, str(e))

    # ------------------------------------------------------------------
    # 5. Chargement de lisflood.dll
    # ------------------------------------------------------------------
    print("\n[5] lisflood.dll")
    if dll_path is None:
        print("    ⚠️  Aucun chemin DLL fourni — test ignoré.")
        print("    Appelez diagnostic_qgis.run_diagnostic(r'C:\\...\\lisflood.dll')")
    else:
        if not os.path.isfile(dll_path):
            print(f"    ❌ Fichier introuvable : {dll_path}")
        else:
            dll_dir = os.path.dirname(os.path.abspath(dll_path))
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH","")
            try:
                lib = ctypes.CDLL(dll_path)
                print(f"    ✅ DLL chargée : {dll_path}")

                # Vérifie les fonctions BMI essentielles
                fns_required = [
                    "initialize", "update", "finalize",
                    "get_current_time", "get_end_time", "get_value",
                ]
                for fn in fns_required:
                    has = hasattr(lib, fn)
                    _ok(f"  DLL.{fn}()", has)

            except OSError as e:
                print(f"    ❌ Échec chargement DLL : {e}")
                print("    → Vérifiez que lisflood.exe est dans le même dossier")
                print("    → Vérifiez que MinGW / MSVC runtime est installé")

    # ------------------------------------------------------------------
    # 6. QGIS
    # ------------------------------------------------------------------
    print("\n[6] QGIS")
    try:
        from qgis.core import QgsProject, QgsRasterLayer
        print(f"    ✅ qgis.core disponible")
        print(f"    Projet : {QgsProject.instance().fileName() or '(sans nom)'}")
    except ImportError:
        print("    ⚠️  qgis.core absent (normal si hors QGIS)")

    # ------------------------------------------------------------------
    # 7. Résumé
    # ------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  Modules lisflood_qgis — vérification des imports")
    print("=" * 65)
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    for module_file in ["lisflood_bmi_ctypes.py", "raster_io_safe.py",
                         "lisflood_qgis_runner.py"]:
        path = os.path.join(_this_dir, module_file)
        _ok(module_file, os.path.isfile(path),
            "MANQUANT" if not os.path.isfile(path) else "")

    print("\n✅ Diagnostic terminé. Si tout est vert, vous pouvez lancer la simulation.")
    print("   → import lisflood_qgis_runner as lfr")
    print("   → lfr.quick_run(dll_path=..., par_file=..., dem_path=..., output_dir=...)")
    print("=" * 65)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _ok(label, condition, note=""):
    status = "✅" if condition else "❌"
    suffix = f"  [{note}]" if note else ""
    print(f"    {status}  {label}{suffix}")


def _test_readraster_safe():
    """
    Crée un raster MEM en mémoire et le relit ligne par ligne
    pour valider le contournement gdal_array.
    """
    import struct, numpy as np
    try:
        from osgeo import gdal
    except ImportError:
        import gdal

    driver = gdal.GetDriverByName("MEM")
    ds = driver.Create("", 5, 3, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((0, 1, 0, 3, 0, -1))
    band = ds.GetRasterBand(1)

    data = [[float(i * 5 + j) for j in range(5)] for i in range(3)]
    for r, row in enumerate(data):
        raw = struct.pack("5f", *row)
        band.WriteRaster(0, r, 5, 1, raw, 5, 1, gdal.GDT_Float32)

    arr = np.empty((3, 5), dtype=np.float32)
    for row in range(3):
        raw = band.ReadRaster(0, row, 5, 1, 5, 1, gdal.GDT_Float32)
        arr[row, :] = np.frombuffer(raw, dtype=np.float32)

    ds = None
    ok = (arr[1, 2] == 7.0)
    if ok:
        print("OK")
    else:
        print(f"ERREUR (valeur={arr[1,2]}, attendu=7.0)")


# =============================================================================
# Lancement direct depuis la console QGIS
# =============================================================================
if __name__ == "__main__":
    run_diagnostic()
