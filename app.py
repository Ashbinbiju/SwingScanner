import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

# Import our modules
from smart_api_client import SmartApiClient
from brkpoint_api import fetch_signals
from backtest_engine import calculate_indicators, validate_setup

st.set_page_config(page_title="Swing Backtest UI", layout="wide")

st.title("Swing Trading Backtest & Validations")

# --- Sidebar / Configuration ---
st.sidebar.header("Configuration")
target_date = st.sidebar.date_input("Select Date", datetime(2026, 1, 1))
# Convert to YYYY-MM-DD
date_str = target_date.strftime("%Y-%m-%d")

# Init API Client
@st.cache_resource
def get_smart_api_client():
    client = SmartApiClient()
    if client.login():
        return client
    return None

client = get_smart_api_client()

if not client:
    st.error("Failed to login to SmartAPI. Check console logs or credentials.")
    st.stop()

# Load Scrip Master (Cached)
if st.sidebar.button("Reload Scrip Master"):
    st.cache_resource.clear()
    client = get_smart_api_client()
    with st.spinner("Downloading Scrip Master..."):
        client.load_scrip_master()
    st.success("Reloaded!")

if client.token_map is None:
     with st.spinner("Loading Scrip Master..."):
        client.load_scrip_master()

# --- Main Logic ---

if st.button("Run Backtest"):
    st.info(f"Fetching signals for {date_str}...")
    
    signals_df = fetch_signals(date_str)
    
    if signals_df is None or signals_df.empty:
        st.warning(f"No signals found for {date_str}.")
    else:
        st.success(f"Found {len(signals_df)} raw signals.")
        
        # Display Raw Signals (Optional)
        with st.expander("View Raw Signals"):
            st.dataframe(signals_df)

        valid_trades = []
        rejected_trades = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(signals_df)
        
        for i, row in signals_df.iterrows():
            symbol = row['tradingsymbol']
            status_text.text(f"Processing {symbol} ({i+1}/{total})...")
            
            # Fetch Historical Data
            # We need data ending at the signal date. 
            # If signal date is today, we fetch last 30 days.
            to_date_obj = datetime.strptime(row['date'], "%Y-%m-%dT%H:%M:%S.%fZ") # Adjust format if needed
            # The signal date in JSON is like "2025-12-31T18:30:00.000Z"
            # We need to fetch data up to this point. 
            
            # Format dates for API
            to_date_str = to_date_obj.strftime("%Y-%m-%d %H:%M")
            from_date_obj = to_date_obj - timedelta(days=60) # Fetch 60 days for reliable EMA
            from_date_str = from_date_obj.strftime("%Y-%m-%d %H:%M")
            
            hist_df, error_msg = client.fetch_historical_data(symbol, from_date_str, to_date_str)
            
            if hist_df is not None:
                # Calculate Indicators
                hist_df = calculate_indicators(hist_df)
                
                # Validate
                result = validate_setup(row, hist_df)
                
                if result['valid']:
                    res_row = result.copy()
                    res_row['symbol'] = symbol
                    res_row['date'] = date_str
                    valid_trades.append(res_row)
                else:
                    rej_row = result.copy()
                    rej_row['symbol'] = symbol
                    rejected_trades.append(rej_row)
            else:
                rejected_trades.append({'symbol': symbol, 'reason': f"No Data ({error_msg})", 'valid': False})

            progress_bar.progress((i + 1) / total)
            time.sleep(1.0) # Increased to 1.0s + Retry Logic in Client

        status_text.text("Processing Complete.")
        
        # --- Results ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"✅ Valid Long Setups ({len(valid_trades)})")
            if valid_trades:
                valid_df = pd.DataFrame(valid_trades)
                # Reorder cols
                cols = ['symbol', 'close', 'spread_pct', 'ltp', 'stop_loss', 'target', 'ema_9', 'ema_20']
                st.dataframe(valid_df[cols])
            else:
                st.write("No valid setups found.")

        with col2:
            st.subheader(f"❌ Rejected Signals ({len(rejected_trades)})")
            if rejected_trades:
                rej_df = pd.DataFrame(rejected_trades)
                st.dataframe(rej_df)
            else:
                 st.write("No rejected signals.")
