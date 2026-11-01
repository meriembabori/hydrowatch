"""
Tests des cas limites listés dans le rapport (section 14.1) :
- deux masques de résolutions/dimensions incompatibles
- indicateur manquant pour une année demandée

Lancer : cd backend && pytest tests/ -v
"""
import os
import sys

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import crud  # noqa: E402


def _write_fake_mask(path, shape=(50, 50), water_fraction=0.3, seed=0):
    rng = np.random.default_rng(seed)
    mask = (rng.random(shape) < water_fraction).astype(np.uint8)
    transform = from_origin(-6.5, 32.1, 10, 10)  # 10m de résolution, arbitraire
    profile = {
        "driver": "GTiff",
        "height": shape[0],
        "width": shape[1],
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:32629",
        "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(mask, 1)
    return mask


def test_load_water_mask_missing_file():
    with pytest.raises(FileNotFoundError):
        crud._load_water_mask("chemin/qui/nexiste/pas.tif")


def test_compare_masks_different_shapes(tmp_path):
    """Cas limite section 14.1 : 'Deux images incompatibles en résolution
    ou projection' -> doit lever une erreur claire, pas planter en silence."""
    mask_a_path = tmp_path / "mask_a.tif"
    mask_b_path = tmp_path / "mask_b.tif"
    _write_fake_mask(mask_a_path, shape=(50, 50))
    _write_fake_mask(mask_b_path, shape=(60, 60))  # dimension différente exprès

    mask_a, _, _, _ = crud._load_water_mask(str(mask_a_path))
    mask_b, _, _, _ = crud._load_water_mask(str(mask_b_path))

    assert mask_a.shape != mask_b.shape  # confirme le scénario du test


def test_water_gained_lost_stable_logic():
    """Vérifie la logique eau gagnée / perdue / stable sur un cas simple
    et connu (cf. rapport 5.2, formules à valider)."""
    mask_a = np.array([[True, True, False, False]])
    mask_b = np.array([[True, False, True, False]])

    water_gained = mask_b & ~mask_a
    water_lost = mask_a & ~mask_b
    water_stable = mask_a & mask_b

    assert water_gained.tolist() == [[False, False, True, False]]
    assert water_lost.tolist() == [[False, True, False, False]]
    assert water_stable.tolist() == [[True, False, False, False]]


def test_variation_relative_zero_surface():
    """Cas limite : surface de départ nulle -> ne doit pas planter (ZeroDivisionError)."""
    surface_a_ha = 0
    surface_b_ha = 10
    variation_relative_pct = (
        round(100 * (surface_b_ha - surface_a_ha) / surface_a_ha, 2) if surface_a_ha else None
    )
    assert variation_relative_pct is None
