import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from web3 import Web3
import pandas as pd
import json
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import time

# Load environment variables
load_dotenv()

class TokenPnLAnalyzer:
    def __init__(self):
        # Initialize Web3 with Infura endpoint
        self.w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/eth'))
        
        # Initialize Etherscan API
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
        if not self.etherscan_api_key:
            raise ValueError("Please set ETHERSCAN_API_KEY in .env file")
        self.etherscan_url = "https://api.etherscan.io/api"
        
        # Cache for historical prices
        self.price_cache = {}
        
        # WETH address
        self.weth_address = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
        
        # Uniswap V2 Router ABI
        self.router_abi = [
            {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},
            {"inputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint256","name":"amountInMax","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapTokensForExactTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},
            {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"},
            {"inputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsIn","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"factory","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}
        ]
        
        # Uniswap V2 Factory ABI
        self.factory_abi = [
            {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"}],"name":"getPair","outputs":[{"internalType":"address","name":"pair","type":"address"}],"stateMutability":"view","type":"function"}
        ]
        
        # Uniswap V2 Pair ABI
        self.pair_abi = [
            {"constant":True,"inputs":[],"name":"token0","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},
            {"constant":True,"inputs":[],"name":"token1","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},
            {"constant":True,"inputs":[],"name":"getReserves","outputs":[{"name":"reserve0","type":"uint112"},{"name":"reserve1","type":"uint112"},{"name":"blockTimestampLast","type":"uint32"}],"payable":False,"stateMutability":"view","type":"function"}
        ]
        
        # Uniswap V2 Router address
        self.router_address = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'
        
        # Initialize router contract
        self.router_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(self.router_address),
            abi=self.router_abi
        )
        
        # Get factory address from router
        self.factory_address = self.router_contract.functions.factory().call()
        
        # Initialize factory contract
        self.factory_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(self.factory_address),
            abi=self.factory_abi
        )

        # Basic ERC20 ABI for token interactions
        self.token_abi = [
            {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"},
            {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},
            {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},
            {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}
        ]

    def get_token_transfers(self, address, token_address):
        """Fetch token transfers for the given address"""
        params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': token_address,
            'address': address,
            'sort': 'asc',
            'apikey': self.etherscan_api_key
        }
        
        response = requests.get(self.etherscan_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '1':
                return data['result']
            else:
                raise Exception(f"Etherscan API error: {data['message']}")
        else:
            raise Exception(f"Failed to fetch data: {response.status_code}")

    def get_internal_transactions(self, tx_hash):
        """Get internal transactions for a transaction hash"""
        params = {
            'module': 'account',
            'action': 'txlistinternal',
            'txhash': tx_hash,
            'apikey': self.etherscan_api_key
        }
        
        response = requests.get(self.etherscan_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '1':
                # Convert values to ETH
                for tx in data['result']:
                    if 'value' in tx:
                        tx['value'] = float(tx['value']) / 1e18
                return data['result']
        return []

    def get_transaction_receipt(self, tx_hash):
        """Get transaction receipt details"""
        params = {
            'module': 'proxy',
            'action': 'eth_getTransactionReceipt',
            'txhash': tx_hash,
            'apikey': self.etherscan_api_key
        }
        
        response = requests.get(self.etherscan_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and data['result']:
                return data['result']
        return None

    def get_transaction_trace(self, tx_hash):
        """Get transaction trace details"""
        params = {
            'module': 'account',
            'action': 'txlistinternal',
            'txhash': tx_hash,
            'apikey': self.etherscan_api_key
        }
        
        response = requests.get(self.etherscan_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '1' and data['result']:
                total_eth = 0
                for trace in data['result']:
                    total_eth += float(trace['value']) / 1e18
                return total_eth
        return 0

    def get_transaction(self, tx_hash):
        """Get transaction details"""
        total_value = 0
        
        # Get transaction details
        params = {
            'module': 'proxy',
            'action': 'eth_getTransactionByHash',
            'txhash': tx_hash,
            'apikey': self.etherscan_api_key
        }
        
        response = requests.get(self.etherscan_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and data['result']:
                tx = data['result']
                
                # Check if this is a swap transaction (input data starts with swap method signature)
                input_data = tx.get('input', '')
                if input_data.startswith('0x38ed1739'):  # swapExactTokensForTokens
                    # Decode the input data
                    try:
                        # Remove method signature
                        data = input_data[10:]
                        # Get amountIn (first 64 chars after method sig)
                        amount_in = int(data[:64], 16) / 1e18
                        total_value = amount_in
                        print(f"Found swap input amount in {tx_hash}: {amount_in} ETH")
                    except Exception as e:
                        print(f"Error decoding input data: {str(e)}")
                
                # Also check direct ETH value
                if tx.get('value', '0x0') != '0x0':
                    value = int(tx['value'], 16) / 1e18
                    total_value += value
                    print(f"Direct ETH value in {tx_hash}: {value} ETH")
        
        # Get internal transactions
        params = {
            'module': 'account',
            'action': 'txlistinternal',
            'txhash': tx_hash,
            'apikey': self.etherscan_api_key
        }
        
        response = requests.get(self.etherscan_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '1' and data['result']:
                for tx in data['result']:
                    if 'value' in tx and tx['value'] != '0':
                        value = float(tx['value']) / 1e18
                        total_value += value
                        print(f"Internal transaction value in {tx_hash}: {value} ETH")
        
        print(f"Total value for {tx_hash}: {total_value} ETH")
        return {'eth_value': total_value, 'internal_value': 0}

    def get_eth_price(self):
        """Get current ETH price in USD"""
        params = {
            'module': 'stats',
            'action': 'ethprice',
            'apikey': self.etherscan_api_key
        }
        response = requests.get(self.etherscan_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '1':
                return float(data['result']['ethusd'])
        return None

    def get_token_price_from_dexscreener(self, token_address):
        """Get token price from DexScreener API"""
        try:
            # DexScreener API endpoint
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('pairs') and len(data['pairs']) > 0:
                    # Get the first WETH pair
                    weth_pairs = [p for p in data['pairs'] if 
                                p.get('quoteToken', {}).get('symbol', '').upper() == 'WETH' and 
                                p.get('chainId') == 'ethereum']
                    
                    if weth_pairs:
                        pair = weth_pairs[0]  # Use the first WETH pair
                        price_usd = float(pair['priceUsd'])
                        price_eth = float(pair.get('priceNative', 0))
                        print(f"Token price in USD: ${price_usd:.4f}")
                        return price_eth
                    
                    # If no WETH pair, use the first pair and convert through USD
                    pair = data['pairs'][0]
                    if pair.get('priceUsd'):
                        price_usd = float(pair['priceUsd'])
                        eth_price_usd = self.get_eth_price()
                        if eth_price_usd:
                            price_eth = price_usd / eth_price_usd
                            print(f"Token price in USD: ${price_usd:.4f}")
                            return price_eth
            
            return None
        except Exception as e:
            print(f"Warning: Could not fetch price from DexScreener: {str(e)}")
            return None

    def get_token_price(self, token_address):
        """Get current token price in ETH"""
        try:
            # If token is WETH, price is 1 ETH
            if token_address.lower() == self.weth_address.lower():
                return 1.0

            # Try DexScreener first
            dexscreener_price = self.get_token_price_from_dexscreener(token_address)
            if dexscreener_price:
                return dexscreener_price

            # Fallback to DEX price if DexScreener fails
            token_contract = self.w3.eth.contract(address=token_address, abi=self.token_abi)
            token_decimals = token_contract.functions.decimals().call()

            # Get WETH pair address
            pair_address = self.factory_contract.functions.getPair(token_address, self.weth_address).call()
            
            if pair_address == '0x0000000000000000000000000000000000000000':
                print("Warning: No WETH pair found for this token")
                return None

            # Get pair contract
            pair_contract = self.w3.eth.contract(address=pair_address, abi=self.pair_abi)
            
            # Get reserves
            reserves = pair_contract.functions.getReserves().call()
            token0 = pair_contract.functions.token0().call()
            
            # Calculate price based on reserves
            if token0.lower() == token_address.lower():
                # Token is token0, price = reserve1/reserve0
                price = (reserves[1] / 1e18) / (reserves[0] / (10 ** token_decimals))
            else:
                # Token is token1, price = reserve0/reserve1
                price = (reserves[0] / 1e18) / (reserves[1] / (10 ** token_decimals))

            # Get current ETH price in USD
            eth_price_usd = self.get_eth_price()
            if eth_price_usd:
                token_price_usd = price * eth_price_usd
                print(f"Token price in USD: ${token_price_usd:.4f}")

            return price

        except Exception as e:
            print(f"Warning: Could not fetch token price: {str(e)}")
            return None

    def get_token_info(self, token_address):
        """Get token information"""
        try:
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token_address),
                abi=self.token_abi
            )
            
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            
            return {
                'name': name,
                'symbol': symbol,
                'decimals': decimals
            }
        except Exception as e:
            print(f"Warning: Could not get token info: {str(e)}")
            return None

    def get_historical_eth_price(self, timestamp):
        """Get historical ETH price for a specific timestamp"""
        try:
            # Using CoinGecko API for historical prices
            date = datetime.fromtimestamp(timestamp).strftime('%d-%m-%Y')
            url = f"https://api.coingecko.com/api/v3/coins/ethereum/history?date={date}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                return data['market_data']['current_price']['usd']
        except Exception as e:
            print(f"Warning: Could not get historical ETH price: {str(e)}")
        return None

    def get_token_address_from_pair(self, token_pair):
        """Get token address from token pair"""
        try:
            # Split the pair
            base_token, quote_token = token_pair.split('/')
            
            # Get token address from pair
            pair_address = self.router_contract.functions.getPair(
                self.w3.to_checksum_address(base_token),
                self.w3.to_checksum_address(self.weth_address)
            ).call()
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                # Try with quote token if base token fails
                pair_address = self.router_contract.functions.getPair(
                    self.w3.to_checksum_address(quote_token),
                    self.w3.to_checksum_address(self.weth_address)
                ).call()
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                print("Error: Could not find token pair")
                return None
            
            return pair_address
            
        except Exception as e:
            print(f"Error getting token address: {str(e)}")
            return None

    def get_token_from_pair(self, pair_address):
        """Get token address from pair address"""
        try:
            pair_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(pair_address),
                abi=self.pair_abi
            )
            token0 = pair_contract.functions.token0().call()
            token1 = pair_contract.functions.token1().call()
            
            # Get token info for both tokens
            token0_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token0),
                abi=self.token_abi
            )
            token1_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token1),
                abi=self.token_abi
            )
            
            # Get symbols
            token0_symbol = token0_contract.functions.symbol().call()
            token1_symbol = token1_contract.functions.symbol().call()
            
            # Return the non-WETH token
            if token0_symbol == 'WETH':
                return token1
            elif token1_symbol == 'WETH':
                return token0
            else:
                return token0  # Default to token0 if neither is WETH
                
        except Exception as e:
            print(f"Error getting token from pair: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_historical_token_price(self, token_address, timestamp):
        """Get historical token price with caching"""
        cache_key = f"{token_address}_{timestamp}"
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        try:
            # First try DexScreener historical data
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('pairs') and len(data['pairs']) > 0:
                    weth_pairs = [p for p in data['pairs'] if 
                                p.get('quoteToken', {}).get('symbol', '').upper() == 'WETH' and 
                                p.get('chainId') == 'ethereum']
                    
                    if weth_pairs:
                        pair = weth_pairs[0]
                        price_history = pair.get('priceHistory', [])
                        if price_history:
                            closest_price = min(price_history, 
                                             key=lambda x: abs(x['timestamp'] - timestamp))
                            price = float(closest_price['price'])
                            self.price_cache[cache_key] = price
                            return price
            
            # Fallback to reserves calculation
            price = self._calculate_price_from_reserves(token_address)
            if price:
                self.price_cache[cache_key] = price
                return price
            
            return None
        except Exception:
            return None

    def _calculate_price_from_reserves(self, token_address):
        """Helper method to calculate price from reserves"""
        try:
            token_contract = self.w3.eth.contract(address=token_address, abi=self.token_abi)
            token_decimals = token_contract.functions.decimals().call()
            pair_address = self.factory_contract.functions.getPair(token_address, self.weth_address).call()
            
            if pair_address != '0x0000000000000000000000000000000000000000':
                pair_contract = self.w3.eth.contract(address=pair_address, abi=self.pair_abi)
                reserves = pair_contract.functions.getReserves().call()
                token0 = pair_contract.functions.token0().call()
                
                if token0.lower() == token_address.lower():
                    return (reserves[1] / 1e18) / (reserves[0] / (10 ** token_decimals))
                else:
                    return (reserves[0] / 1e18) / (reserves[1] / (10 ** token_decimals))
            return None
        except Exception:
            return None

    def process_transfer(self, transfer, wallet_address, token_address):
        """Process a single transfer with all calculations"""
        try:
            # Get transaction details
            tx_details = self.get_transaction(transfer['hash'])
            tx_value = tx_details['eth_value']
            
            # Calculate gas cost
            gas_used = int(transfer['gasUsed'])
            gas_price = int(transfer['gasPrice'])
            gas_cost_eth = (gas_used * gas_price) / 1e18
            
            # Convert token amount
            token_amount = float(transfer['value']) / (10 ** int(transfer['tokenDecimal']))
            
            # Get historical price
            timestamp = int(transfer['timeStamp'])
            historical_price = self.get_historical_token_price(token_address, timestamp)
            
            # Calculate values
            eth_value = token_amount * historical_price if historical_price else tx_value
            is_buy = transfer['to'].lower() == wallet_address.lower()
            
            return {
                'is_buy': is_buy,
                'token_amount': token_amount,
                'eth_value': eth_value,
                'gas_cost': gas_cost_eth,
                'hash': transfer['hash']  # Add hash for debugging
            }
        except Exception as e:
            print(f"Warning: Failed to process transfer {transfer.get('hash', 'unknown')}: {str(e)}")
            return None

    def analyze_pnl(self, wallet_address, token_address):
        """Analyze PnL for a given token"""
        # Get token transfers
        transfers = self.get_token_transfers(wallet_address, token_address)
        if not transfers:
            return None

        # Initialize variables
        total_tokens_bought = 0
        total_tokens_sold = 0
        total_in_eth = 0
        total_out_eth = 0
        total_gas_eth = 0
        buy_count = 0
        sell_count = 0
        gas_price = self.get_eth_price()

        print("\nAnalyzing transactions...")
        # Process each transfer with progress bar
        for transfer in tqdm(transfers, desc="Processing transactions", unit="tx"):
            # Get transaction details including ETH value
            tx_details = self.get_transaction(transfer['hash'])
            tx_value = tx_details['eth_value']
            
            # Calculate gas cost
            gas_used = int(transfer['gasUsed'])
            gas_price = int(transfer['gasPrice'])
            gas_cost_eth = (gas_used * gas_price) / 1e18
            total_gas_eth += gas_cost_eth

            # Convert token amount to decimal
            token_amount = float(transfer['value']) / (10 ** int(transfer['tokenDecimal']))
            
            # Get historical token price at transaction time
            timestamp = int(transfer['timeStamp'])
            historical_price = self.get_historical_token_price(token_address, timestamp)
            
            # If we have historical price, use it to calculate ETH value
            if historical_price:
                eth_value = token_amount * historical_price
                if transfer['to'].lower() == wallet_address.lower():
                    total_in_eth += eth_value
                else:
                    total_out_eth += eth_value

            # Determine if it's a buy or sell
            if transfer['to'].lower() == wallet_address.lower():
                print(f"Buy transaction - Added {eth_value if historical_price else tx_value} ETH to total_in_eth (now {total_in_eth})")
                total_tokens_bought += token_amount
                buy_count += 1
            else:
                print(f"Sell transaction - Added {eth_value if historical_price else tx_value} ETH to total_out_eth (now {total_out_eth})")
                total_tokens_sold += token_amount
                sell_count += 1

        # Get current token balance and price
        token_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=self.token_abi
        )
        current_balance = total_tokens_bought - total_tokens_sold
        current_price_eth = self.get_token_price(token_address)
        
        # Get token info
        token_symbol = token_contract.functions.symbol().call()
        token_name = token_contract.functions.name().call()
        
        # Calculate current holdings value
        current_holdings_eth = current_balance * current_price_eth if current_price_eth else 0
        
        # Get ETH price for USD conversion
        eth_price_usd = self.get_eth_price()
        
        # Calculate PnL
        realized_pnl_eth = total_out_eth - total_in_eth - total_gas_eth
        unrealized_pnl_eth = current_holdings_eth
        
        # Convert to USD
        if eth_price_usd:
            realized_pnl_usd = realized_pnl_eth * eth_price_usd
            unrealized_pnl_usd = unrealized_pnl_eth * eth_price_usd
            current_holdings_usd = current_holdings_eth * eth_price_usd
        else:
            realized_pnl_usd = 0
            unrealized_pnl_usd = 0
            current_holdings_usd = 0

        return {
            'token_name': token_name,
            'token_symbol': token_symbol,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'total_tokens_bought': total_tokens_bought,
            'total_tokens_sold': total_tokens_sold,
            'current_balance': current_balance,
            'total_in_eth': total_in_eth,
            'total_out_eth': total_out_eth,
            'total_gas_eth': total_gas_eth,
            'current_price_eth': current_price_eth,
            'current_holdings_eth': current_holdings_eth,
            'current_holdings_usd': current_holdings_usd,
            'realized_pnl_eth': realized_pnl_eth,
            'realized_pnl_usd': realized_pnl_usd,
            'unrealized_pnl_eth': unrealized_pnl_eth,
            'unrealized_pnl_usd': unrealized_pnl_usd
        }

def main():
    """Main function"""
    try:
        # Get user input
        print("Enter token contract address or pair address:")
        token_input = input().strip()
        
        print("Enter trader wallet address:")
        wallet_address = input().strip()
        
        # Validate wallet address
        if not Web3.is_address(wallet_address):
            print("Error: Invalid wallet address format")
            return
            
        # Initialize analyzer
        analyzer = TokenPnLAnalyzer()
        
        # Check if input is a pair address
        if '/' in token_input:
            token_address = analyzer.get_token_address_from_pair(token_input)
        else:
            token_address = token_input
            
        if not token_address:
            print("Error: Could not determine token address")
            return
            
        # Analyze PnL
        results = analyzer.analyze_pnl(wallet_address, token_address)
        if results:
            # Token Info Section
            print("\n" + "="*50)
            print(f"📊 {results['token_name']} ({results['token_symbol']}) Analysis")
            print("="*50)
            
            # Transaction Overview
            print("\n🔄 Transaction Overview")
            print(f"   • Buy Transactions:  {results['buy_count']}")
            print(f"   • Sell Transactions: {results['sell_count']}")
            
            # Token Position
            print("\n💰 Token Position")
            print(f"   • Tokens Bought:   {results['total_tokens_bought']:,.2f}")
            print(f"   • Tokens Sold:     {results['total_tokens_sold']:,.2f}")
            print(f"   • Current Balance: {results['current_balance']:,.2f}")
            
            # Investment Summary
            print("\n💸 Investment Summary")
            print(f"   • Total Invested: {results['total_in_eth']:.4f} ETH")
            print(f"   • Total Returned: {results['total_out_eth']:.4f} ETH")
            print(f"   • Gas Costs:      {results['total_gas_eth']:.4f} ETH")
            
            # Current Value
            print("\n📈 Current Value")
            print(f"   • Token Price:    {results['current_price_eth']:.8f} ETH")
            print(f"   • Holdings Value: {results['current_holdings_eth']:.4f} ETH (${results['current_holdings_usd']:,.2f})")
            
            # PnL Summary
            print("\n📊 Profit/Loss Summary")
            print("   Realized:")
            print(f"   • ETH: {results['realized_pnl_eth']:.4f}")
            print(f"   • USD: ${results['realized_pnl_usd']:,.2f}")
            print("   Unrealized:")
            print(f"   • ETH: {results['unrealized_pnl_eth']:.4f}")
            print(f"   • USD: ${results['unrealized_pnl_usd']:,.2f}")
            
            # Total PnL
            total_pnl_eth = results['realized_pnl_eth'] + results['unrealized_pnl_eth']
            total_pnl_usd = results['realized_pnl_usd'] + results['unrealized_pnl_usd']
            print("\n💫 Total Position PnL")
            print(f"   • ETH: {total_pnl_eth:.4f}")
            print(f"   • USD: ${total_pnl_usd:,.2f}")
            
            print("\n" + "="*50)
        else:
            print("No transactions found for this token and wallet combination")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 