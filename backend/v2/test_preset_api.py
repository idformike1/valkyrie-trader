import unittest
import sys
import os

# Adjust paths to make imports work from root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app import app, preset_manager

class TestPresetApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.test_storage_path = "backend/v2/test_presets_api.json"
        if os.path.exists(self.test_storage_path):
            os.remove(self.test_storage_path)
            
        # Point the app's preset manager to the test storage and re-initialize
        self.old_storage_path = preset_manager.storage_path
        preset_manager.storage_path = self.test_storage_path
        preset_manager._ensure_storage_exists()
        
        self.client = TestClient(app)

    def tearDown(self):
        if os.path.exists(self.test_storage_path):
            os.remove(self.test_storage_path)
        preset_manager.storage_path = self.old_storage_path

    def test_get_all_presets_endpoint(self):
        response = self.client.get("/api/v2/presets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3) # default preloaded presets

    def test_get_preset_by_id_success(self):
        response = self.client.get("/api/v2/presets/preset_five_ema_aggressive")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Five EMA Aggressive")
        self.assertEqual(data["strategy_id"], "five_ema")

    def test_get_preset_by_id_not_found(self):
        response = self.client.get("/api/v2/presets/unknown_preset")
        self.assertEqual(response.status_code, 404)

    def test_create_preset(self):
        preset_payload = {
            "id": "preset_test_created",
            "name": "Test Created Preset",
            "strategy_id": "heikin_ashi",
            "parameters": {"candle_limit": 8},
            "risk_management": {"cutoff_time": "15:00"},
            "strike_selection": {"mode": "ATM"},
            "expiry_selection": {"mode": "CURRENT_WEEKLY"},
            "timeframe": "1m",
            "notes": "Test notes",
            "tags": ["test"]
        }
        response = self.client.post("/api/v2/presets", json=preset_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Test Created Preset")
        
        # Verify it can be fetched
        response_fetch = self.client.get("/api/v2/presets/preset_test_created")
        self.assertEqual(response_fetch.status_code, 200)
        self.assertEqual(response_fetch.json()["parameters"]["candle_limit"], 8)

    def test_update_preset(self):
        update_payload = {
            "name": "Five EMA Aggressive New Name",
            "timeframe": "3m"
        }
        response = self.client.put("/api/v2/presets/preset_five_ema_aggressive", json=update_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Five EMA Aggressive New Name")
        self.assertEqual(data["timeframe"], "3m")

    def test_duplicate_preset(self):
        response = self.client.post(
            "/api/v2/presets/preset_ema_trend/duplicate", 
            json={"new_name": "EMA Trend Duplicated"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "EMA Trend Duplicated")
        self.assertTrue(data["id"].startswith("preset_"))

    def test_delete_preset(self):
        response = self.client.delete("/api/v2/presets/preset_five_ema_conservative")
        self.assertEqual(response.status_code, 200)
        
        # Verify it is deleted
        response_get = self.client.get("/api/v2/presets/preset_five_ema_conservative")
        self.assertEqual(response_get.status_code, 404)
