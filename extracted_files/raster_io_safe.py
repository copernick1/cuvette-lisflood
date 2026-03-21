# =============================================================================
# raster_io_safe.py
# Lecture/écriture raster GDAL SANS gdal_array ni numpy.core.multiarray
# Compatible avec le conflit NumPy 1.x/2.x dans QGIS embarqué
# Stratégie : band.ReadRaster() ligne par ligne + np.frombuffer()
# =============================================================================
import os
import struct
import numpy as np

try:
    from osgeo import gdal, osr
    gdal.UseExceptions()
except ImportError:
    # Dans QGIS, gdal est parfois importé directement
    import gdal
    import osr

# Mapping type GDAL → struct format + numpy dtype
_GDAL_TO_STRUCT = {
    gdal.GDT_Byte:    ("B", np.uint8),
    gdal.GDT_UInt16:  ("H", np.uint16),
    gdal.GDT_Int16:   ("h", np.int16),
    gdal.GDT_UInt32:  ("I", np.uint32),
    gdal.GDT_Int32:   ("i", np.int32),
    gdal.GDT_Float32: ("f", np.float32),
    gdal.GDT_Float64: ("d", np.float64),
}


# =============================================================================
# LECTURE
# =============================================================================

def read_raster_safe(raster_path: str, band_index: int = 1,
                     nodata_to_nan: bool = True):
    """
    Lit un raster GDAL entièrement en mémoire SANS gdal_array.
    Utilise ReadRaster() ligne par ligne + np.frombuffer().

    Retourne
    --------
    arr : np.ndarray  shape (nrows, ncols)
    geo : tuple       GeoTransform GDAL (6 valeurs)
    proj : str        Projection WKT
    nodata : float | None
    """
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(f"Impossible d'ouvrir : {raster_path}")

    band   = ds.GetRasterBand(band_index)
    nrows  = ds.RasterYSize
    ncols  = ds.RasterXSize
    gdt    = band.DataType
    geo    = ds.GetGeoTransform()
    proj   = ds.GetProjection()
    nodata = band.GetNoDataValue()

    if gdt not in _GDAL_TO_STRUCT:
        raise ValueError(f"Type GDAL non supporté : {gdt}")

    _, dtype = _GDAL_TO_STRUCT[gdt]
    arr = np.empty((nrows, ncols), dtype=dtype)

    # Lecture ligne par ligne — contourne gdal_array
    for row in range(nrows):
        raw = band.ReadRaster(0, row, ncols, 1,
                              ncols, 1, gdt)
        arr[row, :] = np.frombuffer(raw, dtype=dtype)

    band = None
    ds   = None

    if nodata_to_nan and nodata is not None and np.issubdtype(dtype, np.floating):
        arr[arr == nodata] = np.nan

    return arr, geo, proj, nodata


def read_raster_window_safe(raster_path: str, col_off: int, row_off: int,
                             win_cols: int, win_rows: int,
                             band_index: int = 1):
    """
    Lit une fenêtre (window) d'un raster sans gdal_array.

    Paramètres
    ----------
    col_off, row_off : coin supérieur gauche de la fenêtre (pixels)
    win_cols, win_rows : taille de la fenêtre
    """
    ds   = gdal.Open(raster_path, gdal.GA_ReadOnly)
    band = ds.GetRasterBand(band_index)
    gdt  = band.DataType
    _, dtype = _GDAL_TO_STRUCT.get(gdt, ("f", np.float32))

    arr = np.empty((win_rows, win_cols), dtype=dtype)
    for row in range(win_rows):
        raw = band.ReadRaster(col_off, row_off + row,
                              win_cols, 1,
                              win_cols, 1, gdt)
        arr[row, :] = np.frombuffer(raw, dtype=dtype)

    geo  = ds.GetGeoTransform()
    proj = ds.GetProjection()
    ds   = None
    return arr, geo, proj


def read_raster_info(raster_path: str):
    """Retourne les métadonnées sans lire les données."""
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(raster_path)
    info = {
        "ncols":   ds.RasterXSize,
        "nrows":   ds.RasterYSize,
        "nbands":  ds.RasterCount,
        "geo":     ds.GetGeoTransform(),
        "proj":    ds.GetProjection(),
        "nodata":  ds.GetRasterBand(1).GetNoDataValue(),
        "dtype":   gdal.GetDataTypeName(ds.GetRasterBand(1).DataType),
    }
    ds = None
    return info


# =============================================================================
# ÉCRITURE
# =============================================================================

