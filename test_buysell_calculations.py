#!/usr/bin/env python3
import os
import json
import time
from dotenv import load_dotenv
from src.token_pnl_analyzer import TokenPnLAnalyzer

# Load environment variables
load_dotenv()

# Initialize analyzer
analyzer = TokenPnLAnalyzer()

# Create results directory
RESULTS_DIR = "test_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Test wallets with known buy/sell patterns
TEST_WALLETS = [
    # Test case 1: Wallet with clear buy/sell pattern with ETH
    {
        'wallet': '0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503',
        'token': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',  # UNI
        'description': 'UNI token with ETH buys/sells',
        'expected_buys': 3,
        'expected_sells': 2
    },
    # Test case 2: Wallet with stablecoin transactions
    {
        'wallet': '0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296',
        'token': '0x514910771AF9Ca656af840dff83E8264EcF986CA',  # LINK
        'description': 'LINK token with stablecoin buys',
        'expected_buys': 2,
        'expected_sells': 1
    }
]

def test_buy_sell_logic(wallet_info):
    """Test buy/sell calculation logic for a specific wallet and token"""
    print("\n" + "="*80)
    print(f"TESTING BUY/SELL LOGIC: {wallet_info['description']}")
    print(f"Wallet: {wallet_info['wallet']}")
    print(f"Token: {wallet_info['token']}")
    print("="*80)
    
    try:
        # Run the PnL analysis
        results = analyzer.analyze_pnl(wallet_info['wallet'], wallet_info['token'])
        
        if not results:
            print("No results returned")
            return None
        
        # Extract buy/sell counts and amounts
        buy_count = results['buy_count']
        sell_count = results['sell_count']
        total_tokens_bought = results['total_tokens_bought']
        total_tokens_sold = results['total_tokens_sold']
        total_in_eth = results['total_in_eth']
        total_out_eth = results['total_out_eth']
        
        # Calculate average prices
        avg_buy_price = total_in_eth / total_tokens_bought if total_tokens_bought > 0 else 0
        avg_sell_price = total_out_eth / total_tokens_sold if total_tokens_sold > 0 else 0
        
        # Check if counts match expected values
        buy_count_match = buy_count == wallet_info['expected_buys']
        sell_count_match = sell_count == wallet_info['expected_sells']
        
        # Create result object
        result = {
            'wallet': wallet_info['wallet'],
            'token': wallet_info['token'],
            'token_name': results['token_name'],
            'token_symbol': results['token_symbol'],
            'description': wallet_info['description'],
            'buy_count': buy_count,
            'expected_buy_count': wallet_info['expected_buys'],
            'buy_count_match': buy_count_match,
            'sell_count': sell_count,
            'expected_sell_count': wallet_info['expected_sells'],
            'sell_count_match': sell_count_match,
            'total_tokens_bought': total_tokens_bought,
            'total_tokens_sold': total_tokens_sold,
            'total_in_eth': total_in_eth,
            'total_out_eth': total_out_eth,
            'avg_buy_price_eth': avg_buy_price,
            'avg_sell_price_eth': avg_sell_price,
            'realized_pnl_eth': results['realized_pnl_eth'],
            'unrealized_pnl_eth': results['unrealized_pnl_eth'],
            'current_balance': results['current_balance'],
            'current_price_eth': results['current_price_eth']
        }
        
        # Print results
        print("\nAnalysis Results:")
        print(f"Token: {results['token_name']} ({results['token_symbol']})")
        print(f"Buy Count: {buy_count} (Expected: {wallet_info['expected_buys']}) - Match: {buy_count_match}")
        print(f"Sell Count: {sell_count} (Expected: {wallet_info['expected_sells']}) - Match: {sell_count_match}")
        print(f"Total Tokens Bought: {total_tokens_bought:.4f} {results['token_symbol']}")
        print(f"Total Tokens Sold: {total_tokens_sold:.4f} {results['token_symbol']}")
        print(f"Total ETH In: {total_in_eth:.4f} ETH")
        print(f"Total ETH Out: {total_out_eth:.4f} ETH")
        print(f"Average Buy Price: {avg_buy_price:.6f} ETH per {results['token_symbol']}")
        print(f"Average Sell Price: {avg_sell_price:.6f} ETH per {results['token_symbol']}")
        print(f"Realized PnL: {results['realized_pnl_eth']:.4f} ETH (${results['realized_pnl_usd']:.2f})")
        print(f"Unrealized PnL: {results['unrealized_pnl_eth']:.4f} ETH (${results['unrealized_pnl_usd']:.2f})")
        
        # Print transaction details
        if 'transactions' in results:
            print("\nTransaction Details:")
            for i, tx in enumerate(results['transactions']):
                print(f"{i+1}. [{tx['type']}] {tx['date_time']} - {tx['token_amount']:.4f} {results['token_symbol']} ({tx['eth_value']:.4f} ETH)")
        
        return result
    
    except Exception as e:
        import traceback
        print(f"Error in test_buy_sell_logic: {str(e)}")
        print(traceback.format_exc())
        return None

def run_buysell_tests():
    """Run tests on buy/sell calculation logic"""
    print("Starting buy/sell calculation tests...")
    
    results = []
    for wallet_info in TEST_WALLETS:
        result = test_buy_sell_logic(wallet_info)
        if result:
            results.append(result)
        # Add delay to avoid rate limiting
        time.sleep(1)
    
    # Calculate success metrics
    buy_count_matches = sum(1 for r in results if r['buy_count_match'])
    sell_count_matches = sum(1 for r in results if r['sell_count_match'])
    
    # Generate summary
    summary = {
        'total_tests': len(results),
        'buy_count_matches': buy_count_matches,
        'buy_count_match_percentage': (buy_count_matches / len(results)) * 100 if results else 0,
        'sell_count_matches': sell_count_matches,
        'sell_count_match_percentage': (sell_count_matches / len(results)) * 100 if results else 0,
        'results': results
    }
    
    # Save results
    result_file = os.path.join(RESULTS_DIR, "buysell_test_results.json")
    with open(result_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("BUY/SELL CALCULATION TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Buy Count Matches: {buy_count_matches}/{len(results)} ({summary['buy_count_match_percentage']:.1f}%)")
    print(f"Sell Count Matches: {sell_count_matches}/{len(results)} ({summary['sell_count_match_percentage']:.1f}%)")
    print(f"Full results saved to {result_file}")
    
    return summary

if __name__ == "__main__":
    run_buysell_tests() 