import os
import json
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("Valkyrie.PresetManager")

class StrategyPreset(BaseModel):
    id: str = Field(default_factory=lambda: "preset_" + str(uuid.uuid4())[:8])
    name: str
    strategy_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    risk_management: Dict[str, Any] = Field(default_factory=dict)
    strike_selection: Dict[str, Any] = Field(default_factory=dict)
    expiry_selection: Dict[str, Any] = Field(default_factory=dict)
    timeframe: str
    notes: Optional[str] = ""
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

DEFAULT_PRESETS = [
    {
        "id": "preset_five_ema_aggressive",
        "name": "Five EMA Aggressive",
        "strategy_id": "five_ema",
        "parameters": {
            "five_ema_period": 5,
            "five_ema_rr": 4.0,
            "max_candles": 5,
            "cut_off_time": "15:15"
        },
        "risk_management": {
            "target_type": "percent",
            "target_value": 4.0,
            "stop_loss_type": "percent",
            "stop_loss_value": 1.5,
            "max_holding_candles": 5,
            "cutoff_time": "15:15"
        },
        "strike_selection": {"mode": "OTM_1"},
        "expiry_selection": {"mode": "CURRENT_WEEKLY"},
        "timeframe": "1m",
        "notes": "Aggressive scalping settings with tight exit and higher risk-reward targets.",
        "tags": ["scalping", "aggressive", "5ema"]
    },
    {
        "id": "preset_five_ema_conservative",
        "name": "Five EMA Conservative",
        "strategy_id": "five_ema",
        "parameters": {
            "five_ema_period": 5,
            "five_ema_rr": 2.5,
            "max_candles": 15,
            "cut_off_time": "15:15"
        },
        "risk_management": {
            "target_type": "percent",
            "target_value": 2.5,
            "stop_loss_type": "percent",
            "stop_loss_value": 0.8,
            "max_holding_candles": 15,
            "cutoff_time": "15:15"
        },
        "strike_selection": {"mode": "ATM"},
        "expiry_selection": {"mode": "CURRENT_WEEKLY"},
        "timeframe": "5m",
        "notes": "Conservative scalping settings using ATM strikes for lower slippage and a lower reward multiplier.",
        "tags": ["scalping", "conservative", "5ema"]
    },
    {
        "id": "preset_ema_trend",
        "name": "EMA Trend",
        "strategy_id": "ema",
        "parameters": {
            "fast_period": 9,
            "slow_period": 21,
            "cut_off_time": "15:25"
        },
        "risk_management": {
            "target_type": "none",
            "target_value": 0.0,
            "stop_loss_type": "none",
            "stop_loss_value": 0.0,
            "max_holding_candles": 100,
            "cutoff_time": "15:25"
        },
        "strike_selection": {"mode": "ATM"},
        "expiry_selection": {"mode": "CURRENT_WEEKLY"},
        "timeframe": "5m",
        "notes": "Standard trend crossover settings using 9 and 21 periods.",
        "tags": ["trend", "crossover", "ema"]
    }
]

class PresetManager:
    def __init__(self, storage_path: str = "backend/v2/presets.json"):
        self.storage_path = storage_path
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            logger.info(f"Presets file not found. Preloading {len(DEFAULT_PRESETS)} default presets.")
            self._save_presets_raw(DEFAULT_PRESETS)

    def _load_presets_raw(self) -> List[Dict[str, Any]]:
        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read presets from {self.storage_path}: {e}")
            return []

    def _save_presets_raw(self, presets: List[Dict[str, Any]]):
        try:
            with open(self.storage_path, "w") as f:
                json.dump(presets, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to write presets to {self.storage_path}: {e}")

    def get_all_presets(self) -> List[StrategyPreset]:
        raw_list = self._load_presets_raw()
        presets = []
        for raw in raw_list:
            try:
                presets.append(StrategyPreset(**raw))
            except Exception as e:
                logger.error(f"Invalid preset schema in file: {raw}. Error: {e}")
        return presets

    def get_preset(self, preset_id: str) -> Optional[StrategyPreset]:
        presets = self.get_all_presets()
        for p in presets:
            if p.id == preset_id:
                return p
        return None

    def create_preset(self, preset: StrategyPreset) -> StrategyPreset:
        presets = self._load_presets_raw()
        # Remove any existing preset with same ID to avoid duplicates
        presets = [p for p in presets if p["id"] != preset.id]
        presets.append(preset.model_dump())
        self._save_presets_raw(presets)
        return preset

    def update_preset(self, preset_id: str, preset_data: Dict[str, Any]) -> Optional[StrategyPreset]:
        presets = self._load_presets_raw()
        updated_preset = None
        for i, p in enumerate(presets):
            if p["id"] == preset_id:
                # Merge data
                for k, v in preset_data.items():
                    if k != "id":
                        p[k] = v
                p["updated_at"] = datetime.utcnow().isoformat() + "Z"
                updated_preset = StrategyPreset(**p)
                presets[i] = p
                break
        if updated_preset:
            self._save_presets_raw(presets)
        return updated_preset

    def delete_preset(self, preset_id: str) -> bool:
        presets = self._load_presets_raw()
        original_len = len(presets)
        presets = [p for p in presets if p["id"] != preset_id]
        if len(presets) < original_len:
            self._save_presets_raw(presets)
            return True
        return False

    def duplicate_preset(self, preset_id: str, new_name: str) -> Optional[StrategyPreset]:
        source = self.get_preset(preset_id)
        if not source:
            return None
        
        duplicated_data = source.model_dump()
        duplicated_data["id"] = "preset_" + str(uuid.uuid4())[:8]
        duplicated_data["name"] = new_name
        duplicated_data["created_at"] = datetime.utcnow().isoformat() + "Z"
        duplicated_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        dup_preset = StrategyPreset(**duplicated_data)
        self.create_preset(dup_preset)
        return dup_preset
