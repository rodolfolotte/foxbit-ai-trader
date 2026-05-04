import os
import sys
import json
import time
from datetime import datetime
import pandas as pd
import pandas_ta as ta
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Button, Label
from textual.containers import Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual import work
from textual_plotext import PlotextPlot

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)
from core.foxbit_client import FoxbitClient

class RSIChart(PlotextPlot):
    def update_data(self, timestamps: list, rsi_values: list):
        self.plt.clear_figure()
        self.plt.title("BTC-BRL Live RSI Pulse")
        self.plt.xlabel("Time (15m candles)")
        self.plt.ylabel("RSI")
        self.plt.ylim(0, 100)
        
        # Safe plotting method for plotext: pass only Y values, set X ticks manually
        self.plt.plot(rsi_values, color="cyan", marker="dot")
        
        # Use a subset of ticks so they don't overlap if terminal is small
        if len(timestamps) > 0:
            indices = list(range(len(timestamps)))
            # Only show about 5-6 labels total regardless of data size
            step = max(1, len(timestamps) // 5)
            tick_indices = indices[::step]
            tick_labels = timestamps[::step]
            self.plt.xticks(tick_indices, tick_labels)
            
        self.plt.hline(70, color="red")
        self.plt.hline(30, color="green")
        self.plt.grid(True, True)
        self.refresh()

class FoxbitTrader(App):
    """Ultimate 4-Panel Textual TUI Dashboard."""

    CSS = """
    Screen {
        background: $surface;
    }
    Grid {
        grid-size: 2;
        grid-rows: 1fr 1fr;
        grid-columns: 1fr 1fr;
    }
    .panel {
        border: solid $primary;
        height: 100%;
    }
    #wallet-panel { row-span: 1; column-span: 1; }
    #market-panel { row-span: 1; column-span: 1; }
    #trades-panel { row-span: 1; column-span: 1; }
    #chart-panel { row-span: 1; column-span: 1; }
    
    #control-bar {
        height: 3;
        padding: 0 1;
        background: $panel;
        border: solid $secondary;
    }
    #ticker-bar {
        height: 1;
        padding: 0 0;
        background: $primary-background;
        overflow: hidden;
    }
    #status-label {
        width: 1fr;
        content-align: center middle;
    }
    #strategy-label {
        width: 1fr;
        content-align: center middle;
    }
    #total-wallet-label {
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        color: $success;
    }
    #ticker-label {
        width: auto;
    }
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit Dashboard"),
        ("r", "refresh_data", "Refresh Data")
    ]

    live_mode = reactive(False)
    ticker_data = Text(" Loading Market Ticker... ")
    ticker_offset = 0
    market_names = {}
    cached_prices = {}
    cached_market_data = {}  # Store everything from market_state.json

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="control-bar"):
            yield Label("Loading...", id="status-label")
            yield Button("LIVE/PAPER", id="toggle-button", variant="primary")
            yield Label("TOTAL PORTFOLIO: R$ ...", id="total-wallet-label")
            yield Label("Strategy...", id="strategy-label")
            yield Button("STRATEGY", id="strategy-button", variant="warning")
            
        with Horizontal(id="ticker-bar"):
            yield Label("", id="ticker-label")
        
        with Grid():
            with Vertical(classes="panel", id="wallet-panel"):
                yield Label("Live Wallet Balances", classes="panel-title")
                yield DataTable(id="wallet-table")
                
            with Vertical(classes="panel", id="market-panel"):
                yield Label("Global Market Situation", classes="panel-title")
                yield DataTable(id="market-table")
                
            with Vertical(classes="panel", id="trades-panel"):
                yield Label("Trade History & Reasoning", classes="panel-title")
                yield DataTable(id="trades-table")
                
            with Vertical(classes="panel", id="chart-panel"):
                yield Label("Live Market Pulse", classes="panel-title")
                yield RSIChart(id="rsi-chart")
                
        yield Footer()

    def on_mount(self) -> None:
        wallet = self.query_one("#wallet-table", DataTable)
        wallet.add_columns("Asset", "Symbol", "Balance", "Value (R$)", "24h Chg%", "Acquired")
        
        market = self.query_one("#market-table", DataTable)
        market.add_columns("Market", "Price", "24h Vol", "Macro", "MACD", "RSI", "EMA", "Decision")
        
        trades = self.query_one("#trades-table", DataTable)
        trades.add_columns("Time", "Market", "Action", "Price", "Qty", "Reasoning")

        self.client = FoxbitClient()
        
        # Build normal names dict
        try:
            m_res = self.client.get_markets()
            for m in m_res.get("data", []):
                sym = m.get("symbol", "").upper()
                name = m.get("base", {}).get("name", sym)
                self.market_names[sym] = name
        except Exception:
            pass

        self.check_env_status()
        
        # Dispatch initial manual calls
        self.auto_refresh_tables()
        self.live_chart_worker()
        self.slow_ticker_worker()

        # Safely register repeating intervals so they don't block `q`uit
        self.set_interval(10.0, self.auto_refresh_tables)
        self.set_interval(30.0, self.live_chart_worker)
        self.set_interval(60.0, self.slow_ticker_worker)
        
        # Super fast Marquee scroller (runs on main thread safely)
        self.set_interval(0.2, self.scroll_ticker)

    def scroll_ticker(self) -> None:
        if len(self.ticker_data) > 0:
            self.ticker_offset = (self.ticker_offset + 1) % len(self.ticker_data)
            display_text = self.ticker_data[self.ticker_offset:] + self.ticker_data[:self.ticker_offset]
            label = self.query_one("#ticker-label", Label)
            label.update(display_text)

    def check_env_status(self) -> None:
        self.live_mode = False
        strategy_mode = "MAX_GAIN"
        
        env_file = os.path.join(PROJECT_ROOT, ".env")
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                content = f.read()
                if "APP_STATUS=LIVE" in content:
                    self.live_mode = True
                if "STRATEGY_MODE=LONG_TERM" in content:
                    strategy_mode = "LONG_TERM"

        status_label = self.query_one("#status-label", Label)
        if self.live_mode:
            status_label.update("[bold green]CURRENT MODE: LIVE (REAL MONEY)[/bold green]")
        else:
            status_label.update("[bold yellow]CURRENT MODE: PAPER (SIMULATED)[/bold yellow]")
            
        strategy_label = self.query_one("#strategy-label", Label)
        if strategy_mode == "LONG_TERM":
            strategy_label.update("[bold blue]STRATEGY: LONG TERM[/bold blue]")
        else:
            strategy_label.update("[bold magenta]STRATEGY: MAX GAIN[/bold magenta]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "toggle-button":
            toggle_script = os.path.join(PROJECT_ROOT, "toggle_live.py")
            os.system(f"python3 {toggle_script} > /dev/null")
            self.check_env_status()
        elif event.button.id == "strategy-button":
            toggle_script = os.path.join(PROJECT_ROOT, "toggle_strategy.py")
            os.system(f"python3 {toggle_script} > /dev/null")
            self.check_env_status()

    def action_refresh_data(self) -> None:
        self.check_env_status()
        self.refresh_wallet_table()
        self.refresh_market()
        self.refresh_trades()

    @work(exclusive=True, thread=True)
    def auto_refresh_tables(self) -> None:
        """Fast worker triggered by set_interval."""
        self.call_from_thread(self.refresh_wallet_table)
        self.call_from_thread(self.refresh_market)
        self.call_from_thread(self.refresh_trades)

    @work(exclusive=True, thread=True)
    def live_chart_worker(self) -> None:
        """Chart worker triggered by set_interval."""
        try:
            data = self.client.get_candlesticks("btcbrl", interval="15m", limit=60)
            if data and len(data) > 30:
                data.reverse()
                df = pd.DataFrame(data).iloc[:, :6]
                df.columns = ["timestamp", "open", "high", "low", "close", "close_time"]
                df["close"] = pd.to_numeric(df["close"])
                df.ta.rsi(length=14, append=True)
                df.dropna(inplace=True)
                
                plot_df = df.tail(30)
                rsi_col = [c for c in plot_df.columns if c.startswith('RSI')][0]
                y_vals = [float(y) for y in plot_df[rsi_col].tolist()]
                x_vals = [datetime.fromtimestamp(int(ts)/1000).strftime('%H:%M') for ts in plot_df["timestamp"]]
                
                chart = self.query_one("#rsi-chart", RSIChart)
                self.call_from_thread(chart.update_data, x_vals, y_vals)
        except Exception as e:
            self.log(f"Chart error: {e}")

    @work(exclusive=True, thread=True)
    def slow_ticker_worker(self) -> None:
        """Slow worker triggered by set_interval for Fiat calculations and Ticker."""
        try:
            # 1. Total Portfolio Calculation
            total_brl = 0.0
            res = self.client.get_balances()
            for acc in res.get("data", []):
                bal = float(acc.get("balance", acc.get("available", "0")))
                if bal > 0:
                    sym = acc.get("currency_symbol", acc.get("symbol", "UKN")).upper()
                    if sym == "BRL":
                        total_brl += bal
                    else:
                        try:
                            mkt_symbol = f"{sym.lower()}brl"
                            p_data = self.client.get_candlesticks(mkt_symbol, interval="1m", limit=1)
                            if p_data:
                                current_price = float(p_data[0][4])
                                self.cached_prices[sym] = current_price
                                total_brl += (bal * current_price)
                        except Exception:
                            pass
            
            wallet_label = self.query_one("#total-wallet-label", Label)
            self.call_from_thread(wallet_label.update, f"[bold green]TOTAL PORTFOLIO: R$ {total_brl:,.2f}[/bold green]")
            
            # 2. Ticker Tape Generation using CACHED data from market_state.json
            new_ticker = Text(no_wrap=True)
            
            state_file = os.path.join(PROJECT_ROOT, "data/market_state.json")
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r") as f:
                        data = json.load(f)
                    
                    self.cached_market_data = {m['market'].upper(): m for m in data.get("markets", [])}
                    
                    # Generate ticker from cached data
                    for sym, m in self.cached_market_data.items():
                        price = m.get("price", 0.0)
                        change = m.get("change_24h", 0.0)
                        normal_name = self.market_names.get(sym, sym)
                        
                        if change >= 0:
                            new_ticker.append(f" ▲ {normal_name}: R$ {price:,.2f} (+{change:.2f}%)    ", style="bold green")
                        else:
                            new_ticker.append(f" ▼ {normal_name}: R$ {price:,.2f} ({change:.2f}%)    ", style="bold red")
                    
                    if len(new_ticker) > 0:
                        self.ticker_data = new_ticker + new_ticker
                except Exception as e:
                    self.log(f"Ticker generation error: {e}")

        except Exception as e:
            self.log(f"Ticker error: {e}")

    def get_last_acquired(self, symbol_brl: str) -> str:
        log_file = os.path.join(PROJECT_ROOT, "data/trade_history.json")
        if not os.path.exists(log_file):
            return "N/A"
        try:
            with open(log_file, "r") as f:
                trades = json.load(f)
            for t in reversed(trades):
                if t['market'].upper() == symbol_brl.upper() and t['action'] == "BUY":
                    dt = t['timestamp'].replace('T', ' ')[:16]
                    return dt
        except Exception:
            pass
        return "N/A"

    def refresh_wallet_table(self) -> None:
        """Fast refresh for table balances ONLY."""
        table = self.query_one("#wallet-table", DataTable)
        table.clear()
        try:
            res = self.client.get_balances()
            accounts = res.get("data", [])
            for acc in accounts:
                bal = float(acc.get("balance", acc.get("available", "0")))
                if bal > 0:
                    symbol = acc.get("currency_symbol", acc.get("symbol", "UKN")).upper()
                    if bal > 10:
                        bal_str = f"{bal:.2f}"
                    else:
                        bal_str = f"{bal:.6f}"
                    
                    change_str = "0.00%"
                    if symbol == "BRL":
                        val_str = f"R$ {bal:,.2f}"
                        change_str = "-"
                    else:
                        m_data = self.cached_market_data.get(f"{symbol}BRL")
                        if m_data:
                            price = m_data.get("price", 0.0)
                            val_str = f"R$ {(bal * price):,.2f}"
                            change = m_data.get("change_24h", 0.0)
                            if change > 0:
                                change_str = f"[bold green]+{change:.2f}%[/]"
                            elif change < 0:
                                change_str = f"[bold red]{change:.2f}%[/]"
                            else:
                                change_str = f"{change:.2f}%"
                        else:
                            val_str = "Loading..."
                            change_str = "..."
                    
                    last_acq = self.get_last_acquired(f"{symbol}BRL") if symbol != "BRL" else "-"
                    normal_name = self.market_names.get(f"{symbol}BRL", symbol) if symbol != "BRL" else "Real (BRL)"
                    table.add_row(normal_name, symbol, bal_str, val_str, change_str, last_acq)
        except Exception:
            pass

    def refresh_market(self) -> None:
        table = self.query_one("#market-table", DataTable)
        table.clear()
        state_file = os.path.join(PROJECT_ROOT, "data/market_state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                
                # Update panel title with last update time
                ts = data.get("timestamp", "")
                if ts:
                    dt = datetime.fromisoformat(ts).strftime("%H:%M:%S")
                    label = self.query_one("#market-panel .panel-title", Label)
                    label.update(f"Global Market Situation [dim](Last Scan: {dt})[/]")

                for m in data.get("markets", []):
                    sym = m['market'].upper()
                    normal_name = self.market_names.get(sym, sym)
                    
                    price = m.get("price", 0.0)
                    price_str = f"R$ {price:,.2f}" if price > 0 else "N/A"
                    
                    vol = m.get("volume_24h", 0.0)
                    vol_str = f"R$ {vol:,.0f}" if vol > 0 else "N/A"

                    macro = f"[bold green]{m['macro']}[/]" if m['macro'] == "BULL" else f"[bold red]{m['macro']}[/]" if m['macro'] == "BEAR" else m['macro']
                    dec = f"[bold green]{m['decision']}[/]" if m['decision'] == "BUY" else f"[bold red]{m['decision']}[/]" if m['decision'] == "SELL" else f"[dim]{m['decision']}[/]"
                    table.add_row(normal_name, price_str, vol_str, macro, m['macd_vote'], m['rsi_vote'], m['ema_vote'], dec)
            except Exception:
                pass

    def refresh_trades(self) -> None:
        table = self.query_one("#trades-table", DataTable)
        table.clear()
        log_file = os.path.join(PROJECT_ROOT, "data/trade_history.json")
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    trades = json.load(f)
                for t in reversed(trades[-50:]):
                    action_fmt = f"[bold green]{t['action']}[/]" if t['action'] == "BUY" else f"[bold red]{t['action']}[/]"
                    ts = t['timestamp'].replace('T', ' ')[:19]
                    reason = t.get("reason", "Manual")
                    table.add_row(ts, t['market'], action_fmt, f"R$ {t['price']}", t['quantity'], reason)
            except Exception:
                pass

if __name__ == "__main__":
    app = FoxbitTrader()
    app.run()
