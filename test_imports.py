try:
    import smart_api_client
    import brkpoint_api
    import backtest_engine
    import app
    print("Imports successful.")
except Exception as e:
    print(f"Import failed: {e}")
