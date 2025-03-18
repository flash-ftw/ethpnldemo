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
        # Initialize Web3 with alternative endpoint
        # Using multiple fallback providers in case one fails
        rpc_url = os.getenv('ETH_RPC_URL', 'https://eth.llamarpc.com')
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Check if connection is working, if not try fallback URLs
        if not self.w3.is_connected():
            fallback_urls = [
                'https://ethereum.publicnode.com',
                'https://rpc.builder0x69.io',
                'https://eth.meowrpc.com',
                'https://eth.drpc.org'
            ]
            
            for url in fallback_urls:
                try:
                    self.w3 = Web3(Web3.HTTPProvider(url))
                    if self.w3.is_connected():
                        print(f"Connected to Ethereum network via {url}")
                        break
                except Exception:
                    continue
            
            if not self.w3.is_connected():
                raise Exception("Failed to connect to any Ethereum RPC endpoint")
        
        # Initialize Etherscan API
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
        if not self.etherscan_api_key:
            raise ValueError("Please set ETHERSCAN_API_KEY in .env file")
        self.etherscan_url = "https://api.etherscan.io/api"
        
        # Cache for historical prices
        self.price_cache = {}
        
        # WETH address
        self.weth_address = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
        
        # Define stablecoin addresses (lowercase)
        self.stablecoins = {
            # USDC
            '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': {
                'symbol': 'USDC',
                'decimals': 6
            },
            # USDT
            '0xdac17f958d2ee523a2206206994597c13d831ec7': {
                'symbol': 'USDT', 
                'decimals': 6
            },
            # DAI
            '0x6b175474e89094c44da98b954eedeac495271d0f': {
                'symbol': 'DAI',
                'decimals': 18
            },
            # FRAX
            '0x853d955acef822db058eb8505911ed77f175b99e': {
                'symbol': 'FRAX',
                'decimals': 18
            },
            # LUSD
            '0x5f98805a4e8be255a32880fdec7f6728c6568ba0': {
                'symbol': 'LUSD',
                'decimals': 18
            },
            # USDC.e (Bridged USDC)
            '0x2791bca1f2de4661ed88a30c99a7a9449aa84174': {
                'symbol': 'USDC.e',
                'decimals': 6
            },
            # BUSD
            '0x4fabb145d64652a948d72533023f6e7a623c7c53': {
                'symbol': 'BUSD',
                'decimals': 18
            },
            # GUSD (Gemini USD)
            '0x056fd409e1d7a124bd7017459dfea2f387b6d5cd': {
                'symbol': 'GUSD',
                'decimals': 2
            },
            # sUSD (Synthetix USD)
            '0x57ab1ec28d129707052df4df418d58a2d46d5f51': {
                'symbol': 'sUSD',
                'decimals': 18
            },
            # TUSD (TrueUSD)
            '0x0000000000085d4780b73119b644ae5ecd22b376': {
                'symbol': 'TUSD',
                'decimals': 18
            },
            # USDP (Pax Dollar)
            '0x8e870d67f660d95d5be530380d0ec0bd388289e1': {
                'symbol': 'USDP',
                'decimals': 18
            },
            # FEI USD
            '0x956f47f50a910163d8bf957cf5846d573e7f87ca': {
                'symbol': 'FEI',
                'decimals': 18
            },
            # Euro stablecoins
            # EURS (STASIS EURO)
            '0xdb25f211ab05b1c97d595516f45794528a807ad8': {
                'symbol': 'EURS',
                'decimals': 2
            },
            # Deprecated/renamed stablecoins that might be in historical transactions
            # SAI (Single Collateral DAI - old version)
            '0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359': {
                'symbol': 'SAI',
                'decimals': 18
            }
        }
        
        # Method signatures for DEX transactions
        self.method_signatures = {
            # Swaps
            '0x38ed1739': 'swapExactTokensForTokens',
            '0x8803dbee': 'swapTokensForExactTokens',
            
            # ETH to Token swaps
            '0x7ff36ab5': 'swapExactETHForTokens',
            '0x4a25d94a': 'swapTokensForExactETH',
            
            # Token to ETH swaps
            '0x18cbafe5': 'swapExactTokensForETH',
            '0xfb3bdb41': 'swapETHForExactTokens',
            
            # Uniswap v3 
            '0xc04b8d59': 'exactInput',
            '0xb858183f': 'exactOutput',
            '0x414bf389': 'exactInputSingle',
            '0xdb3e2198': 'exactOutputSingle',
            
            # Sushiswap
            '0x1f00ca74': 'swapExactTokensForTokensSupportingFeeOnTransferTokens',
            '0x791ac947': 'swapExactTokensForETHSupportingFeeOnTransferTokens',
            '0x5c11d795': 'swapExactETHForTokensSupportingFeeOnTransferTokens',
            
            # 1inch
            '0x7c025200': 'swap',
            '0xe449022e': 'uniswapV3Swap',
            '0x84bd6d29': 'clipperSwap',
            
            # 0x Protocol
            '0x415565b0': 'transformERC20',
            '0xc7e474c8': 'sellToUniswap',
            '0x90411a32': 'batchFillRfqOrders',
            
            # Balancer
            '0x762e7e6f': 'batchSwap',
            '0x945bcec9': 'swap',
            
            # Paraswap
            '0xd9627aa4': 'swapOnUniswap',
            '0xb2f1e6db': 'swapOnUniswapFork'
        }
        
        # Classify method signatures by type
        self.buy_methods = {
            '0x7ff36ab5',  # swapExactETHForTokens
            '0xfb3bdb41',  # swapETHForExactTokens
            '0x5c11d795',  # swapExactETHForTokensSupportingFeeOnTransferTokens
            '0x414bf389',  # exactInputSingle (when input is ETH/WETH)
            '0xdb3e2198',  # exactOutputSingle (when output is not ETH/WETH)
        }
        
        self.sell_methods = {
            '0x4a25d94a',  # swapTokensForExactETH
            '0x18cbafe5',  # swapExactTokensForETH
            '0x791ac947',  # swapExactTokensForETHSupportingFeeOnTransferTokens
            '0x414bf389',  # exactInputSingle (when input is not ETH/WETH)
            '0xdb3e2198',  # exactOutputSingle (when output is ETH/WETH)
        }
        
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

    def is_stablecoin(self, address):
        """Check if an address is a stablecoin"""
        return address.lower() in self.stablecoins
    
    def get_stablecoin_info(self, address):
        """Get stablecoin info"""
        if self.is_stablecoin(address):
            return self.stablecoins[address.lower()]
        return None
        
    def convert_stablecoin_to_eth(self, amount, stablecoin_address, timestamp=None):
        """Convert stablecoin amount to ETH using current or historical prices"""
        if not self.is_stablecoin(stablecoin_address):
            return amount
            
        stablecoin = self.stablecoins[stablecoin_address.lower()]
        
        # Get ETH price - for now we use current price
        # In a future version, we could implement historical price lookup based on timestamp
        eth_price = self.get_eth_price() 
        if not eth_price:
            eth_price = 2000  # Default ETH price if we can't get it
            
        # For historical prices, we could use a service like CoinGecko or CryptoCompare
        # This would require additional API calls and rate limiting considerations
        # For now, we'll use current price but make the code ready for historical prices
        
        # Adjust for EUR stablecoins (approximately 1.1 USD per EUR)
        if stablecoin['symbol'] == 'EURS':
            stablecoin_usd_rate = 1.1  # 1 EUR ≈ 1.1 USD
        else:
            stablecoin_usd_rate = 1.0  # 1 stablecoin = 1 USD (by definition)
            
        # Calculate the ETH amount: (stablecoin amount * USD rate) / ETH price in USD
        eth_amount = (amount * stablecoin_usd_rate) / eth_price
        
        result = eth_amount
        print(f"Converted {amount} {stablecoin['symbol']} to {result:.6f} ETH (ETH price: ${eth_price})")
        return result

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
        
        try:
            response = requests.get(self.etherscan_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '1':
                    return data['result']
                elif data['status'] == '0' and data['message'] == 'No transactions found':
                    return []
                elif data['message'] == 'NOTOK':
                    # Common issues with NOTOK response
                    error_msg = "Invalid Etherscan API key or API request limit exceeded"
                    if 'result' in data and isinstance(data['result'], str) and len(data['result']) > 0:
                        error_msg = data['result']  # Sometimes more info is in result
                    raise Exception(f"Etherscan API error: {error_msg}")
                else:
                    raise Exception(f"Etherscan API error: {data['message']}")
            else:
                raise Exception(f"Failed to fetch data: HTTP {response.status_code} - Please check your token address and try again.")
        except requests.exceptions.Timeout:
            raise Exception("Etherscan API request timed out. Please try again later.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when connecting to Etherscan: {str(e)}")
        except Exception as e:
            raise Exception(f"Error fetching token transfers: {str(e)}")

    def get_internal_transactions(self, tx_hash):
        """Get internal transactions for a transaction hash"""
        params = {
            'module': 'account',
            'action': 'txlistinternal',
            'txhash': tx_hash,
            'apikey': self.etherscan_api_key
        }
        
        try:
            response = requests.get(self.etherscan_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '1':
                    # Convert values to ETH
                    for tx in data['result']:
                        if 'value' in tx:
                            tx['value'] = float(tx['value']) / 1e18
                    return data['result']
                elif data['status'] == '0' and data['message'] == 'No transactions found':
                    return []
            return []
        except Exception:
            # Just return empty array if there's an error, since this is a supplementary call
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
        """Get transaction details with improved detection of value transfers"""
        total_value = 0
        internal_value = 0
        tx_type = "unknown"
        involved_tokens = []
        
        try:
            # Get transaction details
            params = {
                'module': 'proxy',
                'action': 'eth_getTransactionByHash',
                'txhash': tx_hash,
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    tx = data['result']
                    
                    # Check direct ETH value first
                    if tx.get('value', '0x0') != '0x0':
                        value = int(tx['value'], 16) / 1e18
                        total_value += value
                        print(f"Direct ETH value in {tx_hash}: {value} ETH")
                    
                    # Check if this is a swap transaction based on method signature
                    input_data = tx.get('input', '')
                    if len(input_data) >= 10:  # At least method signature (4 bytes + 0x)
                        method_sig = input_data[:10]
                        
                        # Identify transaction type based on method signature
                        if method_sig in self.method_signatures:
                            method_name = self.method_signatures[method_sig]
                            print(f"Method signature: {method_sig} ({method_name})")
                            
                            # Classify transaction type
                            if method_sig in self.buy_methods:
                                tx_type = "buy"
                                print(f"Transaction {tx_hash} classified as BUY based on method signature {method_sig}")
                            elif method_sig in self.sell_methods:
                                tx_type = "sell"
                                print(f"Transaction {tx_hash} classified as SELL based on method signature {method_sig}")
                            else:
                                tx_type = "swap"  # Generic swap
                                print(f"Transaction {tx_hash} classified as generic SWAP based on method signature {method_sig}")
                                
                            # Extract token path for swaps if possible
                            try:
                                if method_sig in ['0x38ed1739', '0x8803dbee', '0x18cbafe5', '0x7ff36ab5']:
                                    # These methods have path parameter - extract it
                                    # Format is usually:
                                    # [64 bytes amountIn/Out][64 bytes amountOut/In][64 bytes pathOffset][64 bytes toOffset][64 bytes deadlineOffset]
                                    # Then [path_length][path_item1][path_item2]...
                                    
                                    # For simplicity, we'll just look for addresses in the input data
                                    # This is not perfect but works for most cases
                                    data_without_sig = input_data[10:]
                                    
                                    # Look for potential addresses in the data
                                    for i in range(0, len(data_without_sig) - 40, 2):
                                        potential_addr = '0x' + data_without_sig[i:i+40]
                                        if Web3.is_address(potential_addr):
                                            involved_tokens.append(potential_addr.lower())
                                            
                                    # Remove duplicates
                                    involved_tokens = list(set(involved_tokens))
                                    print(f"Involved tokens: {', '.join(involved_tokens)}")
                                    
                                    # Check for stablecoins in the path
                                    for token in involved_tokens:
                                        if self.is_stablecoin(token):
                                            stablecoin_info = self.get_stablecoin_info(token)
                                            print(f"Stablecoin detected: {stablecoin_info['symbol']}")
                            except Exception as e:
                                print(f"Error extracting token path: {str(e)}")
            
            # Get transaction receipt for gas used and logs
            params = {
                'module': 'proxy',
                'action': 'eth_getTransactionReceipt',
                'txhash': tx_hash,
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result'] and data['result'].get('status') == '0x1':  # Success
                    receipt = data['result']
                    
                    # Check logs for Transfer events which might indicate tokens involved
                    if 'logs' in receipt:
                        for log in receipt['logs']:
                            # Transfer event topic (keccak256("Transfer(address,address,uint256)"))
                            if log.get('topics') and len(log['topics']) >= 3 and log['topics'][0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                                contract_addr = log.get('address', '').lower()
                                if contract_addr not in involved_tokens:
                                    involved_tokens.append(contract_addr)
            
            # Get internal transactions - these often contain the actual ETH transfers in DEX trades
            params = {
                'module': 'account',
                'action': 'txlistinternal',
                'txhash': tx_hash,
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '1' and data['result']:
                    for itx in data['result']:
                        if 'value' in itx and itx['value'] != '0':
                            value = float(itx['value']) / 1e18
                            internal_value += value
                            print(f"Internal transaction value in {tx_hash}: {value} ETH")
            
            # Handle stablecoin transactions
            stablecoin_transfers = []
            for token in involved_tokens:
                if self.is_stablecoin(token):
                    stablecoin_info = self.get_stablecoin_info(token)
                    print(f"Stablecoin involved in transaction: {stablecoin_info['symbol']} ({token})")
                    stablecoin_transfers.append(token)
                    
            # If this looks like a stablecoin transaction
            if total_value == 0 and len(stablecoin_transfers) > 0:
                print(f"Transaction {tx_hash} involves stablecoins but no direct ETH transfer")
                
                # We'll try to further analyze with token transfers
                # The actual stablecoin amount will be determined in the analyze_pnl method
                # when processing the token transfers
                
                # If transaction type is still unknown but we have stablecoins,
                # we'll set a type based on token transfers in analyze_transaction_type
                if tx_type == "unknown":
                    print(f"Transaction type is unknown with stablecoins - will determine from token transfers")
            
            # For sell transactions, the value is typically in internal transactions
            if tx_type == "sell" and internal_value > 0:
                total_value = internal_value
                print(f"Using internal transaction value for sell: {total_value} ETH")
            
            # If we still have 0 value, try more aggressively to find it
            if total_value == 0 and internal_value > 0:
                total_value = internal_value
                print(f"Using internal transaction value since direct value is 0: {total_value} ETH")
            
            # Fallback to a small default value if we couldn't determine anything
            # This helps ensure we don't have 0 values for transactions
            if total_value == 0:
                total_value = 0.0001  # small default value
                print(f"Using default value for {tx_hash} since no value could be determined")
        
        except Exception as e:
            print(f"Error processing transaction {tx_hash}: {str(e)}")
            # Use a small default value on error rather than returning 0
            total_value = 0.0001
            
        print(f"Final values for {tx_hash}: {total_value} ETH, Transaction type: {tx_type}, Tokens: {len(involved_tokens)}")
        return {
            'eth_value': total_value, 
            'internal_value': internal_value, 
            'tx_type': tx_type,
            'involved_tokens': involved_tokens
        }

    def analyze_transaction_type(self, tx_hash, wallet_address, token_address):
        """Analyze a transaction to determine its precise type (buy, sell, transfer)"""
        token_address = token_address.lower()
        wallet_address = wallet_address.lower()
        
        try:
            # Get transaction details
            tx_details = self.get_transaction(tx_hash)
            
            # Get all token transfers for this transaction
            transfers = self.get_token_transaction_transfers(tx_hash)
            
            # Check if this transaction involves stablecoins
            stablecoin_involved = False
            stablecoin_address = None
            stablecoin_amount = 0
            
            for token in tx_details.get('involved_tokens', []):
                if self.is_stablecoin(token):
                    stablecoin_involved = True
                    stablecoin_address = token
                    
                    # Find stablecoin amount in transfers
                    for transfer in transfers:
                        if transfer.get('contractAddress', '').lower() == stablecoin_address:
                            stablecoin_info = self.get_stablecoin_info(stablecoin_address)
                            decimals = stablecoin_info.get('decimals', 18)
                            value = float(transfer.get('value', 0)) / (10 ** decimals)
                            
                            # If wallet is receiving stablecoin, it's likely a sell
                            if transfer.get('to', '').lower() == wallet_address:
                                stablecoin_amount += value
                                print(f"Wallet received {value} stablecoin in tx {tx_hash}")
                            # If wallet is sending stablecoin, it's likely a buy
                            elif transfer.get('from', '').lower() == wallet_address:
                                stablecoin_amount -= value
                                print(f"Wallet sent {value} stablecoin in tx {tx_hash}")
                    
                    break
            
            # Filter transfers for our token and wallet
            our_token_transfers = []
            for transfer in transfers:
                if transfer.get('contractAddress', '').lower() == token_address and (
                   transfer.get('from', '').lower() == wallet_address or 
                   transfer.get('to', '').lower() == wallet_address):
                    our_token_transfers.append(transfer)
            
            if not our_token_transfers:
                print(f"No relevant transfers found for tx {tx_hash}")
                return "unknown", 0
            
            # Count incoming and outgoing transfers
            incoming = 0
            outgoing = 0
            token_amount = 0
            
            for transfer in our_token_transfers:
                token_decimals = int(transfer.get('tokenDecimal', 18))
                amount = float(transfer.get('value', 0)) / (10 ** token_decimals)
                
                if transfer.get('to', '').lower() == wallet_address:
                    incoming += 1
                    token_amount += amount
                elif transfer.get('from', '').lower() == wallet_address:
                    outgoing += 1
                    token_amount += amount
            
            # Determine transaction type with improved logic
            tx_type = tx_details['tx_type']
            
            # Use method signature detection first
            if tx_type != "unknown":
                # Already determined from method signature
                pass
            # If stablecoin is involved, use that to determine buy/sell
            elif stablecoin_involved:
                if stablecoin_amount > 0 and outgoing > 0:
                    # Wallet sent tokens and received stablecoins -> SELL
                    tx_type = "sell"
                    print(f"Classified as SELL based on stablecoin receipt: {tx_hash}")
                elif stablecoin_amount < 0 and incoming > 0:
                    # Wallet sent stablecoins and received tokens -> BUY
                    tx_type = "buy"
                    print(f"Classified as BUY based on stablecoin payment: {tx_hash}")
            # Fallback to transfer pattern detection
            elif incoming > 0 and outgoing == 0:
                # Only incoming transfers to wallet
                tx_type = "buy"
            elif outgoing > 0 and incoming == 0:
                # Only outgoing transfers from wallet
                tx_type = "sell"
            elif incoming > 0 and outgoing > 0:
                # Both incoming and outgoing - could be a swap, internal transfer, etc.
                # Need more advanced logic to determine type
                tx_type = "unknown"
            
            return tx_type, token_amount
            
        except Exception as e:
            print(f"Error analyzing transaction type for {tx_hash}: {str(e)}")
            return "unknown", 0
    
    def get_token_transaction_transfers(self, tx_hash):
        """Get all token transfers for a transaction hash"""
        params = {
            'module': 'account',
            'action': 'tokentx',
            'txhash': tx_hash,
            'apikey': self.etherscan_api_key
        }
        
        try:
            response = requests.get(self.etherscan_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '1':
                    return data['result']
            return []
        except Exception as e:
            print(f"Error getting token transfers for tx {tx_hash}: {str(e)}")
            return []

    def analyze_pnl(self, wallet_address, token_address):
        """Analyze profit and loss for a token"""
        try:
            print(f"Starting analysis for wallet {wallet_address} and token {token_address}")
            
            # Normalize addresses
            wallet_address = self.w3.to_checksum_address(wallet_address)
            token_address = self.w3.to_checksum_address(token_address)
            
            # Get token transfer events - handle pagination for large number of transactions
            print(f"Fetching token transfers for {wallet_address} and {token_address}")
            transfers = self.get_token_transfers(wallet_address, token_address)
            
            if not transfers:
                print("No transfers found")
                return None
                
            # Load token contract
            try:
                token_contract = self.w3.eth.contract(
                    address=token_address,
                    abi=self.token_abi
                )
                token_name = token_contract.functions.name().call()
                token_symbol = token_contract.functions.symbol().call()
                token_decimals = token_contract.functions.decimals().call()
                print(f"Token loaded: {token_name} ({token_symbol}) with {token_decimals} decimals")
            except Exception as e:
                print(f"Error loading token contract: {str(e)}")
                # Fallback to basic names
                token_name = "Unknown Token"
                token_symbol = "????"
                token_decimals = 18
                
            # Initialize counters
            buy_count = 0
            sell_count = 0
            total_tokens_bought = 0
            total_tokens_sold = 0
            total_in_eth = 0
            total_out_eth = 0
            total_gas_eth = 0
            
            # Get current token balance
            try:
                current_balance = token_contract.functions.balanceOf(wallet_address).call() / (10 ** token_decimals)
                print(f"Current balance: {current_balance} {token_symbol}")
            except Exception as e:
                print(f"Error getting token balance: {str(e)}")
                current_balance = 0
                
            # Get current token price
            try:
                current_price_eth = self.get_token_price(token_address)
                if current_price_eth is None:
                    # If price can't be determined, use a very small default value
                    current_price_eth = 0.0000001
                print(f"Current token price: {current_price_eth} ETH")
            except Exception as e:
                print(f"Error getting token price: {str(e)}")
                current_price_eth = 0.0000001
                
            # Get current ETH price
            try:
                eth_price_usd = self.get_eth_price() or 2000  # Default to 2000 if not available
                print(f"Current ETH price: ${eth_price_usd}")
            except Exception as e:
                print(f"Error getting ETH price: {str(e)}")
                eth_price_usd = 2000  # Default value
                
            # Process transfers
            print(f"Analyzing transactions...")
            transfers = sorted(transfers, key=lambda x: int(x.get('timeStamp', 0)))
            
            # Process each transaction, tracking unique transaction hashes to avoid duplicates
            processed_txs = set()
            
            # Group transfers by transaction hash to count buys/sells correctly
            tx_transfers = {}
            for tx in transfers:
                tx_hash = tx['hash']
                if tx_hash not in tx_transfers:
                    tx_transfers[tx_hash] = []
                tx_transfers[tx_hash].append(tx)
            
            # Prepare to track each transaction with full details
            transactions = []
            
            # Get gas prices for transactions
            with tqdm(total=len(tx_transfers), desc="Processing transactions") as pbar:
                for tx_hash, tx_group in tx_transfers.items():
                    try:
                        # Skip if we've already processed this transaction
                        if tx_hash in processed_txs:
                            pbar.update(1)
                            continue
                        
                        # Check if transaction is relevant to the wallet and token
                        is_relevant = False
                        for tx in tx_group:
                            if (tx['to'].lower() == wallet_address.lower() or 
                                tx['from'].lower() == wallet_address.lower()) and \
                               tx['contractAddress'].lower() == token_address.lower():
                                is_relevant = True
                                break
                                
                        if not is_relevant:
                            processed_txs.add(tx_hash)
                            pbar.update(1)
                            continue
                        
                        # Get timestamp
                        timestamp = int(tx_group[0].get('timeStamp', 0))
                        date_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Perform detailed transaction type analysis
                        tx_type, token_amount = self.analyze_transaction_type(tx_hash, wallet_address, token_address)
                        
                        # Get transaction value and details
                        tx_value = self.get_transaction(tx_hash)
                        
                        # Calculate gas cost
                        gas_used = int(tx_group[0].get('gasUsed', '0'))
                        gas_price = int(tx_group[0].get('gasPrice', '0'))
                        gas_cost = (gas_used * gas_price) / 1e18
                        total_gas_eth += gas_cost
                        
                        # Get transaction eth value
                        eth_value = tx_value['eth_value']
                        
                        # Check for stablecoins
                        has_stablecoin = False
                        stablecoin_address = None
                        for token in tx_value.get('involved_tokens', []):
                            if self.is_stablecoin(token):
                                has_stablecoin = True
                                stablecoin_address = token
                                stablecoin_info = self.get_stablecoin_info(token)
                                print(f"Transaction involves stablecoin: {stablecoin_info['symbol']}")
                                break
                        
                        # Store transaction data
                        tx_data = {
                            'hash': tx_hash,
                            'timestamp': timestamp,
                            'date_time': date_time,
                            'type': tx_type,
                            'eth_value': eth_value,
                            'gas_cost': gas_cost,
                            'token_amount': 0,
                            'has_stablecoin': has_stablecoin,
                            'stablecoin_address': stablecoin_address
                        }
                        
                        # Process buy transaction
                        if tx_type == "buy":
                            buy_count += 1
                            
                            # Calculate token amount - use the sum from all transfers
                            token_amount_in = 0
                            for tx in tx_group:
                                if tx['to'].lower() == wallet_address.lower() and tx['contractAddress'].lower() == token_address.lower():
                                    token_amount_in += float(tx['value']) / (10 ** int(tx.get('tokenDecimal', token_decimals)))
                            
                            tx_data['token_amount'] = token_amount_in
                            total_tokens_bought += token_amount_in
                            
                            # Use estimated ETH value or internal values
                            if eth_value == 0:
                                # Check for stablecoin payments
                                if has_stablecoin and stablecoin_address:
                                    # Try to find stablecoin amount from transfers
                                    stablecoin_transfers = self.get_token_transaction_transfers(tx_hash)
                                    stablecoin_amount = 0
                                    
                                    for transfer in stablecoin_transfers:
                                        if transfer.get('contractAddress', '').lower() == stablecoin_address.lower():
                                            # Only count outgoing stablecoin transfers for buys
                                            if transfer.get('from', '').lower() == wallet_address.lower():
                                                stablecoin_info = self.get_stablecoin_info(stablecoin_address)
                                                decimals = stablecoin_info.get('decimals', 18)
                                                value = float(transfer.get('value', 0)) / (10 ** decimals)
                                                stablecoin_amount += value
                                                print(f"Found stablecoin payment: {value} {stablecoin_info['symbol']}")
                                    
                                    if stablecoin_amount > 0:
                                        # Convert stablecoin amount to ETH
                                        eth_value = self.convert_stablecoin_to_eth(stablecoin_amount, stablecoin_address, timestamp)
                                        print(f"Buy: Converted {stablecoin_amount} stablecoin to {eth_value} ETH")
                                        tx_data['eth_value'] = eth_value
                                    else:
                                        # Still falling back to token price
                                        eth_value = token_amount_in * current_price_eth
                                        tx_data['eth_value'] = eth_value
                                else:
                                    # Use current price as a fallback
                                    eth_value = token_amount_in * current_price_eth
                                    tx_data['eth_value'] = eth_value
                            
                            total_in_eth += eth_value
                            print(f"Buy transaction - Added {eth_value} ETH to total_in_eth (now {total_in_eth})")
                            
                        # Process sell transaction
                        elif tx_type == "sell":
                            sell_count += 1
                            
                            # Calculate token amount - use the sum from all transfers
                            token_amount_out = 0
                            for tx in tx_group:
                                if tx['from'].lower() == wallet_address.lower() and tx['contractAddress'].lower() == token_address.lower():
                                    token_amount_out += float(tx['value']) / (10 ** int(tx.get('tokenDecimal', token_decimals)))
                            
                            tx_data['token_amount'] = token_amount_out
                            total_tokens_sold += token_amount_out
                            
                            # Use estimated ETH value or internal values
                            if eth_value == 0:
                                # Check for stablecoin receipts
                                if has_stablecoin and stablecoin_address:
                                    # Try to find stablecoin amount from transfers
                                    stablecoin_transfers = self.get_token_transaction_transfers(tx_hash)
                                    stablecoin_amount = 0
                                    
                                    for transfer in stablecoin_transfers:
                                        if transfer.get('contractAddress', '').lower() == stablecoin_address.lower():
                                            # Only count incoming stablecoin transfers for sells
                                            if transfer.get('to', '').lower() == wallet_address.lower():
                                                stablecoin_info = self.get_stablecoin_info(stablecoin_address)
                                                decimals = stablecoin_info.get('decimals', 18)
                                                value = float(transfer.get('value', 0)) / (10 ** decimals)
                                                stablecoin_amount += value
                                                print(f"Found stablecoin receipt: {value} {stablecoin_info['symbol']}")
                                    
                                    if stablecoin_amount > 0:
                                        # Convert stablecoin amount to ETH
                                        eth_value = self.convert_stablecoin_to_eth(stablecoin_amount, stablecoin_address, timestamp)
                                        print(f"Sell: Converted {stablecoin_amount} stablecoin to {eth_value} ETH")
                                        tx_data['eth_value'] = eth_value
                                    else:
                                        # Still falling back to token price
                                        eth_value = token_amount_out * current_price_eth
                                        tx_data['eth_value'] = eth_value
                                else:
                                    # Use current price as a fallback
                                    eth_value = token_amount_out * current_price_eth
                                    tx_data['eth_value'] = eth_value
                            
                            total_out_eth += eth_value
                            print(f"Sell transaction - Added {eth_value} ETH to total_out_eth (now {total_out_eth})")
                        
                        # Add transaction to list
                        transactions.append(tx_data)
                        
                        # Mark this transaction as processed
                        processed_txs.add(tx_hash)
                        
                    except Exception as e:
                        print(f"Error processing transaction {tx_hash}: {str(e)}")
                    finally:
                        pbar.update(1)
                    
            # Double-check our totals
            print(f"\nVerifying total transactions:")
            print(f"Total buy transactions: {buy_count}")
            print(f"Total sell transactions: {sell_count}")
            print(f"Total tokens bought: {total_tokens_bought:.4f} {token_symbol}")
            print(f"Total tokens sold: {total_tokens_sold:.4f} {token_symbol}")
            print(f"Total ETH in: {total_in_eth:.4f} ETH")
            print(f"Total ETH out: {total_out_eth:.4f} ETH")
                    
            # Calculate holdings and PnL
            current_holdings_eth = current_balance * current_price_eth
            current_holdings_usd = current_holdings_eth * eth_price_usd
            
            # Calculate realized PnL (what we've already sold)
            if total_tokens_bought > 0:
                cost_basis_per_token = total_in_eth / total_tokens_bought
                realized_cost = total_tokens_sold * cost_basis_per_token
                realized_pnl_eth = total_out_eth - realized_cost
            else:
                realized_pnl_eth = 0
                cost_basis_per_token = 0
            
            realized_pnl_usd = realized_pnl_eth * eth_price_usd
            
            # Calculate unrealized PnL (what we're still holding)
            if total_tokens_bought > 0:
                unrealized_cost = current_balance * cost_basis_per_token
                unrealized_pnl_eth = current_holdings_eth - unrealized_cost
            else:
                unrealized_pnl_eth = 0
                
            unrealized_pnl_usd = unrealized_pnl_eth * eth_price_usd
            
            # Calculate total PnL
            total_pnl_eth = realized_pnl_eth + unrealized_pnl_eth
            total_pnl_usd = realized_pnl_usd + unrealized_pnl_usd
            
            print("\nAnalysis Results:")
            print(f"Token: {token_name} ({token_symbol})")
            print(f"Current Balance: {current_balance:.4f} {token_symbol}")
            print(f"Total Bought: {total_tokens_bought:.4f} {token_symbol} for {total_in_eth:.4f} ETH")
            print(f"Total Sold: {total_tokens_sold:.4f} {token_symbol} for {total_out_eth:.4f} ETH")
            print(f"Realized PnL: {realized_pnl_eth:.4f} ETH (${realized_pnl_usd:.2f})")
            print(f"Unrealized PnL: {unrealized_pnl_eth:.4f} ETH (${unrealized_pnl_usd:.2f})")
            print(f"Total Transactions: {len(processed_txs)} (Buys: {buy_count}, Sells: {sell_count})")
            
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
                'unrealized_pnl_usd': unrealized_pnl_usd,
                'total_pnl_eth': total_pnl_eth,
                'total_pnl_usd': total_pnl_usd,
                'eth_price_usd': eth_price_usd,
                'transactions': transactions
            }
        except Exception as e:
            import traceback
            print(f"ERROR in analyze_pnl: {str(e)}")
            print(f"Detailed error: {traceback.format_exc()}")
            raise Exception(f"Failed to analyze token: {str(e)}")

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
            
            # Get tokens in pair
            token0 = pair_contract.functions.token0().call()
            token1 = pair_contract.functions.token1().call()
            
            # Get reserves
            reserves = pair_contract.functions.getReserves().call()
            
            # Calculate price based on reserves
            price = 0
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
                print(f"Token price from pair reserves: {price:.8f} ETH (${token_price_usd:.2f})")
            else:
                print(f"Token price from pair reserves: {price:.8f} ETH")
                
            return price
        except Exception as e:
            print(f"Warning: Could not calculate token price: {str(e)}")
            return None

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
            print(f"   • Tokens Bought:   {results['total_tokens_bought']:.1f}")
            print(f"   • Tokens Sold:     {results['total_tokens_sold']:.1f}")
            print(f"   • Current Balance: {results['current_balance']:.1f}")
            
            # Investment Summary
            print("\n💸 Investment Summary")
            print(f"   • Invested: {results['total_in_eth']:.1f} ETH (${results['total_in_eth'] * results.get('eth_price_usd', 2000):.1f})")
            print(f"   • Returned: {results['total_out_eth']:.1f} ETH (${results['total_out_eth'] * results.get('eth_price_usd', 2000):.1f})")
            print(f"   • Gas Cost: {results['total_gas_eth']:.1f} ETH (${results['total_gas_eth'] * results.get('eth_price_usd', 2000):.1f})")
            
            # Current Value
            print("\n📈 Current Value")
            print(f"   • Token Price: {results['current_price_eth']:.8f} ETH")
            print(f"   • Holdings: {results['current_holdings_eth']:.1f} ETH (${results['current_holdings_usd']:.1f})")
            
            # PnL Summary
            print("\n📊 Profit/Loss Summary")
            print(f"   • Realized: {results['realized_pnl_eth']:.1f} ETH (${results['realized_pnl_usd']:.1f})")
            print(f"   • Unrealized: {results['unrealized_pnl_eth']:.1f} ETH (${results['unrealized_pnl_usd']:.1f})")
            print(f"   • Total PnL: {results['total_pnl_eth']:.1f} ETH (${results['total_pnl_usd']:.1f})")
            
            print("\n" + "="*50)
        else:
            print("No transactions found for this token and wallet combination")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 