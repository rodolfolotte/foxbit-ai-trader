import os
import time
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv

class FoxbitClient:
    """
    A Python client to interact with the Foxbit V3 REST API.
    Handles authentication and signatures automatically.
    """
    BASE_URL = "https://api.foxbit.com.br"

    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("FOXBIT_API_KEY")
        self.api_secret = os.getenv("FOXBIT_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            print("WARNING: FOXBIT_API_KEY or FOXBIT_API_SECRET not found in .env")

    def _generate_signature(self, timestamp: str, method: str, path: str, query_string: str, body: str) -> str:
        """
        Generates HMAC SHA256 signature for private endpoints.
        """
        pre_hash = f"{timestamp}{method}{path}{query_string}{body}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            pre_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, path: str, params: dict = None, data: dict = None, is_private: bool = False):
        url = f"{self.BASE_URL}{path}"
        headers = {
            "Content-Type": "application/json"
        }

        query_string = ""
        if params:
            # Sort params and build query string (Foxbit might not require sorting, but it's good practice)
            # requests handles params automatically, but for signature we need the exact string
            req = requests.models.PreparedRequest()
            req.prepare_url(url, params)
            query_string = req.url.split('?')[1] if '?' in req.url else ""

        body_str = json.dumps(data) if data else ""

        if is_private:
            if not self.api_key or not self.api_secret:
                raise ValueError("API Key and Secret are required for private endpoints.")
            
            timestamp = str(int(time.time() * 1000))
            signature = self._generate_signature(timestamp, method, path, query_string, body_str)
            
            headers["X-FB-ACCESS-KEY"] = self.api_key
            headers["X-FB-ACCESS-TIMESTAMP"] = timestamp
            headers["X-FB-ACCESS-SIGNATURE"] = signature

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data if data else None
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            raise

    # --- Public Endpoints ---

    def get_candlesticks(self, market_symbol: str, interval: str = "1h", limit: int = 100):
        """
        Get OHLCV candlestick data for a market.
        Intervals: 1m, 5m, 15m, 1h, 1d, 1M
        """
        path = f"/rest/v3/markets/{market_symbol}/candlesticks"
        params = {
            "interval": interval,
            "limit": limit
        }
        return self._request("GET", path, params=params, is_private=False)

    def get_ticker(self, market_symbol: str):
        """
        Get 24h ticker for a specific market.
        """
        path = f"/rest/v3/markets/{market_symbol}/ticker"
        return self._request("GET", path, is_private=False)

    def get_markets(self):
        """
        Get all active markets.
        """
        path = "/rest/v3/markets"
        return self._request("GET", path, is_private=False)

    # --- Private Endpoints ---

    def get_balances(self):
        """
        Get account balances.
        """
        path = "/rest/v3/accounts"
        return self._request("GET", path, is_private=True)

    def create_order(self, market_symbol: str, side: str, order_type: str, quantity: str = None, price: str = None):
        """
        Create a new order.
        side: 'BUY' or 'SELL'
        order_type: 'MARKET' or 'LIMIT'
        """
        path = "/rest/v3/orders"
        data = {
            "market_symbol": market_symbol,
            "side": side,
            "type": order_type
        }
        
        if quantity:
            data["quantity"] = quantity
        if price and order_type == 'LIMIT':
            data["price"] = price

        return self._request("POST", path, data=data, is_private=True)
