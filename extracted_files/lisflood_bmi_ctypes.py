# =============================================================================
# lisflood_bmi_ctypes.py
# Wrapper BMI 1.0 pour lisflood.dll via ctypes PUR
# Aucune dépendance externe — fonctionne dans QGIS Python 3.9 embarqué
# Compatible NumPy 1.x ET 2.x (n'utilise pas numpy.core ni gdal_array)
# =============================================================================
import ctypes
import os
import sys
import struct
import numpy as np   # NumPy est requis mais uniquement pour np.frombuffer/np.zeros
                     # Aucun appel à numpy.core.multiarray directement

# ---------------------------------------------------------------------------
# Constantes BMI 1.0
# ---------------------------------------------------------------------------
BMI_SUCCESS = 0
BMI_FAILURE = 1
MAX_COMPONENT_NAME = 2000
MAX_VAR_NAME       = 2000
MAX_TYPE_NAME      = 2000
MAX_UNITS_NAME     = 2000


class LisfloodBMI:
    """
    Wrapper ctypes pour LISFLOOD-FP v5.9 (lisflood.dll / liblisflood.so).

    Usage minimal :
        model = LisfloodBMI(r"C:\\chemin\\vers\\lisflood.dll")
        model.initialize(r"C:\\chemin\\vers\\model.par")
        while model.get_current_time() < model.get_end_time():
            model.update()
        model.finalize()
    """

    def __init__(self, dll_path: str):
        """
        Paramètres
        ----------
        dll_path : str
            Chemin absolu vers lisflood.dll (Windows) ou liblisflood.so (Linux).
        """
        if not os.path.isfile(dll_path):
            raise FileNotFoundError(f"DLL introuvable : {dll_path}")

        # Sur Windows, s'assurer que le répertoire de la DLL est dans PATH
        # (lisflood.dll peut avoir des dépendances dans le même dossier)
        dll_dir = os.path.dirname(os.path.abspath(dll_path))
        if dll_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

        # Charge la bibliothèque partagée
        self._lib = ctypes.CDLL(dll_path)
        self._dll_path = dll_path
        self._initialized = False

        # Prépare les signatures de fonctions ctypes
        self._bind_functions()

    # ------------------------------------------------------------------
    # Liaison des fonctions C vers ctypes
    # ------------------------------------------------------------------
    def _bind_functions(self):
        """Déclare argtypes/restype pour chaque fonction BMI exposée."""
        lib = self._lib

        # --- Contrôle du cycle de vie ---
        lib.initialize.argtypes  = [ctypes.c_char_p]
        lib.initialize.restype   = ctypes.c_int

        lib.update.argtypes  = []
        lib.update.restype   = ctypes.c_int

        lib.update_until.argtypes = [ctypes.c_double]
        lib.update_until.restype  = ctypes.c_int

        lib.finalize.argtypes = []
        lib.finalize.restype  = ctypes.c_int

        # --- Informations temporelles ---
        lib.get_start_time.argtypes  = [ctypes.POINTER(ctypes.c_double)]
        lib.get_start_time.restype   = ctypes.c_int

        lib.get_end_time.argtypes    = [ctypes.POINTER(ctypes.c_double)]
        lib.get_end_time.restype     = ctypes.c_int

        lib.get_current_time.argtypes = [ctypes.POINTER(ctypes.c_double)]
        lib.get_current_time.restype  = ctypes.c_int

        lib.get_time_step.argtypes   = [ctypes.POINTER(ctypes.c_double)]
        lib.get_time_step.restype    = ctypes.c_int

        lib.get_time_units.argtypes  = [ctypes.c_char_p]
        lib.get_time_units.restype   = ctypes.c_int

        # --- Informations sur les variables ---
        lib.get_var_type.argtypes  = [ctypes.c_char_p, ctypes.c_char_p]
        lib.get_var_type.restype   = ctypes.c_int

        lib.get_var_units.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.get_var_units.restype  = ctypes.c_int

        lib.get_var_rank.argtypes  = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        lib.get_var_rank.restype   = ctypes.c_int

        lib.get_var_shape.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        lib.get_var_shape.restype  = ctypes.c_int

        lib.get_var_stride.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        lib.get_var_stride.restype  = ctypes.c_int

        # --- Lecture / écriture de valeurs ---
        lib.get_value.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        lib.get_value.restype  = ctypes.c_int

        lib.set_value.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        lib.set_value.restype  = ctypes.c_int

        lib.get_value_at_indices.argtypes = [
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int
        ]
        lib.get_value_at_indices.restype = ctypes.c_int

        lib.set_value_at_indices.argtypes = [
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int
        ]
        lib.set_value_at_indices.restype = ctypes.c_int

        # --- Informations sur le modèle ---
        lib.get_component_name.argtypes = [ctypes.c_char_p]
        lib.get_component_name.restype  = ctypes.c_int

        lib.get_input_var_name_count.argtypes  = [ctypes.POINTER(ctypes.c_int)]
        lib.get_input_var_name_count.restype   = ctypes.c_int

        lib.get_output_var_name_count.argtypes = [ctypes.POINTER(ctypes.c_int)]
        lib.get_output_var_name_count.restype  = ctypes.c_int

        lib.get_input_var_names.argtypes  = [ctypes.POINTER(ctypes.c_char_p)]
        lib.get_input_var_names.restype   = ctypes.c_int

        lib.get_output_var_names.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
        lib.get_output_var_names.restype  = ctypes.c_int

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    def initialize(self, config_file: str) -> None:
        """Initialise le modèle avec le fichier .par spécifié."""
        config_bytes = config_file.encode("utf-8")
        ret = self._lib.initialize(config_bytes)
        if ret != BMI_SUCCESS:
            raise RuntimeError(f"initialize() a échoué (code {ret}) pour : {config_file}")
        self._initialized = True
        print(f"[LISFLOOD-BMI] Modèle initialisé : {config_file}")

    def update(self) -> None:
        """Avance d'un pas de temps."""
        ret = self._lib.update()
        if ret != BMI_SUCCESS:
            raise RuntimeError(f"update() a échoué (code {ret})")

    def update_until(self, time: float) -> None:
        """Avance jusqu'au temps absolu indiqué."""
        ret = self._lib.update_until(ctypes.c_double(time))
        if ret != BMI_SUCCESS:
            raise RuntimeError(f"update_until({time}) a échoué (code {ret})")

    def finalize(self) -> None:
        """Libère les ressources du modèle."""
        if self._initialized:
            ret = self._lib.finalize()
            self._initialized = False
            if ret != BMI_SUCCESS:
                raise RuntimeError(f"finalize() a échoué (code {ret})")
            print("[LISFLOOD-BMI] Modèle finalisé.")

    def __del__(self):
        """Destructeur de sécurité."""
        try:
            self.finalize()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Temps
    # ------------------------------------------------------------------
    def get_start_time(self) -> float:
        val = ctypes.c_double(0.0)
        self._lib.get_start_time(ctypes.byref(val))
        return val.value

    def get_end_time(self) -> float:
        val = ctypes.c_double(0.0)
        self._lib.get_end_time(ctypes.byref(val))
        return val.value

    def get_current_time(self) -> float:
        val = ctypes.c_double(0.0)
        self._lib.get_current_time(ctypes.byref(val))
        return val.value

    def get_time_step(self) -> float:
        val = ctypes.c_double(0.0)
        self._lib.get_time_step(ctypes.byref(val))
        return val.value

    def get_time_units(self) -> str:
        buf = ctypes.create_string_buffer(MAX_UNITS_NAME)
        self._lib.get_time_units(buf)
        return buf.value.decode("utf-8").strip()

    # ------------------------------------------------------------------
    # Métadonnées des variables
    # ------------------------------------------------------------------
    def get_var_type(self, var_name: str) -> str:
        """Retourne le type C de la variable (ex. 'double', 'float')."""
        buf = ctypes.create_string_buffer(MAX_TYPE_NAME)
        self._lib.get_var_type(var_name.encode(), buf)
        return buf.value.decode("utf-8").strip()

    def get_var_units(self, var_name: str) -> str:
        buf = ctypes.create_string_buffer(MAX_UNITS_NAME)
        self._lib.get_var_units(var_name.encode(), buf)
        return buf.value.decode("utf-8").strip()

    def get_var_rank(self, var_name: str) -> int:
        val = ctypes.c_int(0)
        self._lib.get_var_rank(var_name.encode(), ctypes.byref(val))
        return val.value

    def get_var_shape(self, var_name: str) -> list:
        """Retourne la forme (shape) de la variable sous forme de liste Python."""
        rank = self.get_var_rank(var_name)
        shape_arr = (ctypes.c_int * rank)()
        self._lib.get_var_shape(var_name.encode(), shape_arr)
        return list(shape_arr)

    # ------------------------------------------------------------------
    # Lecture de valeurs → NumPy array (SANS numpy.core ni gdal_array)
    # ------------------------------------------------------------------
    _TYPE_MAP = {
        "double": (ctypes.c_double, np.float64),
        "float":  (ctypes.c_float,  np.float32),
        "int":    (ctypes.c_int,    np.int32),
        "long":   (ctypes.c_long,   np.int64),
    }

    def get_value(self, var_name: str) -> np.ndarray:
        """
        Lit une variable BMI et retourne un numpy array.
        N'utilise PAS numpy.core directement — compatible NumPy 1.x et 2.x.
        """
        ctype, dtype = self._resolve_type(var_name)
        shape = self.get_var_shape(var_name)
        n_elements = 1
        for s in shape:
            n_elements *= s

        # Allocation via ctypes (contournement du conflit NumPy)
        buf = (ctype * n_elements)()
        ret = self._lib.get_value(var_name.encode(), buf)
        if ret != BMI_SUCCESS:
            raise RuntimeError(f"get_value('{var_name}') a échoué (code {ret})")

        # Conversion sûre : bytes → numpy via frombuffer (ABI stable)
        raw = bytes(buf)
        arr = np.frombuffer(raw, dtype=dtype).copy()
        return arr.reshape(shape) if len(shape) > 1 else arr

    def set_value(self, var_name: str, values: np.ndarray) -> None:
        """Écrit un numpy array dans une variable BMI."""
        ctype, dtype = self._resolve_type(var_name)
        flat = np.asarray(values, dtype=dtype).flatten()
        n = len(flat)
        buf = (ctype * n)(*flat.tolist())
        ret = self._lib.set_value(var_name.encode(), buf)
        if ret != BMI_SUCCESS:
            raise RuntimeError(f"set_value('{var_name}') a échoué (code {ret})")

    def get_value_at_indices(self, var_name: str, indices: list) -> np.ndarray:
        """Lit une variable aux indices spécifiés."""
        ctype, dtype = self._resolve_type(var_name)
        n = len(indices)
        buf     = (ctype * n)()
        idx_arr = (ctypes.c_int * n)(*indices)
        ret = self._lib.get_value_at_indices(var_name.encode(), buf, idx_arr, n)
        if ret != BMI_SUCCESS:
            raise RuntimeError(f"get_value_at_indices('{var_name}') a échoué (code {ret})")
        return np.frombuffer(bytes(buf), dtype=dtype).copy()

    def set_value_at_indices(self, var_name: str, indices: list, values) -> None:
        """Écrit des valeurs aux indices spécifiés."""
        ctype, dtype = self._resolve_type(var_name)
        n       = len(indices)
        flat    = np.asarray(values, dtype=dtype).flatten()
        buf     = (ctype * n)(*flat.tolist())
        idx_arr = (ctypes.c_int * n)(*indices)
        ret = self._lib.set_value_at_indices(var_name.encode(), buf, idx_arr, n)
        if ret != BMI_SUCCESS:
            raise RuntimeError(f"set_value_at_indices('{var_name}') a échoué (code {ret})")

    # ------------------------------------------------------------------
    # Informations sur le modèle
    # ------------------------------------------------------------------
    def get_component_name(self) -> str:
        buf = ctypes.create_string_buffer(MAX_COMPONENT_NAME)
        self._lib.get_component_name(buf)
        return buf.value.decode("utf-8").strip()

    def get_input_var_names(self) -> list:
        return self._get_var_names("input")

    def get_output_var_names(self) -> list:
        return self._get_var_names("output")

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------
    def _resolve_type(self, var_name: str):
        """Retourne (ctypes_type, numpy_dtype) pour la variable."""
        type_str = self.get_var_type(var_name).lower()
        for key, val in self._TYPE_MAP.items():
            if key in type_str:
                return val
        # Fallback : double
        return ctypes.c_double, np.float64

    def _get_var_names(self, direction: str) -> list:
        if direction == "input":
            count_fn = self._lib.get_input_var_name_count
            names_fn = self._lib.get_input_var_names
        else:
            count_fn = self._lib.get_output_var_name_count
            names_fn = self._lib.get_output_var_names

        count = ctypes.c_int(0)
        count_fn(ctypes.byref(count))
        n = count.value

        bufs = [ctypes.create_string_buffer(MAX_VAR_NAME) for _ in range(n)]
        arr  = (ctypes.c_char_p * n)(*[ctypes.cast(b, ctypes.c_char_p) for b in bufs])
        names_fn(arr)
        return [b.value.decode("utf-8").strip() for b in bufs]

    # ------------------------------------------------------------------
    # Utilitaire : affiche un résumé du modèle
    # ------------------------------------------------------------------
    def print_info(self):
        print("=" * 60)
        print(f"  Composant  : {self.get_component_name()}")
        print(f"  Temps déb. : {self.get_start_time()}")
        print(f"  Temps fin  : {self.get_end_time()}")
        print(f"  Pas de tps : {self.get_time_step()} {self.get_time_units()}")
        print(f"  Variables in  : {self.get_input_var_names()}")
        print(f"  Variables out : {self.get_output_var_names()}")
        print("=" * 60)
