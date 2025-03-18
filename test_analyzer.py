#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from src.token_pnl_analyzer import TokenPnLAnalyzer

# Load environment variables
load_dotenv()

# Check for API key
if not os.getenv('ETHERSCAN_API_KEY'):
    print("ERROR: ETHERSCAN_API_KEY environment variable is not set.")
    print("Please create a .env file with your Etherscan API key.")
    sys.exit(1)

# Initialize analyzer
analyzer = TokenPnLAnalyzer()

# Test cases - wallet address, token address, description
TEST_CASES = [
    # Test case 1: A wallet with WETH transactions
    {
        'wallet': '0x87851CbCDa813b3C2ec1411c3e4b7f2d3121aBf8',
        'token': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
        'description': 'Wallet with WETH transactions'
    },
    # Test case 2: A wallet with stablecoin transactions (USDC)
    {
        'wallet': '0x5a52E96BAcdaBb82fd05763E25335261B270Efcb',
        'token': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',  # USDC
        'description': 'Wallet with USDC stablecoin transactions'
    },
    # Test case 3: A wallet with multiple token transactions
    {
        'wallet': '0x28C6c06298d514Db089934071355E5743bf21d60',
        'token': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',  # WBTC
        'description': 'Wallet with WBTC transactions'
    },
    # Test case 4: A wallet with known buy/sell transactions with stablecoins
    {
        'wallet': '0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296',
        'token': '0x514910771AF9Ca656af840dff83E8264EcF986CA',  # LINK
        'description': 'Wallet with LINK transactions and stablecoin swaps'
    },
    # Test case 5: A wallet with a mix of ETH and stablecoin transactions
    {
        'wallet': '0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503',
        'token': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',  # UNI
        'description': 'Wallet with UNI token transactions using both ETH and stablecoins'
    }
]

def save_results(results, case_index):
    """Save test results to a JSON file"""
    filename = f"test_results_case_{case_index}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {filename}")

def run_tests():
    """Run all test cases and record results"""
    print(f"Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing {len(TEST_CASES)} scenarios")
    
    for i, case in enumerate(TEST_CASES):
        print("\n" + "="*80)
        print(f"TEST CASE {i+1}: {case['description']}")
        print(f"Wallet: {case['wallet']}")
        print(f"Token: {case['token']}")
        print("="*80 + "\n")
        
        try:
            # Run the analysis
            results = analyzer.analyze_pnl(case['wallet'], case['token'])
            
            if results:
                # Print summary
                print("\nRESULTS SUMMARY:")
                print(f"Token: {results['token_name']} ({results['token_symbol']})")
                print(f"Buy Count: {results['buy_count']}")
                print(f"Sell Count: {results['sell_count']}")
                print(f"Total Bought: {results['total_tokens_bought']:.4f} {results['token_symbol']} for {results['total_in_eth']:.4f} ETH")
                print(f"Total Sold: {results['total_tokens_sold']:.4f} {results['token_symbol']} for {results['total_out_eth']:.4f} ETH")
                print(f"Current Balance: {results['current_balance']:.4f} {results['token_symbol']}")
                print(f"Realized PnL: {results['realized_pnl_eth']:.4f} ETH (${results['realized_pnl_usd']:.2f})")
                print(f"Unrealized PnL: {results['unrealized_pnl_eth']:.4f} ETH (${results['unrealized_pnl_usd']:.2f})")
                print(f"Total Gas Spent: {results['total_gas_eth']:.4f} ETH")
                print("\nVALIDATION INSTRUCTIONS:")
                print(f"1. Visit https://etherscan.io/address/{case['wallet']}")
                print(f"2. Check token transfers for {results['token_symbol']} at https://etherscan.io/token/{case['token']}?a={case['wallet']}")
                print(f"3. Verify current balance matches Etherscan")
                print(f"4. Sample transaction hashes to verify on Etherscan:")
                
                # Print a few transaction hashes for manual verification
                if 'transactions' in results and results['transactions']:
                    for j, tx in enumerate(results['transactions'][:3]):  # Show first 3 transactions
                        print(f"   - {tx['hash']} ({tx['type']} {tx['token_amount']:.4f} {results['token_symbol']} at {tx['date_time']})")
                
                # Save detailed results to file
                save_results(results, i+1)
            else:
                print("No results returned from analyzer")
        
        except Exception as e:
            print(f"ERROR analyzing case {i+1}: {str(e)}")
    
    print("\nAll tests completed")

if __name__ == "__main__":
    run_tests() 