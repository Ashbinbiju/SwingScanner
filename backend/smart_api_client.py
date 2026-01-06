import os
import json
import time
import requests
import pandas as pd
from SmartApi import SmartConnect
import pyotp
from datetime import datetime

# Credentials
CLIENT_ID = "AAAG399109"
PASSWORD = "1503"
TOTP_SECRET = "OLRQ3CYBLPN2XWQPHLKMB7WEKI"
HISTORICAL_API_KEY = "c3C0tMGn"

# Scrip Master URL
SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
SCRIP_MASTER_FILE = "OpenAPIScripMaster.json"

class SmartApiClient:
    def __init__(self):
        self.api_key = HISTORICAL_API_KEY
        self.client_id = CLIENT_ID
        self.password = PASSWORD
        self.totp_secret = TOTP_SECRET
        self.smartApi = SmartConnect(api_key=self.api_key)
        self.token_map = None
        
    def login(self):
        try:
            totp = pyotp.TOTP(self.totp_secret).now()
            data = self.smartApi.generateSession(self.client_id, self.password, totp)
            if data['status'] == False:
                print(f"Login Failed: {data}")
                return False
            
            # Retrieve the feed token (optional for historical, but good practice)
            # self.feed_token = self.smartApi.getfeedToken()
            print("SmartAPI Login Successful")
            return True
        except Exception as e:
            print(f"Login Error: {e}")
            return False

    def load_scrip_master(self):
        """Downloads or loads the scrip master JSON to map symbols to tokens."""
        if os.path.exists(SCRIP_MASTER_FILE):
             # Check if file is older than 24 hours, if so, refresh
             file_time = os.path.getmtime(SCRIP_MASTER_FILE)
             if (time.time() - file_time) > 86400:
                 print("Scrip master old, downloading...")
                 self._download_scrip_master()
        else:
            print("Scrip master not found, downloading...")
            self._download_scrip_master()

        # Load into memory
        print("Loading Scrip Master...")
        with open(SCRIP_MASTER_FILE, 'r') as f:
            data = json.load(f)
            # Create a dictionary for fast lookup: Symbol -> {Token, Exchange}
            # Assuming we prioritize NSE.
            self.token_map = {}
            for item in data:
                if item['exch_seg'] == 'NSE' and item['symbol'].endswith('-EQ'):
                     symbol_root = item['symbol'].replace('-EQ', '')
                     self.token_map[symbol_root] = item
                elif item['exch_seg'] == 'NSE':
                     # Fallback or specific handling if needed
                     self.token_map[item['symbol']] = item
        print(f"Loaded {len(self.token_map)} NSE symbols.")

    def _download_scrip_master(self):
        r = requests.get(SCRIP_MASTER_URL)
        if r.status_code == 200:
            with open(SCRIP_MASTER_FILE, 'w') as f:
                f.write(r.text)
        else:
            print(f"Failed to download Scrip Master: {r.status_code}")


    def get_token(self, symbol):
        if self.token_map is None:
            self.load_scrip_master()
        
        # 1. Direct match (e.g. from keys I stored)
        if symbol in self.token_map:
            return self.token_map[symbol]['token']
        
        # 2. Key might be upper/lower case mismatch?
        # My keys are from cleaned symbols in UPPER.
        
        return None

    def fetch_historical_data(self, symbol, from_date, to_date, interval='ONE_DAY'):
        """
        Fetches historical data.
        Returns (df, error_message)
        """
        token = self.get_token(symbol)
        if not token:
            return None, f"Token Not Found for {symbol}"

        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": interval,
            "fromdate": from_date,
            "todate": to_date
        }

        for attempt in range(5):
            try:
                response = self.smartApi.getCandleData(params)
                
                # Verify response is valid
                if response is None:
                    # Treat None as error
                    return None, "API returned None"

                # Safe access 'status'
                status = response.get('status', False)
                
                if status == True and response.get('data'):
                    df = pd.DataFrame(response['data'], columns=['date', 'open', 'high', 'low', 'close', 'volume'])
                    df['date'] = pd.to_datetime(df['date'])
                    df['open'] = df['open'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['close'] = df['close'].astype(float)
                    df['volume'] = df['volume'].astype(int)
                    return df, None
                else:
                    msg = response.get('message', 'Unknown API Error')
                    error_code = response.get('errorcode', '')
                    # If Rate Limit or Server Error (AB1004), Retry
                    if error_code in ['AB1004', 'AB1005', 'AB2001']:
                         print(f"[{symbol}] Rate limit hit ({error_code}), attempt {attempt+1}/5. Sleeping 5s...")
                         time.sleep(5) 
                         if attempt == 2:
                             self.login()
                         continue
                    
                    # Self-Healing: If Invalid Token, Refresh Scrip Master
                    if "Invalid Token" in msg or error_code == "AG8001": # Common invalid token code
                         print(f"[{symbol}] Invalid Token detected. Refreshing Scrip Master...")
                         self._download_scrip_master()
                         self.load_scrip_master()
                         # Should we update the token variable?
                         token = self.get_token(symbol)
                         params["symboltoken"] = token
                         time.sleep(2)
                         continue

                    return None, f"API Error: {msg} ({error_code})"
            except Exception as e:
                print(f"Exception for {symbol}: {e}")
                # import traceback
                # traceback.print_exc()
                time.sleep(2)
                if attempt == 4:
                     return None, f"Exception: {str(e)}"
        
        return None, "Max Retries Exceeded"

if __name__ == "__main__":
    # Test
    client = SmartApiClient()
    if client.login():
        client.load_scrip_master()
        # Test fetch for Reliance
        df = client.fetch_historical_data("RELIANCE", "2024-12-01 09:15", "2024-12-31 15:30")
        if df is not None:
            print(df.tail())
