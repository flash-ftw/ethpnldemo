#!/usr/bin/env python3
import os
import json
import requests
from dotenv import load_dotenv
from web3 import Web3
from src.token_pnl_analyzer import TokenPnLAnalyzer

# Load environment variables
load_dotenv()

# Get API key
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
if not ETHERSCAN_API_KEY:
    raise ValueError("Please set ETHERSCAN_API_KEY in .env file")

class ValidationTests:
    def __init__(self):
        self.analyzer = TokenPnLAnalyzer()
        self.etherscan_url = "https://api.etherscan.io/api"
        
    def test_stablecoin_detection(self):
        """Test if stablecoins are correctly detected"""
        print("\n=== Testing Stablecoin Detection ===")
        
        # Known stablecoin addresses
        test_addresses = [
            ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'USDC'),
            ('0xdAC17F958D2ee523a2206206994597C13D831ec7', 'USDT'),
            ('0x6B175474E89094C44Da98b954EedeAC495271d0F', 'DAI'),
            ('0x853d955aCEf822Db058eb8505911ED77F175b99e', 'FRAX'),
            ('0x4Fabb145d64652a948d72533023f6E7A623C7C53', 'BUSD'),
            ('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', 'WETH')  # Not a stablecoin
        ]
        
        for address, symbol in test_addresses:
            is_stable = self.analyzer.is_stablecoin(address)
            if is_stable:
                info = self.analyzer.get_stablecoin_info(address)
                actual_symbol = info['symbol'] if info else 'Unknown'
                print(f"Address {address} detected as stablecoin: {is_stable}, symbol: {actual_symbol}")
                
                # Verify conversion
                amount = 100
                eth_value = self.analyzer.convert_stablecoin_to_eth(amount, address)
                print(f"Converted {amount} {actual_symbol} to {eth_value:.6f} ETH")
            else:
                print(f"Address {address} NOT detected as stablecoin (expected: {symbol != 'WETH'})")
                
        return True
                
    def test_buy_sell_detection(self, tx_hash):
        """Test if buy/sell transactions are correctly classified"""
        print(f"\n=== Testing Buy/Sell Detection for Transaction {tx_hash} ===")
        
        # Get transaction details from our analyzer
        tx_details = self.analyzer.get_transaction(tx_hash)
        
        # Get transaction details from Etherscan for comparison
        params = {
            'module': 'proxy',
            'action': 'eth_getTransactionByHash',
            'txhash': tx_hash,
            'apikey': ETHERSCAN_API_KEY
        }
        
        response = requests.get(self.etherscan_url, params=params)
        etherscan_tx = None
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and data['result']:
                etherscan_tx = data['result']
        
        print(f"Our analyzer classified as: {tx_details['tx_type']}")
        print(f"Value detected: {tx_details['eth_value']} ETH")
        print(f"Tokens involved: {len(tx_details['involved_tokens'])}")
        
        if etherscan_tx:
            print(f"Etherscan transaction value: {int(etherscan_tx['value'], 16) / 1e18} ETH")
            print(f"To: {etherscan_tx['to']}")
            
            # Check if input data contains a method signature
            input_data = etherscan_tx.get('input', '')
            if len(input_data) >= 10:
                method_sig = input_data[:10]
                if method_sig in self.analyzer.method_signatures:
                    print(f"Method signature: {method_sig} ({self.analyzer.method_signatures[method_sig]})")
                    print(f"In buy methods: {method_sig in self.analyzer.buy_methods}")
                    print(f"In sell methods: {method_sig in self.analyzer.sell_methods}")
                else:
                    print(f"Method signature: {method_sig} (unknown)")
        else:
            print("Could not fetch transaction details from Etherscan")
        
        return tx_details['tx_type']
        
    def test_stablecoin_transaction(self, wallet, token, tx_hash):
        """Test a specific transaction involving stablecoins"""
        print(f"\n=== Testing Stablecoin Transaction {tx_hash} ===")
        
        # Normalize addresses
        wallet = Web3.to_checksum_address(wallet)
        token = Web3.to_checksum_address(token)
        
        # Get transaction details
        tx_details = self.analyzer.get_transaction(tx_hash)
        
        # Check if any stablecoins are involved
        stablecoins_involved = []
        for address in tx_details['involved_tokens']:
            if self.analyzer.is_stablecoin(address):
                stablecoin_info = self.analyzer.get_stablecoin_info(address)
                stablecoins_involved.append(stablecoin_info['symbol'])
        
        print(f"Transaction type: {tx_details['tx_type']}")
        print(f"Stablecoins involved: {', '.join(stablecoins_involved) if stablecoins_involved else 'None'}")
        
        # Analyze transaction type with our analyzer
        tx_type, token_amount = self.analyzer.analyze_transaction_type(tx_hash, wallet, token)
        print(f"Analyzed transaction type: {tx_type}")
        print(f"Token amount: {token_amount}")
        
        # Get token transfers for this transaction
        transfers = self.analyzer.get_token_transaction_transfers(tx_hash)
        
        # Filter transfers for our token and wallet
        token_transfers = []
        stablecoin_transfers = []
        
        for transfer in transfers:
            contract_address = transfer.get('contractAddress', '').lower()
            from_address = transfer.get('from', '').lower()
            to_address = transfer.get('to', '').lower()
            
            # Check if this is a token transfer
            if contract_address == token.lower() and (from_address == wallet.lower() or to_address == wallet.lower()):
                token_decimals = int(transfer.get('tokenDecimal', 18))
                amount = float(transfer.get('value', 0)) / (10 ** token_decimals)
                direction = "IN" if to_address == wallet.lower() else "OUT"
                token_transfers.append((direction, amount))
                
            # Check if this is a stablecoin transfer
            elif self.analyzer.is_stablecoin(contract_address) and (from_address == wallet.lower() or to_address == wallet.lower()):
                stablecoin_info = self.analyzer.get_stablecoin_info(contract_address)
                decimals = stablecoin_info.get('decimals', 18)
                amount = float(transfer.get('value', 0)) / (10 ** decimals)
                direction = "IN" if to_address == wallet.lower() else "OUT"
                stablecoin_transfers.append((direction, amount, stablecoin_info['symbol']))
        
        print("\nToken transfers in this transaction:")
        for direction, amount in token_transfers:
            print(f"  {direction}: {amount}")
            
        print("\nStablecoin transfers in this transaction:")
        for direction, amount, symbol in stablecoin_transfers:
            print(f"  {direction}: {amount} {symbol}")
            
        # Validate the transaction type based on the transfers
        expected_type = "unknown"
        if token_transfers:
            # If wallet is receiving tokens and sending stablecoins, it's a buy
            if any(d == "IN" for d, _ in token_transfers) and any(d == "OUT" and s in ['USDC', 'USDT', 'DAI'] for d, _, s in stablecoin_transfers):
                expected_type = "buy"
            # If wallet is sending tokens and receiving stablecoins, it's a sell
            elif any(d == "OUT" for d, _ in token_transfers) and any(d == "IN" and s in ['USDC', 'USDT', 'DAI'] for d, _, s in stablecoin_transfers):
                expected_type = "sell"
        
        print(f"\nExpected transaction type based on transfers: {expected_type}")
        print(f"Analyzer transaction type: {tx_type}")
        print(f"Match: {expected_type == tx_type or (expected_type == 'unknown' and tx_type in ['buy', 'sell'])}")
        
        return tx_type
        
    def verify_token_balances(self, wallet, token):
        """Verify that calculated token balances match Etherscan"""
        print(f"\n=== Verifying Token Balance for {wallet} ===")
        
        # Normalize addresses
        wallet = Web3.to_checksum_address(wallet)
        token = Web3.to_checksum_address(token)
        
        # Get token info
        try:
            token_contract = self.analyzer.w3.eth.contract(
                address=token,
                abi=self.analyzer.token_abi
            )
            token_name = token_contract.functions.name().call()
            token_symbol = token_contract.functions.symbol().call()
            token_decimals = token_contract.functions.decimals().call()
            print(f"Token: {token_name} ({token_symbol}) with {token_decimals} decimals")
            
            # Get current balance from blockchain
            current_balance = token_contract.functions.balanceOf(wallet).call() / (10 ** token_decimals)
            print(f"Current balance from blockchain: {current_balance} {token_symbol}")
            
            # Get balance from Etherscan API
            params = {
                'module': 'account',
                'action': 'tokenbalance',
                'contractaddress': token,
                'address': wallet,
                'tag': 'latest',
                'apikey': ETHERSCAN_API_KEY
            }
            
            response = requests.get(self.etherscan_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '1':
                    etherscan_balance = int(data['result']) / (10 ** token_decimals)
                    print(f"Current balance from Etherscan: {etherscan_balance} {token_symbol}")
                    
                    print(f"Match: {abs(current_balance - etherscan_balance) < 0.0001}")
                else:
                    print(f"Error from Etherscan: {data['message']}")
            else:
                print(f"Error connecting to Etherscan: {response.status_code}")
                
            return current_balance
        except Exception as e:
            print(f"Error verifying token balance: {str(e)}")
            return None
    
    def run_validation_tests(self):
        """Run all validation tests"""
        print("Starting validation tests...")
        
        # Test 1: Stablecoin detection
        self.test_stablecoin_detection()
        
        # Test 2: Buy/sell detection for specific transactions
        # Buy transaction with ETH
        self.test_buy_sell_detection("0x29d148b8e3a0c095131ea2e9b3d80f2c8f7c4d4e7f9af5f730929cdae4267c73")
        
        # Sell transaction to ETH
        self.test_buy_sell_detection("0x621e7dcfd3a3e2f2f796e68eb8df5acb926acb8fffb16e6ec6d94bc2dc4582c1")
        
        # Swap transaction
        self.test_buy_sell_detection("0x50e34b0ab48b1c8cab701cd6fcb8032792f11734cdf066fd5f86972fc8a58bf2")
        
        # Test 3: Stablecoin transaction tests
        # USDC buy
        self.test_stablecoin_transaction(
            "0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296",
            "0x514910771AF9Ca656af840dff83E8264EcF986CA",  # LINK
            "0x3ca5db544a6c20e0c923369ef5f4fa8fae494a39ee787714e5fcc87443aa9397"
        )
        
        # USDT sell
        self.test_stablecoin_transaction(
            "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
            "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",  # UNI
            "0x91be607125faee3ce70f1af7a2e299244e5e5087ce24e52663e5cf99da3dfe1c"
        )
        
        # Test 4: Verify token balances
        self.verify_token_balances("0x87851CbCDa813b3C2ec1411c3e4b7f2d3121aBf8", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")  # WETH
        self.verify_token_balances("0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296", "0x514910771AF9Ca656af840dff83E8264EcF986CA")  # LINK
        
        print("\nAll validation tests completed.")

if __name__ == "__main__":
    tests = ValidationTests()
    tests.run_validation_tests() 