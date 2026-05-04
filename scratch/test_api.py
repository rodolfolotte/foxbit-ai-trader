import os
import sys
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from core.foxbit_client import FoxbitClient

def test_ticker():
    client = FoxbitClient()
    try:
        # Try to find the correct ticker endpoint
        try:
            print("Trying /rest/v3/markets/tickers...")
            tickers = client._request("GET", "/rest/v3/markets/tickers")
            print(f"Tickers found: {len(tickers.get('data', []))}")
            if tickers.get('data'):
                print(f"Sample ticker: {json.dumps(tickers.get('data')[0], indent=2)}")
        except Exception as e:
            print(f"Failed /rest/v3/markets/tickers: {e}")
            
        try:
            print("Trying /rest/v3/markets/btcbrl/ticker...")
            ticker = client.get_ticker("btcbrl")
            print(f"Ticker: {json.dumps(ticker, indent=2)}")
        except Exception as e:
            print(f"Failed /rest/v3/markets/btcbrl/ticker: {e}")
            
        try:
            print("Trying /rest/v3/tickers...")
            tickers = client._request("GET", "/rest/v3/tickers")
            print(f"Tickers found: {len(tickers.get('data', []))}")
            if tickers.get('data'):
                print(f"Sample ticker: {json.dumps(tickers.get('data')[0], indent=2)}")
        except Exception as e:
            print(f"Failed /rest/v3/tickers: {e}")
    except Exception as e:
        print(f"Outer Error: {e}")

if __name__ == "__main__":
    test_ticker()
