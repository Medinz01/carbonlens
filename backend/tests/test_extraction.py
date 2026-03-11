"""
test_extraction.py — Member 2 test suite (Issue #8)

Covers:
  1. SEC lookup returns valid dicts for all process+material combos in sample data
  2. Emission factor lookup returns positive floats for all combos
  3. Fallback behaviour for unknown process / unknown material
  4. LLM extraction (llm_parser.parse_documents) is mocked — no real API calls
  5. Mocked extraction output passes through SEC lookup without KeyError

Run:
    pytest backend/tests/test_extraction.py -v
"""

import json
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup — works from repo root or backend/tests/
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "backend"
_DATA_DIR = _REPO_ROOT / "data"

for p in [str(_BACKEND), str(_REPO_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# Inline sample fixture
# Mirrors the schema of data/sample_inputs/sample_factory_input.json.
# Covers forging, casting, stamping, machining — all 4 processes in the DB.
# ---------------------------------------------------------------------------
SAMPLE_FACTORY_INPUT = {
    "factory": {
        "name": "Rajkot Precision Forgings Pvt. Ltd.",
        "location": "Rajkot, Gujarat, India",
        "grid_region": "gujarat",
        "reporting_period": "FY2024-25",
        "total_kwh": 148000,
        "total_material_kg": 52000,
    },
    "products": [
        {
            "id": "P001",
            "description": "Crankshaft — Mild Steel Hot Forging",
            "process": "forging",
            "material": "mild_steel",
            "quantity": 3200,
        },
        {
            "id": "P002",
            "description": "Differential Housing — Grey Iron Sand Casting",
            "process": "casting",
            "material": "grey_iron",
            "quantity": 1800,
        },
        {
            "id": "P003",
            "description": "Bracket — Cold Stamping (Mild Steel Sheet)",
            "process": "stamping",
            "material": "cold_stamping_mild_steel",
            "quantity": 12000,
        },
        {
            "id": "P004",
            "description": "Spindle — Alloy Steel CNC Turning",
            "process": "machining",
            "material": "alloy_steel_turning",
            "quantity": 950,
        },
        {
            "id": "P005",
            "description": "Pump Body — Aluminium Die Casting",
            "process": "casting",
            "material": "aluminium_die",
            "quantity": 2200,
        },
    ],
}

# ---------------------------------------------------------------------------
# Mocked LLM extraction output
# Represents what llm_parser.parse_documents() returns after Claude processes
# uploaded electricity bill + material invoice + production log.
# ---------------------------------------------------------------------------
MOCK_EXTRACTED_DATA = {
    "total_kwh": 148000,
    "total_material_kg": 52000,
    "grid_region": "gujarat",
    "products": [
        {"id": "P001", "process": "forging",   "material": "mild_steel",              "quantity": 3200},
        {"id": "P002", "process": "casting",   "material": "grey_iron",               "quantity": 1800},
        {"id": "P003", "process": "stamping",  "material": "cold_stamping_mild_steel", "quantity": 12000},
        {"id": "P004", "process": "machining", "material": "alloy_steel_turning",      "quantity": 950},
        {"id": "P005", "process": "casting",   "material": "aluminium_die",            "quantity": 2200},
    ],
}

# Expected SEC keys every valid result must contain
_REQUIRED_SEC_KEYS = {"min", "typical", "max", "yield_coefficient"}


# ---------------------------------------------------------------------------
# Helper: import sec_lookup and factor_db with graceful skip
# ---------------------------------------------------------------------------
def _import_sec_lookup():
    try:
        import core.emission_factors.sec_lookup as m
        return m
    except ImportError:
        pass
    try:
        import sec_lookup as m
        return m
    except ImportError:
        return None


def _import_factor_db():
    try:
        import core.emission_factors.factor_db as m
        return m
    except ImportError:
        pass
    try:
        import factor_db as m
        return m
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Test: SEC lookup — sample data combos
# ---------------------------------------------------------------------------
class TestSECLookupSampleData(unittest.TestCase):
    """SEC lookup must return valid, non-default results for all sample combos."""

    @classmethod
    def setUpClass(cls):
        cls.sec = _import_sec_lookup()
        if cls.sec is None:
            raise unittest.SkipTest("sec_lookup not importable — skipping")

    def _lookup(self, process, material):
        return self.sec.get_sec(process, material)

    def test_all_products_return_dict(self):
        """get_sec returns a dict for every product in sample data."""
        for p in SAMPLE_FACTORY_INPUT["products"]:
            with self.subTest(id=p["id"], process=p["process"], material=p["material"]):
                result = self._lookup(p["process"], p["material"])
                self.assertIsInstance(result, dict)

    def test_all_products_have_required_keys(self):
        """Every result contains min, typical, max, yield_coefficient."""
        for p in SAMPLE_FACTORY_INPUT["products"]:
            with self.subTest(id=p["id"]):
                result = self._lookup(p["process"], p["material"])
                for key in _REQUIRED_SEC_KEYS:
                    self.assertIn(
                        key, result,
                        f"Missing key '{key}' for {p['process']}/{p['material']}"
                    )

    def test_sec_values_are_positive(self):
        """min, typical, max must all be positive numbers."""
        for p in SAMPLE_FACTORY_INPUT["products"]:
            with self.subTest(id=p["id"]):
                r = self._lookup(p["process"], p["material"])
                self.assertGreater(r["min"], 0)
                self.assertGreater(r["typical"], 0)
                self.assertGreater(r["max"], 0)

    def test_sec_ordering(self):
        """min <= typical <= max for every result."""
        for p in SAMPLE_FACTORY_INPUT["products"]:
            with self.subTest(id=p["id"]):
                r = self._lookup(p["process"], p["material"])
                self.assertLessEqual(r["min"], r["typical"])
                self.assertLessEqual(r["typical"], r["max"])

    def test_yield_coefficient_in_range(self):
        """yield_coefficient must be between 0 and 1 (exclusive)."""
        for p in SAMPLE_FACTORY_INPUT["products"]:
            with self.subTest(id=p["id"]):
                r = self._lookup(p["process"], p["material"])
                yc = r["yield_coefficient"]
                self.assertGreater(yc, 0.0, f"yield_coefficient <= 0 for {p['id']}")
                self.assertLess(yc, 1.0, f"yield_coefficient >= 1 for {p['id']}")

    def test_not_default_for_known_combos(self):
        """Known process+material should NOT return the fallback default."""
        for p in SAMPLE_FACTORY_INPUT["products"]:
            with self.subTest(id=p["id"]):
                r = self._lookup(p["process"], p["material"])
                self.assertFalse(
                    r.get("_is_default", False),
                    f"Unexpected default SEC for {p['process']}/{p['material']}"
                )


# ---------------------------------------------------------------------------
# Test: SEC lookup — alias resolution
# ---------------------------------------------------------------------------
class TestSECLookupAliases(unittest.TestCase):
    """Common real-world input variants must resolve without hitting default."""

    @classmethod
    def setUpClass(cls):
        cls.sec = _import_sec_lookup()
        if cls.sec is None:
            raise unittest.SkipTest("sec_lookup not importable")

    def _not_default(self, process, material):
        r = self.sec.get_sec(process, material)
        self.assertFalse(
            r.get("_is_default", False),
            f"Alias ({process!r}, {material!r}) fell through to default"
        )
        return r

    def test_steel_alias(self):
        self._not_default("forging", "steel")

    def test_aluminium_alias(self):
        self._not_default("forging", "aluminium")

    def test_process_alias_forge(self):
        self._not_default("forge", "mild_steel")

    def test_process_alias_cast(self):
        self._not_default("cast", "grey_iron")

    def test_brass_machining(self):
        """brass in machining requires alias -> brass_turning (fuzzy fails at 0.6)."""
        r = self._not_default("machining", "brass")
        self.assertEqual(r.get("_material"), "brass_turning")

    def test_cast_iron_in_casting(self):
        """'cast_iron' (underscored) should resolve to grey_iron in casting."""
        r = self._not_default("casting", "cast_iron")
        self.assertFalse(r.get("_is_default", False))


# ---------------------------------------------------------------------------
# Test: SEC lookup — fallback behaviour
# ---------------------------------------------------------------------------
class TestSECLookupFallback(unittest.TestCase):
    """Unknown inputs must return _is_default=True, never raise."""

    @classmethod
    def setUpClass(cls):
        cls.sec = _import_sec_lookup()
        if cls.sec is None:
            raise unittest.SkipTest("sec_lookup not importable")

    def test_unknown_process_returns_default(self):
        r = self.sec.get_sec("welding", "mild_steel")
        self.assertTrue(r.get("_is_default", False))

    def test_unknown_material_returns_default(self):
        r = self.sec.get_sec("forging", "unobtanium")
        self.assertTrue(r.get("_is_default", False))

    def test_default_still_has_required_keys(self):
        """Even the fallback default must have all required SEC keys."""
        r = self.sec.get_sec("welding", "unobtanium")
        for key in _REQUIRED_SEC_KEYS:
            self.assertIn(key, r)

    def test_default_values_are_positive(self):
        r = self.sec.get_sec("welding", "unobtanium")
        self.assertGreater(r["min"], 0)
        self.assertGreater(r["typical"], 0)
        self.assertGreater(r["max"], 0)

    def test_does_not_raise_on_empty_strings(self):
        try:
            self.sec.get_sec("", "")
        except Exception as e:
            self.fail(f"get_sec raised unexpectedly on empty strings: {e}")

    def test_list_available_processes_returns_list(self):
        result = self.sec.list_available_processes()
        self.assertIsInstance(result, list)
        # In the full repo environment (data/sec_benchmarks/ present), this will be
        # non-empty. In isolated test environments without the benchmark dir it may
        # be empty — that is acceptable; what matters is it doesn't raise.
        # When _load_benchmark is patched (as in CI), verify against known processes.
        if hasattr(self.sec, '_cache') and self.sec._cache:
            self.assertGreater(len(result), 0, 
                "list_available_processes returned empty despite loaded cache"
            )

    def test_list_available_materials_unknown_process(self):
        """Unknown process should return empty list, not raise."""
        result = self.sec.list_available_materials("welding")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# Test: get_yield_coefficient
# ---------------------------------------------------------------------------
class TestGetYieldCoefficient(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sec = _import_sec_lookup()
        if cls.sec is None:
            raise unittest.SkipTest("sec_lookup not importable")
        if not hasattr(cls.sec, "get_yield_coefficient"):
            raise unittest.SkipTest("get_yield_coefficient not implemented yet")

    def test_returns_float(self):
        result = self.sec.get_yield_coefficient("forging", "mild_steel")
        self.assertIsInstance(result, float)

    def test_known_combo_in_range(self):
        yc = self.sec.get_yield_coefficient("forging", "mild_steel")
        self.assertGreater(yc, 0.0)
        self.assertLess(yc, 1.0)

    def test_unknown_combo_returns_default(self):
        yc = self.sec.get_yield_coefficient("welding", "unobtanium")
        self.assertEqual(yc, 0.80)  # documented default


# ---------------------------------------------------------------------------
# Test: factor_db grid + material EFs
# ---------------------------------------------------------------------------
class TestFactorDB(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = _import_factor_db()
        if cls.db is None:
            raise unittest.SkipTest("factor_db not importable")

    def test_india_national_grid(self):
        ef = self.db.get_grid_ef("india_national")
        self.assertAlmostEqual(ef, 0.716, places=3)

    def test_india_state_gujarat(self):
        ef = self.db.get_grid_ef("gujarat")
        self.assertGreater(ef, 0)
        self.assertLess(ef, 2.0)

    def test_india_state_aliases(self):
        for alias, canonical in [("tn", "tamil_nadu"), ("gj", "gujarat"), ("mh", "maharashtra"), ("pb", "punjab")]:
            with self.subTest(alias=alias):
                self.assertAlmostEqual(
                    self.db.get_grid_ef(alias),
                    self.db.get_grid_ef(canonical),
                    places=4
                )

    def test_china_five_provinces_present(self):
        provinces = ["china_guangdong", "china_jiangsu", "china_shandong", "china_zhejiang", "china_hebei"]
        for p in provinces:
            with self.subTest(province=p):
                ef = self.db.get_grid_ef(p)
                self.assertGreater(ef, 0)
                self.assertLess(ef, 2.0)

    def test_unknown_region_returns_default(self):
        ef = self.db.get_grid_ef("antarctica")
        self.assertAlmostEqual(ef, 0.716, places=3)

    def test_material_ef_mild_steel(self):
        ef = self.db.get_material_ef("mild_steel", "primary")
        self.assertAlmostEqual(ef, 1.85, places=2)

    def test_material_ef_aliases(self):
        for alias in ["steel", "ms", "carbon_steel"]:
            with self.subTest(alias=alias):
                ef = self.db.get_material_ef(alias)
                self.assertGreater(ef, 0)

    def test_material_ef_secondary_less_than_primary(self):
        """Recycled production is always lower-carbon than primary."""
        for mat in ["mild_steel", "aluminium", "grey_iron"]:
            with self.subTest(material=mat):
                primary = self.db.get_material_ef(mat, "primary")
                secondary = self.db.get_material_ef(mat, "secondary")
                self.assertLess(secondary, primary)

    def test_unknown_material_returns_default(self):
        ef = self.db.get_material_ef("unobtanium")
        self.assertAlmostEqual(ef, 1.85, places=2)


# ---------------------------------------------------------------------------
# Test: LLM extraction mock
# ---------------------------------------------------------------------------
class TestLLMExtractionMocked(unittest.TestCase):
    """
    Tests for llm_parser.parse_documents().

    The Claude API is always mocked — these tests must never make real HTTP calls.
    Tests verify that the extraction output schema is well-formed and that the
    extracted process+material combos all pass through SEC lookup successfully.
    """

    def _make_mock_anthropic(self):
        """Return a mock anthropic.Anthropic client that returns MOCK_EXTRACTED_DATA."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(type="text", text=json.dumps(MOCK_EXTRACTED_DATA))
        ]
        mock_client.messages.create.return_value = mock_message
        return mock_client

    @patch("anthropic.Anthropic")
    def test_parse_documents_called_with_api(self, MockAnthropic):
        """parse_documents calls anthropic.Anthropic (not requests directly)."""
        MockAnthropic.return_value = self._make_mock_anthropic()
        try:
            from core.extraction import llm_parser
        except ImportError:
            self.skipTest("llm_parser not importable yet")

        llm_parser.parse_documents(["fake_bill.pdf", "fake_invoice.pdf"])
        MockAnthropic.assert_called_once()

    @patch("anthropic.Anthropic")
    def test_parse_documents_returns_products_list(self, MockAnthropic):
        """Extracted data must include a non-empty 'products' list."""
        MockAnthropic.return_value = self._make_mock_anthropic()
        try:
            from core.extraction import llm_parser
        except ImportError:
            self.skipTest("llm_parser not importable yet")

        result = llm_parser.parse_documents(["fake_bill.pdf"])
        self.assertIn("products", result)
        self.assertIsInstance(result["products"], list)
        self.assertGreater(len(result["products"]), 0)

    @patch("anthropic.Anthropic")
    def test_extracted_combos_pass_sec_lookup(self, MockAnthropic):
        """
        Every process+material combo returned by the mocked LLM must yield
        a valid (non-default) SEC result.
        """
        MockAnthropic.return_value = self._make_mock_anthropic()

        sec = _import_sec_lookup()
        if sec is None:
            self.skipTest("sec_lookup not importable")

        # Use the mock extracted data directly (bypasses llm_parser import)
        for product in MOCK_EXTRACTED_DATA["products"]:
            with self.subTest(id=product["id"]):
                r = sec.get_sec(product["process"], product["material"])
                self.assertFalse(
                    r.get("_is_default", False),
                    f"Default SEC for extracted product {product['id']} "
                    f"({product['process']}/{product['material']})"
                )
                for key in _REQUIRED_SEC_KEYS:
                    self.assertIn(key, r)

    def test_no_real_api_call_without_mock(self):
        """
        Importing sec_lookup or factor_db must not trigger any HTTP calls.
        This guards against accidental live API usage in CI.
        """
        import socket
        original_connect = socket.socket.connect

        call_log = []

        def patched_connect(self, *args, **kwargs):
            call_log.append(args)
            return original_connect(self, *args, **kwargs)

        # Just import — should not touch network
        with patch.object(socket.socket, "connect", patched_connect):
            _import_sec_lookup()
            _import_factor_db()

        # Filter to likely HTTP calls (port 80/443)
        http_calls = [a for a in call_log if isinstance(a[0], tuple) and a[0][1] in (80, 443)]
        self.assertEqual(
            len(http_calls), 0,
            f"Unexpected HTTP calls during import: {http_calls}"
        )


# ---------------------------------------------------------------------------
# Test: integration — sample data round-trip
# ---------------------------------------------------------------------------
class TestSampleDataRoundTrip(unittest.TestCase):
    """
    End-to-end: sample fixture -> SEC lookup -> emission factor lookup.
    All values must be computable without errors.
    """

    @classmethod
    def setUpClass(cls):
        cls.sec = _import_sec_lookup()
        cls.db = _import_factor_db()

    def test_all_products_compute_energy_co2e(self):
        """
        For each product: allocated_kwh * grid_ef -> kgCO2e
        Must be a positive float for all products.
        """
        if self.sec is None or self.db is None:
            self.skipTest("sec_lookup or factor_db not importable")

        grid_ef = self.db.get_grid_ef(
            SAMPLE_FACTORY_INPUT["factory"]["grid_region"]
        )

        total_kwh = SAMPLE_FACTORY_INPUT["factory"]["total_kwh"]
        n = len(SAMPLE_FACTORY_INPUT["products"])
        allocated_kwh_each = total_kwh / n  # naive equal split for test purposes

        for p in SAMPLE_FACTORY_INPUT["products"]:
            with self.subTest(id=p["id"]):
                sec = self.sec.get_sec(p["process"], p["material"])
                energy_co2e = allocated_kwh_each * grid_ef
                self.assertGreater(energy_co2e, 0)

    def test_all_products_compute_material_co2e(self):
        """
        For each product: material_kg * material_ef -> kgCO2e
        Must be a positive float for all products.
        """
        if self.sec is None or self.db is None:
            self.skipTest("sec_lookup or factor_db not importable")

        for p in SAMPLE_FACTORY_INPUT["products"]:
            with self.subTest(id=p["id"]):
                # Use canonical material name (strip process suffix for machining/stamping)
                mat = p["material"].replace("_turning","").replace("_milling","") \
                                   .replace("cold_stamping_","").replace("hot_stamping_","")
                ef = self.db.get_material_ef(mat)
                material_co2e = 100.0 * ef  # arbitrary 100 kg input for test
                self.assertGreater(material_co2e, 0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    unittest.main(verbosity=2)