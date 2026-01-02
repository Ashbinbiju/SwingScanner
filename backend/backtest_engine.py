import pandas as pd

def calculate_indicators(df):
    """
    Adds EMA 9 and EMA 20 to the dataframe.
    """
    if df is None or len(df) < 20:
        return df

    # Calculate EMAs using native pandas
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    return df

def validate_setup(row, historical_df):
    """
    Validates the Long Setup for a single signal.
    
    Rules:
    1. EMA 9 > EMA 20
    2. Price (Close) > EMA 9 & Price (Close) > EMA 20
    3. Trigger candle closes above EMA 9 (Already covered by #2 usually, but explicit check)
    4. EMA 9 pulling back & bouncing (Subjective: We check if Price is near EMA 9 or touched it recently)
    5. Prefer Stage 2 = True + MTF = True (Passed in row)
    
    Returns:
        dict: { 'valid': bool, 'reason': str, 'stop_loss': float, 'target': float }
    """
    
    if historical_df is None or len(historical_df) < 20:
        return {'valid': False, 'reason': 'Insufficient Data'}

    # Get the latest candle (Trigger Candle)
    # Assuming 'date' in signal row matches the last candle in historical_df or we find it.
    # The signal date is ISO format. historical_df date is datetime.
    
    signal_date = pd.to_datetime(row['date']).date()
    
    # Locate the row in historical_df that matches the signal date
    # Note: historical_df might have time component if ONE_MINUTE, but let's assume ONE_DAY for swing
    # or handle the date matching carefully.
    
    try:
        # Find exact match or closest previous match
        trigger_candle = historical_df[historical_df['date'].dt.date == signal_date]
        
        if trigger_candle.empty:
            # Maybe the signal was generated AFTER market close, so it refers to 'today' but data might be there?
            # Or signal date is 'Next Day' for action? Usually signal date = data date.
            # Let's try matching the last available candle if exact date not found?
            # No, dangerous. Let's return Invalid if date mismatch.
            # actually, let's use the last row of the DF provided it is close to signal date.
            trigger_candle = historical_df.iloc[-1]
            trigger_date = trigger_candle['date'].date()
            if abs((trigger_date - signal_date).days) > 5:
                 return {'valid': False, 'reason': 'Data Outdated'}
        else:
            trigger_candle = trigger_candle.iloc[0]

    except Exception as e:
        return {'valid': False, 'reason': f"Date Error: {e}"}

    # Extract values
    close = trigger_candle['close']
    ema_9 = trigger_candle['EMA_9']
    ema_20 = trigger_candle['EMA_20']
    
    # 1. EMA 9 > EMA 20
    if not (ema_9 > ema_20):
        return {'valid': False, 'reason': 'EMA 9 < EMA 20'}
    
    # 2. Price > EMA 9 & Price > EMA 20
    if not (close > ema_9 and close > ema_20):
        return {'valid': False, 'reason': 'Price below EMAs'}
        
    # 3. Trigger candle closes above EMA 9 (Redundant but explicit)
    if not (close > ema_9):
         return {'valid': False, 'reason': 'Close below EMA 9'}

    # 4. "Ideal Zone" Spread Rule (0.3% to 1.2%)
    # Rule: abs(EMA9 - EMA20) / EMA20 
    spread_pct = abs(ema_9 - ema_20) / ema_20 * 100
    
    if spread_pct < 0.3:
        return {'valid': False, 'reason': f'Too Squeezed ({spread_pct:.2f}%)'}
    
    if spread_pct > 1.2:
        return {'valid': False, 'reason': f'Overextended ({spread_pct:.2f}%)'}

    # 5. Stage 2 and MTF check (from Signal Row)
    if not row['is_stage2']:
        return {'valid': False, 'reason': 'Not Stage 2'}
        
    # Stop Loss Logic (from user prompt or calculate?)
    stop_loss = row.get('stop_loss', 0)
    target = row.get('next_target', 0)
    
    return {
        'valid': True, 
        'reason': 'Valid Setup',
        'stop_loss': stop_loss, 
        'target': target,
        'ltp': row['ltp'],
        'close': row.get('close', close), # Use row close by default for accuracy
        'ema_9': ema_9,
        'ema_20': ema_20,
        'spread_pct': spread_pct,
        'is_mtf': row.get('is_mtf', False), 
        'is_stage2': row.get('is_stage2', False),
        'note': row.get('note', '') # For 'New' badge
    }
