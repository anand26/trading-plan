import os
from dotenv import load_dotenv
import httpx

load_dotenv()

headers: dict[str, str] = {
    'APCA-API-KEY-ID': os.getenv('ALPACA_API_KEY') or '',
    'APCA-API-SECRET-KEY': os.getenv('ALPACA_SECRET_KEY') or ''
}

base_url = os.getenv('ALPACA_BASE_URL') or 'https://api.alpaca.markets'
r = httpx.get(base_url + '/v2/account', headers=headers)
account_data = r.json()

print('√ Alpaca connected!')
print(f'\nFull Account Response:')
import json
print(json.dumps(account_data, indent=2))
print(f'\n  Account Status: {account_data["status"]}')
print(f'\n  Cash Balance: {account_data["cash"]}')
print(f'  Buying Power: ${float(account_data["buying_power"]):,.2f}')