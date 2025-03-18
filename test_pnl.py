import requests
from web3 import Web3
from datetime import datetime

def verify_transactions(address, token_address, etherscan_api_key):
    """Verify transactions using Etherscan API"""
    base_url = "https://api.etherscan.io/api"
    
    # Get token transfers
    params = {
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': token_address,
        'address': address,
        'sort': 'asc',
        'apikey': etherscan_api_key
    }
    
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == '1':
            transfers = data['result']
            
            # Print raw transaction data for verification
            print("\n=== Raw Transaction Data ===")
            for tx in transfers:
                print(f"\nTransaction Hash: {tx['hash']}")
                print(f"Timestamp: {datetime.fromtimestamp(int(tx['timeStamp']))}")
                print(f"From: {tx['from']}")
                print(f"To: {tx['to']}")
                print(f"Value: {tx['value']}")
                print(f"Token Decimals: {tx['tokenDecimal']}")
                print(f"Gas Used: {tx['gasUsed']}")
                print(f"Gas Price: {tx['gasPrice']}")
                print(f"Block Number: {tx['blockNumber']}")
                
            return transfers
    return None

if __name__ == "__main__":
    # Test addresses
    address = "0x87851CbCDa813b3C2ec1411c3e4b7f2d3121aBf8"
    token_address = "0x69846130091C734Ad4Aa88DDC5E5646A301E6bE4"
    
    # Get API key from environment
    import os
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv('ETHERSCAN_API_KEY')
    
    if not api_key:
        print("Error: Please set ETHERSCAN_API_KEY in .env file")
    else:
        verify_transactions(address, token_address, api_key) 