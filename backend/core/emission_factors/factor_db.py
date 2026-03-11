"""
factor_db.py — Emission Factor Database Interface

Provides:
  - get_grid_ef(region) -> float (kgCO2e/kWh)
  - get_material_ef(material, source="primary") -> float (kgCO2e/kg)
  - list_regions() -> list[str]
  - list_materials() -> list[str]

Grid emission factors:
  - India national grid + 5 regional grids (CEA CO2 Baseline Database v18, 2023-24)
  - India state-level: Gujarat, Maharashtra, Tamil Nadu, Punjab
  - China provincial averages: 5 major manufacturing provinces
    (China Electricity Council / MEE Provincial EF data, 2022)

Material emission factors:
  - Sourced from IPCC AR5, World Steel Association, IAI, IZA
  - Consistent with values embedded in SEC benchmark JSONs

Never raises — returns a logged default on unknown input.
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# ── Grid Emission Factors ─────────────────────────────────────────────────────
# Units: kgCO2e per kWh
#
# India sources:
#   CEA CO2 Baseline Database for the Indian Power Sector, Version 18 (2023-24)
#   https://cea.nic.in/wp-content/uploads/baseline/2023/co2_base_2023.pdf
#   State-level factors derived from CEA state-wise generation mix + emission
#   intensity tables (Table 3, Version 18). Values represent combined margin (OM+BM)/2.
#
# China sources:
#   China Electricity Council (CEC) — Provincial Average CO2 Emission Factor 2022
#   Ministry of Ecology and Environment (MEE) — GHG Accounting Guidelines for
#   Power Generation Enterprises (2022 revision).
#   Provincial figures represent average grid emission intensity (kgCO2/kWh)
#   weighted by actual generation mix reported to MEE.

_GRID_EF: dict[str, dict] = {

    # ── India: National + Regional (CEA Version 18, 2023-24) ─────────────────
    "india_national": {
        "ef": 0.716,
        "source": "CEA CO2 Baseline Database v18 (2023-24) — national weighted average",
        "region_type": "india_national",
    },
    "india_western": {
        "ef": 0.740,
        "source": "CEA v18 — Western Regional Grid (Gujarat, Maharashtra, MP, Chhattisgarh, Goa)",
        "region_type": "india_regional",
    },
    "india_northern": {
        "ef": 0.700,
        "source": "CEA v18 — Northern Regional Grid (UP, Punjab, Haryana, Rajasthan, HP, J&K)",
        "region_type": "india_regional",
    },
    "india_southern": {
        "ef": 0.680,
        "source": "CEA v18 — Southern Regional Grid (Tamil Nadu, Karnataka, Andhra Pradesh, Kerala, Telangana)",
        "region_type": "india_regional",
    },
    "india_eastern": {
        "ef": 0.780,
        "source": "CEA v18 — Eastern Regional Grid (West Bengal, Odisha, Bihar, Jharkhand)",
        "region_type": "india_regional",
    },

    # ── India: State-Level (CEA v18, Table 3 — state generation mix) ─────────
    # Gujarat: coal-heavy baseload + significant renewable additions (wind, solar).
    # EF slightly above national due to coal dominance in industrial load.
    "gujarat": {
        "ef": 0.748,
        "source": "CEA v18 — Gujarat state EF (coal-heavy grid; Rajkot/Surat industrial cluster reference)",
        "region_type": "india_state",
        "notes": "Reference state for Rajkot forging/casting MSME clusters (CBAM-relevant)",
    },
    # Maharashtra: mixed coal + gas + hydro + growing solar.
    "maharashtra": {
        "ef": 0.735,
        "source": "CEA v18 — Maharashtra state EF (Pune/Mumbai industrial corridor)",
        "region_type": "india_state",
        "notes": "Reference state for Pune forging cluster and auto component MSMEs",
    },
    # Tamil Nadu: significant wind + solar + nuclear (Kudankulam) → lower EF.
    "tamil_nadu": {
        "ef": 0.658,
        "source": "CEA v18 — Tamil Nadu state EF (high renewable penetration: wind + solar + nuclear)",
        "region_type": "india_state",
        "notes": "Reference state for Coimbatore foundry cluster",
    },
    # Punjab: coal + hydro (Bhakra). Lower industrial density than Gujarat/MH.
    "punjab": {
        "ef": 0.692,
        "source": "CEA v18 — Punjab state EF (Bhakra hydro + coal thermal mix)",
        "region_type": "india_state",
        "notes": "Reference state for Ludhiana forging/machining cluster",
    },

    # ── China: Provincial Averages (CEC / MEE 2022) ──────────────────────────
    # Guangdong: Pearl River Delta — mixed coal + gas + nuclear + imports from Yunnan hydro.
    # Major EV/electronics manufacturing hub.
    "china_guangdong": {
        "ef": 0.5271,
        "source": "China Electricity Council (CEC) / MEE Provincial EF 2022 — Guangdong",
        "region_type": "china_provincial",
        "notes": "Pearl River Delta manufacturing hub (Guangzhou, Shenzhen, Dongguan)",
    },
    # Jiangsu: Yangtze River Delta — heavily coal-dependent industrial province.
    # Major steel, machinery, and auto components production.
    "china_jiangsu": {
        "ef": 0.7921,
        "source": "CEC / MEE 2022 — Jiangsu (coal-heavy; major industrial province)",
        "region_type": "china_provincial",
        "notes": "Yangtze River Delta — Nanjing, Suzhou, Wuxi manufacturing clusters",
    },
    # Shandong: China's largest coal consumer — highest EF among major provinces.
    # Major steel, forging, and heavy industry concentration.
    "china_shandong": {
        "ef": 0.8666,
        "source": "CEC / MEE 2022 — Shandong (highest coal dependency; heavy industry)",
        "region_type": "china_provincial",
        "notes": "China's largest coal-consuming province; major forging/steel clusters",
    },
    # Zhejiang: Yangtze Delta — less coal than Jiangsu; growing gas + imports.
    # Major light manufacturing, casting, and fastener clusters (Wenzhou, Ningbo).
    "china_zhejiang": {
        "ef": 0.6562,
        "source": "CEC / MEE 2022 — Zhejiang",
        "region_type": "china_provincial",
        "notes": "Ningbo/Wenzhou casting, fastener, and auto parts clusters",
    },
    # Hebei: surrounds Beijing; coal-dominated; major steel producer (Tangshan).
    # Highest steel output province — directly relevant for CBAM embedded carbon.
    "china_hebei": {
        "ef": 0.8423,
        "source": "CEC / MEE 2022 — Hebei (coal-dominated; Tangshan steel cluster)",
        "region_type": "china_provincial",
        "notes": "Tangshan is China's largest steel-producing city; CBAM high-relevance",
    },
}

# ── Aliases for region lookup ─────────────────────────────────────────────────
_REGION_ALIASES: dict[str, str] = {
    # India national
    "india": "india_national",
    "india_grid": "india_national",
    "national": "india_national",
    "india_national_grid": "india_national",

    # India regional
    "western": "india_western",
    "western_region": "india_western",
    "northern": "india_northern",
    "northern_region": "india_northern",
    "southern": "india_southern",
    "southern_region": "india_southern",
    "eastern": "india_eastern",
    "eastern_region": "india_eastern",

    # India states
    "gj": "gujarat",
    "mh": "maharashtra",
    "tn": "tamil_nadu",
    "tamilnadu": "tamil_nadu",
    "pb": "punjab",

    # China
    "guangdong": "china_guangdong",
    "gd": "china_guangdong",
    "jiangsu": "china_jiangsu",
    "js": "china_jiangsu",
    "shandong": "china_shandong",
    "sd": "china_shandong",
    "zhejiang": "china_zhejiang",
    "zj": "china_zhejiang",
    "hebei": "china_hebei",
    "hb": "china_hebei",
}

_GRID_DEFAULT = 0.716   # India national grid — CEA v18
_GRID_DEFAULT_KEY = "india_national"


# ── Material Emission Factors ─────────────────────────────────────────────────
# Units: kgCO2e per kg of material
# Sources: IPCC AR5 WG3 Annex II, World Steel Association (WSA) 2022,
#          International Aluminium Institute (IAI) 2021, IZA Zinc EF,
#          consistent with emission_factors blocks in SEC benchmark JSONs.
#
# "primary" = virgin/primary production
# "secondary" = recycled/scrap-based (electric arc furnace / secondary smelting)

_MATERIAL_EF: dict[str, dict[str, float]] = {
    "mild_steel":       {"primary": 1.85, "secondary": 0.43},
    "alloy_steel":      {"primary": 2.20, "secondary": 0.50},
    "stainless_steel":  {"primary": 3.10, "secondary": 0.70},
    "grey_iron":        {"primary": 1.51, "secondary": 0.43},
    "ductile_iron":     {"primary": 1.72, "secondary": 0.50},
    "aluminium":        {"primary": 8.24, "secondary": 0.60},
    "aluminium_alloy":  {"primary": 8.50, "secondary": 0.65},
    "brass":            {"primary": 3.20, "secondary": 0.85},
    "zinc_alloy":       {"primary": 3.86, "secondary": 0.65},
    "copper":           {"primary": 3.50, "secondary": 0.60},
}

# Aliases consistent with sec_lookup._MATERIAL_ALIASES
_MATERIAL_ALIASES: dict[str, str] = {
    "steel": "mild_steel",
    "ms": "mild_steel",
    "carbon_steel": "mild_steel",
    "low_carbon_steel": "mild_steel",
    "is2062": "mild_steel",
    "alloy steel": "alloy_steel",
    "hss": "alloy_steel",
    "en8": "alloy_steel",
    "en24": "alloy_steel",
    "42crmo4": "alloy_steel",
    "ss": "stainless_steel",
    "stainless": "stainless_steel",
    "ss304": "stainless_steel",
    "ss316": "stainless_steel",
    "cast_iron": "grey_iron",
    "cast iron": "grey_iron",
    "ci": "grey_iron",
    "gray_iron": "grey_iron",
    "gi": "grey_iron",
    "ductile iron": "ductile_iron",
    "sg_iron": "ductile_iron",
    "nodular_iron": "ductile_iron",
    "aluminum": "aluminium",
    "al": "aluminium",
    "aluminium alloy": "aluminium_alloy",
    "aluminum_alloy": "aluminium_alloy",
    "al_alloy": "aluminium_alloy",
    "6061": "aluminium_alloy",
    "7075": "aluminium_alloy",
    "lm6": "aluminium_alloy",
    "lm25": "aluminium_alloy",
    "bronze": "brass",
    "copper_alloy": "brass",
    "zinc": "zinc_alloy",
    "zn": "zinc_alloy",
    "zamak": "zinc_alloy",
    "cu": "copper",
}

_MATERIAL_DEFAULT = 1.85  # mild steel primary — conservative fallback


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise_region(region: str) -> str:
    r = region.lower().strip().replace(" ", "_").replace("-", "_")
    return _REGION_ALIASES.get(r, r)


def _normalise_material(material: str) -> str:
    m_orig = material.lower().strip()
    m = m_orig.replace(" ", "_").replace("-", "_")
    if m_orig in _MATERIAL_ALIASES:
        return _MATERIAL_ALIASES[m_orig]
    if m in _MATERIAL_ALIASES:
        return _MATERIAL_ALIASES[m]
    return m


# ── Public API ────────────────────────────────────────────────────────────────

def list_regions() -> list[str]:
    """Return all canonical region keys (India + China)."""
    return sorted(_GRID_EF.keys())


def list_materials() -> list[str]:
    """Return all canonical material keys with emission factors."""
    return sorted(_MATERIAL_EF.keys())


def get_grid_ef(region: str = "india_national") -> float:
    """
    Get grid emission factor (kgCO2e/kWh) for a region.

    Supports:
      India national/regional: "india_national", "india_western", "india_northern",
                                "india_southern", "india_eastern"
      India state-level:       "gujarat", "maharashtra", "tamil_nadu", "punjab"
      China provincial:        "china_guangdong", "china_jiangsu", "china_shandong",
                                "china_zhejiang", "china_hebei"

    Also accepts common aliases (e.g. "india", "tn", "guangdong").
    Falls back to India national grid (0.716) with a warning if region not found.

    Source: CEA CO2 Baseline Database v18 (2023-24) for India;
            CEC / MEE Provincial EF 2022 for China.

    Args:
        region: region key or alias

    Returns:
        float: kgCO2e per kWh
    """
    norm = _normalise_region(region)
    if norm in _GRID_EF:
        return _GRID_EF[norm]["ef"]

    logger.warning(
        f"factor_db.get_grid_ef: region '{region}' (normalised: '{norm}') not found. "
        f"Available: {list_regions()}. Returning India national default {_GRID_DEFAULT}."
    )
    return _GRID_DEFAULT


def get_grid_ef_record(region: str = "india_national") -> dict:
    """
    Like get_grid_ef() but returns the full record including source citation.

    Returns:
        dict with keys: ef, source, region_type, notes (optional)
    """
    norm = _normalise_region(region)
    if norm in _GRID_EF:
        return _GRID_EF[norm].copy()

    logger.warning(
        f"factor_db.get_grid_ef_record: region '{region}' not found. Returning default."
    )
    return {
        "ef": _GRID_DEFAULT,
        "source": f"DEFAULT — region '{region}' not found; using CEA v18 India national grid",
        "region_type": "default",
        "_is_default": True,
    }


def get_material_ef(
    material: str,
    source: Literal["primary", "secondary"] = "primary",
) -> float:
    """
    Get material emission factor (kgCO2e/kg).

    Args:
        material: e.g. "mild_steel", "grey_iron", "aluminium_alloy"
                  Common aliases accepted (e.g. "steel", "cast iron", "al").
        source:   "primary" (virgin) or "secondary" (recycled/scrap). Default: "primary".

    Returns:
        float: kgCO2e per kg of material

    Source: IPCC AR5 WG3 / WSA 2022 / IAI 2021 / IZA.
    Falls back to 1.85 kgCO2e/kg (mild steel primary) with a warning if not found.
    """
    norm = _normalise_material(material)
    src = source if source in ("primary", "secondary") else "primary"

    if norm in _MATERIAL_EF:
        ef_entry = _MATERIAL_EF[norm]
        if src in ef_entry:
            return ef_entry[src]
        # Requested secondary but only primary available (or vice versa)
        fallback_src = "primary" if src == "secondary" else "secondary"
        if fallback_src in ef_entry:
            logger.warning(
                f"factor_db.get_material_ef: '{src}' EF not available for '{material}'; "
                f"using '{fallback_src}' = {ef_entry[fallback_src]}"
            )
            return ef_entry[fallback_src]

    logger.warning(
        f"factor_db.get_material_ef: material '{material}' (normalised: '{norm}') not found. "
        f"Available: {list_materials()}. Returning default {_MATERIAL_DEFAULT} kgCO2e/kg."
    )
    return _MATERIAL_DEFAULT


def get_material_ef_both(material: str) -> dict[str, float]:
    """
    Return both primary and secondary emission factors for a material.

    Useful for Bayesian engine to model material source uncertainty.

    Returns:
        dict with keys "primary" and "secondary" (kgCO2e/kg)
    """
    norm = _normalise_material(material)
    if norm in _MATERIAL_EF:
        return _MATERIAL_EF[norm].copy()
    logger.warning(
        f"factor_db.get_material_ef_both: material '{material}' not found. Returning default."
    )
    return {"primary": _MATERIAL_DEFAULT, "secondary": 0.43}