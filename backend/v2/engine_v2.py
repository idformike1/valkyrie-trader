import logging
from v2.config import BacktestConfig

logger = logging.getLogger("ValkyrieV2")

def run_backtest_v2(config_dict: dict) -> dict:
    """
    V2 Engine entry point.
    Executes a high-fidelity option backtest using the BacktestRunner.
    """
    # Validate payload
    config = BacktestConfig(**config_dict)
    
    logger.info(f"[V2 Engine] Initialized backtest for {config.underlying_instrument_key}")
    logger.info(f"[V2 Engine] Strike Mode: {config.strike_selection.mode} | Expiry Mode: {config.expiry_selection.mode}")
    
    from v2.backtest_runner import BacktestRunner
    import json
    
    result = BacktestRunner.run(config)
    
    # Safely convert to JSON primitives (including datetime serialization)
    result_json = json.loads(result.model_dump_json())
    
    return {
        "status": "accepted",
        "engine": "v2",
        "configuration": config.model_dump(),
        "result": result_json
    }
