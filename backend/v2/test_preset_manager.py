import unittest
import os
import shutil
from v2.preset_manager import PresetManager, StrategyPreset

class TestPresetManager(unittest.TestCase):
    def setUp(self):
        self.test_storage_path = "backend/v2/test_presets.json"
        # Ensure clean state
        if os.path.exists(self.test_storage_path):
            os.remove(self.test_storage_path)
        self.manager = PresetManager(storage_path=self.test_storage_path)

    def tearDown(self):
        if os.path.exists(self.test_storage_path):
            os.remove(self.test_storage_path)

    def test_preload_defaults(self):
        presets = self.manager.get_all_presets()
        self.assertEqual(len(presets), 3)
        names = [p.name for p in presets]
        self.assertIn("Five EMA Aggressive", names)
        self.assertIn("Five EMA Conservative", names)
        self.assertIn("EMA Trend", names)

    def test_create_and_get_preset(self):
        new_preset = StrategyPreset(
            id="preset_custom",
            name="My Custom Preset",
            strategy_id="five_ema",
            parameters={"five_ema_period": 6},
            risk_management={"max_holding_candles": 12},
            strike_selection={"mode": "ATM"},
            expiry_selection={"mode": "CURRENT_WEEKLY"},
            timeframe="3m"
        )
        self.manager.create_preset(new_preset)
        
        loaded = self.manager.get_preset("preset_custom")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "My Custom Preset")
        self.assertEqual(loaded.timeframe, "3m")
        self.assertEqual(loaded.parameters["five_ema_period"], 6)

    def test_update_preset(self):
        updated = self.manager.update_preset("preset_five_ema_aggressive", {
            "name": "Five EMA Aggressive V2",
            "timeframe": "3m",
            "tags": ["aggressive", "v2"]
        })
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "Five EMA Aggressive V2")
        self.assertEqual(updated.timeframe, "3m")
        self.assertIn("v2", updated.tags)
        
        # Verify persistence
        loaded = self.manager.get_preset("preset_five_ema_aggressive")
        self.assertEqual(loaded.name, "Five EMA Aggressive V2")

    def test_duplicate_preset(self):
        dup = self.manager.duplicate_preset("preset_ema_trend", "EMA Trend Copy")
        self.assertIsNotNone(dup)
        self.assertEqual(dup.name, "EMA Trend Copy")
        self.assertEqual(dup.strategy_id, "ema")
        self.assertTrue(dup.id.startswith("preset_"))
        
        # Verify both exist
        self.assertIsNotNone(self.manager.get_preset("preset_ema_trend"))
        self.assertIsNotNone(self.manager.get_preset(dup.id))

    def test_delete_preset(self):
        success = self.manager.delete_preset("preset_five_ema_conservative")
        self.assertTrue(success)
        self.assertIsNone(self.manager.get_preset("preset_five_ema_conservative"))
        
        # Deleting again should return False
        success_again = self.manager.delete_preset("preset_five_ema_conservative")
        self.assertFalse(success_again)
        
        # Verify count
        presets = self.manager.get_all_presets()
        self.assertEqual(len(presets), 2)
