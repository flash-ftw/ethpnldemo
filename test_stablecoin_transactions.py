#!/usr/bin/env python3
import os
import json
import time
import requests
from dotenv import load_dotenv
from web3 import Web3
from src.token_pnl_analyzer import TokenPnLAnalyzer

# Load environment variables
load_dotenv()

# Initialize analyzer
analyzer = TokenPnLAnalyzer()

# Etherscan API
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
if not ETHERSCAN_API_KEY:
    raise ValueError("Please set ETHERSCAN_API_KEY in .env file")

ETHERSCAN_API_URL = "https://api.etherscan.io/api"

# Create results directory
RESULTS_DIR = "test_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Known stablecoin transactions for testing
TEST_TRANSACTIONS = [
    # Buy token with USDC
    {
        'hash': '0x3ca5db544a6c20e0c923369ef5f4fa8fae494a39ee787714e5fcc87443aa9397',
        'wallet': '0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296',
        'token': '0x514910771AF9Ca656af840dff83E8264EcF986CA',  # LINK
        'expected_type': 'buy',
        'expected_stablecoin': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',  # USDC
        'description': 'Buy LINK with USDC'
    },
    # Sell token for USDT
    {
        'hash': '0x91be607125faee3ce70f1af7a2e299244e5e5087ce24e52663e5cf99da3dfe1c',
        'wallet': '0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503',
        'token': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',  # UNI
        'expected_type': 'sell',
        'expected_stablecoin': '0xdac17f958d2ee523a2206206994597c13d831ec7',  # USDT
        'description': 'Sell UNI for USDT'
    },
    # Buy token with DAI
    {
        'hash': '0x5dd95a9f4a5836af58662f8cc227a32d392c054e2186a6e8320b5a8533ce0d54',
        'wallet': '0x4d944a25Bc871D6C6EE08f0C12726b89e101f64B',
        'token': '0x6b175474e89094c44da98b954eedeac495271d0f',  # DAI (token is also stablecoin)
        'expected_type': 'buy',
        'expected_stablecoin': '0x6b175474e89094c44da98b954eedeac495271d0f',  # DAI
        'description': 'Buy DAI with ETH (special case where token is stablecoin)'
    },
    # Complex stablecoin swap
    {
        'hash': '0xc2fa667abc4bdd7e2ce52ead0f5daa175fdc4d73cad77c9f4e3999d10702a2a6',
        'wallet': '0xD8a394e7d7894bDF2C57139fF17e5Af22D0d12eF',
        'token': '0xdac17f958d2ee523a2206206994597c13d831ec7',  # USDT
        'expected_type': 'swap',
        'expected_stablecoin': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',  # USDC
        'description': 'Complex stablecoin swap USDT/USDC'
    }
]

