import os
import sys
import numpy as np

# Mock LisfloodBMI with dummy behaviors for testing
class MockLisfloodBMI:
    def __init__(self, dll):
        print(f"[TEST] Loading Mock DLL: {dll}")
        self.t = 0.0
        self.end_t = 10.0
        self.shape = (10, 10)
        self.rain = np.zeros(self.shape)

    def initialize(self, par):
        print(f"[TEST] Init with {par}")

    def get_current_time(self): return self.t
    def get_end_time(self): return self.end_t
    def get_var_shape(self, name): return self.shape

    def set_value(self, name, val):
        print(f"[TEST] Setting {name} to {val}")
        if name == "rain": self.rain = val

    def update(self):
        self.t += 1.0
        print(f"[TEST] Update t={self.t}")

    def get_value(self, name):
        if name == "water depth": return np.random.rand(*self.shape)
        if name == "water surface elevation": return np.random.rand(*self.shape)
        return np.zeros(self.shape)

    def finalize(self):
        print("[TEST] Finalize")

# Patch the runner to use Mock
import extracted_files.lisflood_qgis_runner as lfr
lfr.LisfloodBMI = MockLisfloodBMI

# Mock read_raster_info
def mock_read_raster_info(path):
    return {"nrows": 10, "ncols": 10, "geo": (0,1,0,0,0,1), "proj": "WGS84"}
lfr.read_raster_info = mock_read_raster_info

# Mock write_raster_safe
def mock_write_raster_safe(fname, arr, geo, proj, nodata):
    print(f"[TEST] Writing raster: {fname}")
lfr.write_raster_safe = mock_write_raster_safe

# Run test
print("--- Lancement du test simulé ---")
lfr.quick_run("dummy.dll", "dummy.par", "dummy.tif", "dummy_out", rain=0.015)
print("--- Test terminé avec succès ---")