def write_raster_safe(out_path: str, arr: np.ndarray, geo: tuple,
                      proj: str, nodata=None,
                      gdal_dtype=None, driver_name: str = "GTiff"):
    """
    Écrit un numpy array 2D en fichier raster SANS gdal_array.
    Utilise WriteRaster() ligne par ligne + struct.pack().

    Paramètres
    ----------
    arr        : np.ndarray 2D (nrows, ncols)
    geo        : GeoTransform (6-tuple)
    proj       : WKT de projection
    nodata     : valeur NoData (optionnel)
    gdal_dtype : type GDAL cible (auto-détecté si None)
    driver_name: 'GTiff' (défaut), 'AAIGrid', etc.
    """
    if arr.ndim != 2:
        raise ValueError(f"arr doit être 2D, reçu shape={arr.shape}")

    nrows, ncols = arr.shape

    # Détermination automatique du type GDAL
    if gdal_dtype is None:
        gdal_dtype = _numpy_to_gdal_type(arr.dtype)

    struct_fmt, dtype = _GDAL_TO_STRUCT[gdal_dtype]

    driver = gdal.GetDriverByName(driver_name)
    ds = driver.Create(out_path, ncols, nrows, 1, gdal_dtype)
    ds.SetGeoTransform(geo)
    ds.SetProjection(proj)

    band = ds.GetRasterBand(1)
    if nodata is not None:
        band.SetNoDataValue(float(nodata))

    arr_cast = arr.astype(dtype)

    # Écriture ligne par ligne — contourne gdal_array
    for row in range(nrows):
        row_data = arr_cast[row, :]
        raw = struct.pack(f"{ncols}{struct_fmt}", *row_data.tolist())
        band.WriteRaster(0, row, ncols, 1, raw,
                         ncols, 1, gdal_dtype)

    band.FlushCache()
    band = None
    ds   = None
    print(f"[raster_io_safe] Écrit : {out_path}  ({ncols}x{nrows})")


def write_raster_from_bmi(out_path: str, bmi_array: np.ndarray,
                          ref_raster_path: str, nodata: float = -9999.0):
    """
    Écrit un tableau issu d'une variable BMI en reprenant la géométrie
    d'un raster de référence.

    Usage typique :
        arr = model.get_value("water depth")
        write_raster_from_bmi("depth.tif", arr, "DEM.tif")
    """
    info = read_raster_info(ref_raster_path)
    write_raster_safe(out_path, bmi_array, info["geo"], info["proj"], nodata=nodata)


# =============================================================================
# UTILITAIRES
# =============================================================================

def _numpy_to_gdal_type(dtype):
    """Convertit un dtype numpy en type GDAL."""
    mapping = {
        np.uint8:   gdal.GDT_Byte,
        np.uint16:  gdal.GDT_UInt16,
        np.int16:   gdal.GDT_Int16,
        np.uint32:  gdal.GDT_UInt32,
        np.int32:   gdal.GDT_Int32,
        np.float32: gdal.GDT_Float32,
        np.float64: gdal.GDT_Float64,
    }
    for np_type, gdal_type in mapping.items():
        if np.dtype(dtype) == np.dtype(np_type):
            return gdal_type
    return gdal.GDT_Float32  # fallback


def coords_to_pixel(geo, x, y):
    """Convertit des coordonnées géographiques en indices pixel (col, row)."""
    ox, px, _, oy, _, py = geo
    col = int((x - ox) / px)
    row = int((y - oy) / py)
    return col, row


def pixel_to_coords(geo, col, row):
    """Convertit des indices pixel en coordonnées géographiques (centre du pixel)."""
    ox, px, _, oy, _, py = geo
    x = ox + (col + 0.5) * px
    y = oy + (row + 0.5) * py
    return x, y


def reproject_array(arr, src_geo, src_proj, dst_proj,
                    dst_res=None, nodata=-9999.0):
    """
    Reprojette un tableau numpy via GDAL en mémoire (driver MEM).
    Retourne (arr_reproj, dst_geo).
    """
    nrows, ncols = arr.shape
    gdt = _numpy_to_gdal_type(arr.dtype)

    # Source en mémoire
    src_ds = gdal.GetDriverByName("MEM").Create("", ncols, nrows, 1, gdt)
    src_ds.SetGeoTransform(src_geo)
    src_ds.SetProjection(src_proj)
    src_band = src_ds.GetRasterBand(1)
    src_band.SetNoDataValue(nodata)

    # Écriture dans la source en mémoire
    struct_fmt, dtype = _GDAL_TO_STRUCT[gdt]
    arr_cast = arr.astype(dtype)
    for row in range(nrows):
        raw = struct.pack(f"{ncols}{struct_fmt}", *arr_cast[row, :].tolist())
        src_band.WriteRaster(0, row, ncols, 1, raw, ncols, 1, gdt)

    # Reprojection via Warp
    dst_ds = gdal.AutoCreateWarpedVRT(src_ds, src_proj, dst_proj,
                                      gdal.GRA_Bilinear)
    dst_geo  = dst_ds.GetGeoTransform()
    dst_rows = dst_ds.RasterYSize
    dst_cols = dst_ds.RasterXSize
    dst_band = dst_ds.GetRasterBand(1)

    out = np.empty((dst_rows, dst_cols), dtype=dtype)
    for row in range(dst_rows):
        raw = dst_band.ReadRaster(0, row, dst_cols, 1, dst_cols, 1, gdt)
        out[row, :] = np.frombuffer(raw, dtype=dtype)

    src_ds = dst_ds = None
    return out, dst_geo
