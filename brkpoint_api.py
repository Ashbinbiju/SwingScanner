import requests
import pandas as pd

API_URL = "https://brkpoint.in/api/smc-scanner/signals"

def fetch_signals(date_str):
    """
    Fetches signals for a specific date (YYYY-MM-DD).
    Returns a DataFrame of signals or None if failed.
    """
    try:
        url = f"{API_URL}?date={date_str}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if 'results' in data:
                return pd.DataFrame(data['results'])
        print(f"Failed to fetch signals: {response.status_code}")
        return None
    except Exception as e:
        print(f"Error fetching signals: {e}")
        return None