def analyze_stablecoin_transaction(tx_info):
    """Analyze a stablecoin transaction"""
    tx_hash = tx_info['hash']
    wallet = tx_info['wallet']
    token = tx_info['token']
    
    print("\n" + "="*80)
    print(f"TESTING: {tx_info['description']}")
    print(f"Transaction: {tx_hash}")
    print("="*80)
    
    # Get transaction details
    tx_details = analyzer.get_transaction(tx_hash)
    
    # Check if stablecoins are involved
    stablecoins_involved = []
    for address in tx_details['involved_tokens']:
        if analyzer.is_stablecoin(address):
            stablecoin_info = analyzer.get_stablecoin_info(address)
            stablecoins_involved.append({
                'address': address,
                'symbol': stablecoin_info['symbol'],
                'decimals': stablecoin_info['decimals']
            })
    
    # Get token transfers for this transaction
    transfers = analyzer.get_token_transaction_transfers(tx_hash)
    
    # Get transaction type from analyzer
    tx_type, token_amount = analyzer.analyze_transaction_type(tx_hash, wallet, token)
    
    # Filter transfers for token and stablecoins
    token_transfers = []
    stablecoin_transfers = []
    
    for transfer in transfers:
        contract_address = transfer.get('contractAddress', '').lower()
        from_address = transfer.get('from', '').lower()
        to_address = transfer.get('to', '').lower()
        
        # Get token info
        token_decimals = int(transfer.get('tokenDecimal', 18))
        amount = float(transfer.get('value', 0)) / (10 ** token_decimals)
        
        transfer_data = {
            'contract': contract_address,
            'from': from_address,
            'to': to_address,
            'amount': amount,
            'decimals': token_decimals
        }
        
        # Check if this is our token
        if contract_address == token.lower():
            token_transfers.append(transfer_data)
            
        # Check if this is a stablecoin
        if analyzer.is_stablecoin(contract_address):
            stablecoin_info = analyzer.get_stablecoin_info(contract_address)
            transfer_data['symbol'] = stablecoin_info['symbol']
            stablecoin_transfers.append(transfer_data)
    
    # Determine stablecoin flow
    stablecoin_in = 0
    stablecoin_out = 0
    stablecoin_flow = {}
    
    for transfer in stablecoin_transfers:
        if transfer['to'].lower() == wallet.lower():
            stablecoin_in += transfer['amount']
            symbol = transfer.get('symbol', 'Unknown')
            if symbol not in stablecoin_flow:
                stablecoin_flow[symbol] = {'in': 0, 'out': 0}
            stablecoin_flow[symbol]['in'] += transfer['amount']
        
        if transfer['from'].lower() == wallet.lower():
            stablecoin_out += transfer['amount']
            symbol = transfer.get('symbol', 'Unknown')
            if symbol not in stablecoin_flow:
                stablecoin_flow[symbol] = {'in': 0, 'out': 0}
            stablecoin_flow[symbol]['out'] += transfer['amount']
    
    # Determine token flow
    token_in = 0
    token_out = 0
    
    for transfer in token_transfers:
        if transfer['to'].lower() == wallet.lower():
            token_in += transfer['amount']
        if transfer['from'].lower() == wallet.lower():
            token_out += transfer['amount']
    
    # Determine if the expected stablecoin is involved
    expected_stablecoin_involved = tx_info['expected_stablecoin'].lower() in [s['address'].lower() for s in stablecoins_involved]
    
    # Check if the transaction matches expected type
    type_match = tx_type == tx_info['expected_type']
    
    # Create result object
    result = {
        'transaction_hash': tx_hash,
        'description': tx_info['description'],
        'wallet': wallet,
        'token': token,
        'expected_type': tx_info['expected_type'],
        'analyzer_type': tx_type,
        'type_match': type_match,
        'expected_stablecoin': tx_info['expected_stablecoin'],
        'stablecoins_involved': stablecoins_involved,
        'expected_stablecoin_involved': expected_stablecoin_involved,
        'token_in': token_in,
        'token_out': token_out,
        'stablecoin_in': stablecoin_in,
        'stablecoin_out': stablecoin_out,
        'stablecoin_flow': stablecoin_flow,
        'eth_value': tx_details['eth_value'],
        'token_amount': token_amount
    }
    
    # Print results
    print("\nAnalysis Results:")
    print(f"Transaction Type: {tx_type} (Expected: {tx_info['expected_type']}) - Match: {type_match}")
    print(f"Token Amount: {token_amount}")
    print(f"ETH Value: {tx_details['eth_value']} ETH")
    
    print("\nStablecoins Involved:")
    for stablecoin in stablecoins_involved:
        print(f"- {stablecoin['symbol']} ({stablecoin['address']})")
    
    print(f"\nExpected Stablecoin Involved: {expected_stablecoin_involved}")
    
    print("\nToken Flow:")
    print(f"IN: {token_in}")
    print(f"OUT: {token_out}")
    
    print("\nStablecoin Flow:")
    for symbol, flow in stablecoin_flow.items():
        print(f"{symbol} - IN: {flow['in']}, OUT: {flow['out']}")
    
    return result

def run_stablecoin_tests():
    """Run all stablecoin transaction tests"""
    print("Starting stablecoin transaction tests...")
    
    results = []
    for tx_info in TEST_TRANSACTIONS:
        result = analyze_stablecoin_transaction(tx_info)
        results.append(result)
        # Add delay to avoid rate limiting
        time.sleep(1)
    
    # Calculate success metrics
    type_match_count = sum(1 for r in results if r['type_match'])
    stablecoin_match_count = sum(1 for r in results if r['expected_stablecoin_involved'])
    
    # Generate summary
    summary = {
        'total_tests': len(results),
        'type_match_count': type_match_count,
        'type_match_percentage': (type_match_count / len(results)) * 100 if results else 0,
        'stablecoin_match_count': stablecoin_match_count,
        'stablecoin_match_percentage': (stablecoin_match_count / len(results)) * 100 if results else 0,
        'results': results
    }
    
    # Save results
    result_file = os.path.join(RESULTS_DIR, "stablecoin_test_results.json")
    with open(result_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("STABLECOIN TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Transaction Type Match: {type_match_count}/{len(results)} ({summary['type_match_percentage']:.1f}%)")
    print(f"Stablecoin Detection Match: {stablecoin_match_count}/{len(results)} ({summary['stablecoin_match_percentage']:.1f}%)")
    print(f"Full results saved to {result_file}")
    
    return summary

if __name__ == "__main__":
    run_stablecoin_tests() 