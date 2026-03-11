import logging
from typing import Literal
logger = logging.getLogger(__name__)

_GRID_EF = {
    "india_national":   {"ef": 0.716},
    "india_western":    {"ef": 0.740},
    "india_northern":   {"ef": 0.700},
    "india_southern":   {"ef": 0.680},
    "india_eastern":    {"ef": 0.780},
    "gujarat":          {"ef": 0.748},
    "maharashtra":      {"ef": 0.735},
    "tamil_nadu":       {"ef": 0.658},
    "punjab":           {"ef": 0.692},
    "china_guangdong":  {"ef": 0.5271},
    "china_jiangsu":    {"ef": 0.7921},
    "china_shandong":   {"ef": 0.8666},
    "china_zhejiang":   {"ef": 0.6562},
    "china_hebei":      {"ef": 0.8423},
}
_REGION_ALIASES = {
    "india": "india_national", "india_grid": "india_national", "national": "india_national",
    "india_national_grid": "india_national", "in_national": "india_national",
    "western": "india_western", "western_region": "india_western",
    "northern": "india_northern", "northern_region": "india_northern",
    "southern": "india_southern", "southern_region": "india_southern",
    "eastern": "india_eastern", "eastern_region": "india_eastern",
    "gj": "gujarat", "mh": "maharashtra", "tn": "tamil_nadu",
    "tamilnadu": "tamil_nadu", "pb": "punjab",
    "guangdong": "china_guangdong", "gd": "china_guangdong",
    "jiangsu": "china_jiangsu", "js": "china_jiangsu",
    "shandong": "china_shandong", "sd": "china_shandong",
    "zhejiang": "china_zhejiang", "zj": "china_zhejiang",
    "hebei": "china_hebei", "hb": "china_hebei",
    "guvnl": "gujarat",  # Rajkot/Gujarat utility alias
}
_MATERIAL_EF = {
    "mild_steel":      {"primary": 1.85, "secondary": 0.43},
    "alloy_steel":     {"primary": 2.20, "secondary": 0.50},
    "stainless_steel": {"primary": 3.10, "secondary": 0.70},
    "grey_iron":       {"primary": 1.51, "secondary": 0.43},
    "ductile_iron":    {"primary": 1.72, "secondary": 0.50},
    "aluminium":       {"primary": 8.24, "secondary": 0.60},
    "aluminium_alloy": {"primary": 8.50, "secondary": 0.65},
    "brass":           {"primary": 3.20, "secondary": 0.85},
    "zinc_alloy":      {"primary": 3.86, "secondary": 0.65},
    "copper":          {"primary": 3.50, "secondary": 0.60},
}
_MATERIAL_ALIASES = {
    "steel": "mild_steel", "ms": "mild_steel", "carbon_steel": "mild_steel",
    "is2062": "mild_steel", "alloy steel": "alloy_steel", "hss": "alloy_steel",
    "en8": "alloy_steel", "en24": "alloy_steel", "42crmo4": "alloy_steel",
    "ss": "stainless_steel", "stainless": "stainless_steel",
    "ss304": "stainless_steel", "ss316": "stainless_steel",
    "cast_iron": "grey_iron", "cast iron": "grey_iron", "ci": "grey_iron",
    "gray_iron": "grey_iron", "gi": "grey_iron",
    "ductile iron": "ductile_iron", "sg_iron": "ductile_iron",
    "aluminum": "aluminium", "al": "aluminium",
    "aluminium alloy": "aluminium_alloy", "aluminum_alloy": "aluminium_alloy",
    "al_alloy": "aluminium_alloy", "6061": "aluminium_alloy", "7075": "aluminium_alloy",
    "bronze": "brass", "copper_alloy": "brass",
    "zinc": "zinc_alloy", "zn": "zinc_alloy", "zamak": "zinc_alloy",
    "cu": "copper",
    # compound keys from stamping/machining benchmarks
    "cold_stamping_mild_steel": "mild_steel",
    "alloy_steel_turning": "alloy_steel",
    "aluminium_die": "aluminium",
}
_GRID_DEFAULT = 0.716
_MATERIAL_DEFAULT = 1.85

def _norm_region(r): 
    r = r.lower().strip().replace(" ","_").replace("-","_")
    return _REGION_ALIASES.get(r, r)

def _norm_material(m):
    m_orig = m.lower().strip()
    m = m_orig.replace(" ","_").replace("-","_")
    return _MATERIAL_ALIASES.get(m_orig) or _MATERIAL_ALIASES.get(m, m)

def list_regions(): return sorted(_GRID_EF.keys())
def list_materials(): return sorted(_MATERIAL_EF.keys())

def get_grid_ef(region: str = "india_national") -> float:
    norm = _norm_region(region)
    if norm in _GRID_EF:
        return _GRID_EF[norm]["ef"]
    logger.warning(f"factor_db.get_grid_ef: '{region}' not found, using default {_GRID_DEFAULT}")
    return _GRID_DEFAULT

# Backward-compat aliases used by bayesian_engine.py
def get_grid_emission_factor(grid_zone: str = "india_national") -> float:
    return get_grid_ef(grid_zone)

def get_material_ef(material: str, source: str = "primary") -> float:
    norm = _norm_material(material)
    src = source if source in ("primary","secondary") else "primary"
    if norm in _MATERIAL_EF:
        return _MATERIAL_EF[norm].get(src, _MATERIAL_EF[norm].get("primary", _MATERIAL_DEFAULT))
    logger.warning(f"factor_db.get_material_ef: '{material}' not found, using default {_MATERIAL_DEFAULT}")
    return _MATERIAL_DEFAULT

def get_material_emission_factor(material: str, scrap_based: bool = True) -> float:
    return get_material_ef(material, source="secondary" if scrap_based else "primary")

def get_material_ef_both(material: str) -> dict:
    norm = _norm_material(material)
    if norm in _MATERIAL_EF:
        return _MATERIAL_EF[norm].copy()
    return {"primary": _MATERIAL_DEFAULT, "secondary": 0.43}