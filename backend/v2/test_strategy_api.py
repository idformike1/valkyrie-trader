import unittest
import sys
import os

# Adjust paths to make imports work from root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app import app

class TestStrategyApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_all_strategies_endpoint(self):
        response = self.client.get("/api/v2/strategies")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)

        # Check fields exist for each strategy
        for strategy in data:
            self.assertIn("id", strategy)
            self.assertIn("name", strategy)
            self.assertIn("category", strategy)
            self.assertIn("description", strategy)
            self.assertIn("risk_level", strategy)
            self.assertIn("supported_parameters", strategy)

    def test_get_strategy_by_id_endpoint_success(self):
        # Test five_ema
        response = self.client.get("/api/v2/strategies/five_ema")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "five_ema")
        self.assertEqual(data["name"], "Five EMA Option Scalping")

        # Test heikin_ashi alias
        response_ha = self.client.get("/api/v2/strategies/heikin_ashi_gar")
        self.assertEqual(response_ha.status_code, 200)
        data_ha = response_ha.json()
        self.assertEqual(data_ha["id"], "heikin_ashi")

    def test_get_strategy_by_id_endpoint_not_found(self):
        response = self.client.get("/api/v2/strategies/unknown_strategy_id")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())
