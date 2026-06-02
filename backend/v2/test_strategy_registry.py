import unittest
from v2.strategy_registry import get_strategy_metadata, get_all_strategy_metadata, StrategyMetadata

class TestStrategyRegistry(unittest.TestCase):
    def test_get_all_strategy_metadata(self):
        all_metadata = get_all_strategy_metadata()
        self.assertEqual(len(all_metadata), 3)
        ids = [m.id for m in all_metadata]
        self.assertIn("five_ema", ids)
        self.assertIn("ema", ids)
        self.assertIn("heikin_ashi", ids)

    def test_get_strategy_metadata_direct(self):
        meta = get_strategy_metadata("five_ema")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.name, "Five EMA Option Scalping")
        self.assertEqual(meta.risk_level, "High")

    def test_get_strategy_metadata_alias(self):
        meta = get_strategy_metadata("five_ema_scalping")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.id, "five_ema")

        meta_ha = get_strategy_metadata("heikin_ashi_gar")
        self.assertIsNotNone(meta_ha)
        self.assertEqual(meta_ha.id, "heikin_ashi")

    def test_get_strategy_metadata_invalid(self):
        meta = get_strategy_metadata("non_existent_strategy")
        self.assertIsNone(meta)

    def test_schema_types(self):
        meta = get_strategy_metadata("ema")
        self.assertIsInstance(meta, StrategyMetadata)
        self.assertGreater(len(meta.supported_parameters), 0)
        self.assertEqual(meta.supported_parameters[0].name, "fast_period")
        self.assertEqual(meta.supported_parameters[0].type, "int")
