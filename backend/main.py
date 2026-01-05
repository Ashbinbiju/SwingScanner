from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
import asyncio
from datetime import datetime, timedelta
import pandas as pd
import time
import sys
import os

# Add current directory to sys.path to fix ModuleNotFoundError on Render
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import local modules
from smart_api_client import SmartApiClient
from brkpoint_api import fetch_signals
from backtest_engine import calculate_indicators, validate_setup

app = FastAPI()

# CORS config allowing localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev allowing all, but usually ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Client Instance
client = None

def get_client():
    global client
    if client is None:
        client = SmartApiClient()
        if not client.login():
            raise Exception("Failed to login to SmartAPI")
    return client

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Swing FFD Backend Running"}

@app.post("/run-backtest")
async def run_backtest(payload: dict):
    """
    Payload: {"date": "YYYY-MM-DD"}
    Returns a Stream of JSON strings.
    """
    target_date_str = payload.get("date")
    
    async def event_generator():
        try:
            # 1. Fetch Signals
            yield json.dumps({"type": "status", "message": f"Fetching signals for {target_date_str}..."}) + "\n"
            signals_df = fetch_signals(target_date_str)
            
            if signals_df is None or signals_df.empty:
                yield json.dumps({"type": "error", "message": f"No signals found for {target_date_str}"}) + "\n"
                return

            yield json.dumps({"type": "status", "message": f"Found {len(signals_df)} raw signals. Starting analysis..."}) + "\n"
            
            # 2. Init Client
            try:
                api_client = get_client()
            except Exception as e:
                yield json.dumps({"type": "error", "message": f"SmartAPI Login Failed: {str(e)}"}) + "\n"
                return

            # 3. Ensure Token Map
            if api_client.token_map is None:
                yield json.dumps({"type": "status", "message": "Loading Scrip Master (this may take a moment)..."}) + "\n"
                api_client.load_scrip_master()

            total = len(signals_df)
            valid_trades = []
            rejected_trades = []

            for i, row in signals_df.iterrows():
                symbol = row['tradingsymbol']
                
                # Emit Progress
                progress = (i + 1) / total * 100
                yield json.dumps({
                    "type": "progress", 
                    "value": progress, 
                    "message": f"Processing {symbol} ({i+1}/{total})...",
                    "current_symbol": symbol
                }) + "\n"
                
                # Logic (Copied from app.py)
                try:
                    to_date_obj = datetime.strptime(row['date'], "%Y-%m-%dT%H:%M:%S.%fZ")
                    to_date_str = to_date_obj.strftime("%Y-%m-%d %H:%M")
                    from_date_obj = to_date_obj - timedelta(days=60)
                    from_date_str = from_date_obj.strftime("%Y-%m-%d %H:%M")
                    
                    # Fetch Data
                    hist_df, error_msg = api_client.fetch_historical_data(symbol, from_date_str, to_date_str)
                    
                    if hist_df is not None:
                        hist_df = calculate_indicators(hist_df)
                        result = validate_setup(row, hist_df)
                        
                        if result['valid']:
                            res_row = result.copy()
                            res_row['symbol'] = symbol
                            res_row['date'] = target_date_str
                            valid_trades.append(res_row)
                            # Emit found match immediately!
                            yield json.dumps({"type": "match_found", "data": res_row}) + "\n"
                        else:
                            rej_row = result.copy()
                            rej_row['symbol'] = symbol
                            rejected_trades.append(rej_row)
                            rejected_trades.append(rej_row)
                            # Emit rejected match
                            yield json.dumps({"type": "match_rejected", "message": result['reason'], "current_symbol": symbol}) + "\n"
                    else:
                        msg = f"No Data ({error_msg})"
                        rejected_trades.append({'symbol': symbol, 'reason': msg, 'valid': False})
                        yield json.dumps({"type": "match_rejected", "message": msg, "current_symbol": symbol}) + "\n"
                except Exception as e:
                     rejected_trades.append({'symbol': symbol, 'reason': f"Error: {str(e)}", 'valid': False})

                # Sleep needed for async generator to yield control? 
                # Actually, blocking sleep stops the loop. But fetch_historical_data has sleep.
                # In FastAPI Sync path, it blocks. We should probably make this async properly or use run_in_executor
                # But for now, since it's a generator, the sleep inside fetch_historical_data will just pause this thread.
                # To be safer with rate limits and responsiveness, we keep the sleep in the client.
                await asyncio.sleep(0.01) 

            # Final Result
            yield json.dumps({
                "type": "complete", 
                "valid_count": len(valid_trades),
                "rejected_count": len(rejected_trades),
                "valid_trades": valid_trades
            }) + "\n"

        except Exception as e:
            yield json.dumps({"type": "error", "message": f"Critical Error: {str(e)}"}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
