import pandas as pd
import pandas_ta as ta

def evaluate_confluence(df: pd.DataFrame, macro_trend: str = "UNKNOWN") -> dict:
    """
    Evaluates three different strategies on the provided DataFrame.
    Returns a dictionary with the votes and the final decision.
    +1 for BUY, -1 for SELL, 0 for HOLD.
    macro_trend: 'BULL', 'BEAR', or 'UNKNOWN'
    """
    # 1. Calculate Indicators
    # Bollinger Bands (Length=20, StdDev=2)
    df.ta.bbands(length=20, std=2, append=True)
    # MACD (Fast=12, Slow=26, Signal=9)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    # RSI (Length=14)
    df.ta.rsi(length=14, append=True)
    # EMAs (Fast=9, Slow=21)
    df.ta.ema(length=9, append=True)
    df.ta.ema(length=21, append=True)

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    current_price = latest['close']

    # Safely extract column names since pandas_ta names can be dynamic
    try:
        bbl_col = [c for c in df.columns if c.startswith('BBL')][0]
        bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
        macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
        macds_col = [c for c in df.columns if c.startswith('MACDs')][0]
        ema_fast_col = [c for c in df.columns if c.startswith('EMA_9')][0]
        ema_slow_col = [c for c in df.columns if c.startswith('EMA_21')][0]
        rsi_col = [c for c in df.columns if c.startswith('RSI')][0]
    except IndexError:
        return {"error": "Could not calculate all indicators due to insufficient data."}

    # Extract values
    bb_lower = latest[bbl_col]
    bb_upper = latest[bbu_col]
    
    macd_line = latest[macd_col]
    macd_signal = latest[macds_col]
    prev_macd_line = prev[macd_col]
    prev_macd_signal = prev[macds_col]
    
    current_rsi = latest[rsi_col]
    
    ema_fast = latest[ema_fast_col]
    ema_slow = latest[ema_slow_col]
    prev_ema_fast = prev[ema_fast_col]
    prev_ema_slow = prev[ema_slow_col]

    # --- Strategy 1: MACD + Bollinger Bands ---
    vote_macd_bb = 0
    price_near_lower_bb = current_price <= (bb_lower * 1.01) # Within 1% of lower band
    price_near_upper_bb = current_price >= (bb_upper * 0.99) # Within 1% of upper band
    macd_bullish_cross = (prev_macd_line <= prev_macd_signal) and (macd_line > macd_signal)
    macd_bearish_cross = (prev_macd_line >= prev_macd_signal) and (macd_line < macd_signal)
    
    if price_near_lower_bb and macd_bullish_cross:
        vote_macd_bb = 1
    elif price_near_upper_bb and macd_bearish_cross:
        vote_macd_bb = -1

    # --- Strategy 2: RSI Reversion ---
    vote_rsi = 0
    if current_rsi < 30:
        vote_rsi = 1
    elif current_rsi > 70:
        vote_rsi = -1

    # --- Strategy 3: EMA Crossover ---
    vote_ema = 0
    ema_bullish_cross = (prev_ema_fast <= prev_ema_slow) and (ema_fast > ema_slow)
    ema_bearish_cross = (prev_ema_fast >= prev_ema_slow) and (ema_fast < ema_slow)
    
    # We also check if we are in a strong trend (Fast > Slow by a margin)
    if ema_bullish_cross or (ema_fast > ema_slow and current_price > ema_fast):
        vote_ema = 1
    elif ema_bearish_cross or (ema_fast < ema_slow and current_price < ema_fast):
        vote_ema = -1

    # --- Final Confluence Decision ---
    total_score = vote_macd_bb + vote_rsi + vote_ema
    
    decision = "HOLD"
    if total_score >= 2:
        decision = "BUY"
    elif total_score <= -2:
        decision = "SELL"
        
    # --- Multi-Timeframe Analysis (MTFA) Veto ---
    if macro_trend == "BULL" and decision == "SELL":
        decision = "HOLD"
    elif macro_trend == "BEAR" and decision == "BUY":
        decision = "HOLD"

    return {
        "current_price": current_price,
        "vote_macd_bb": vote_macd_bb,
        "vote_rsi": vote_rsi,
        "vote_ema": vote_ema,
        "total_score": total_score,
        "decision": decision,
        "macro_trend": macro_trend
    }

def format_vote(vote: int) -> str:
    if vote == 1:
        return "[bold green]BUY[/bold green]"
    elif vote == -1:
        return "[bold red]SELL[/bold red]"
    return "[dim]HOLD[/dim]"
