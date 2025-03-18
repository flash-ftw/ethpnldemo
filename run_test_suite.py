#!/usr/bin/env python3
import os
import sys
import json
import time
import random
import requests
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

# Etherscan API
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
ETHERSCAN_API_URL = "https://api.etherscan.io/api"

# Create results directory
RESULTS_DIR = "test_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Test cases - wallet address, token address, description
TEST_CASES = [
    # Test case 1: ETH/WETH transactions
    {
        'wallet': '0x87851CbCDa813b3C2ec1411c3e4b7f2d3121aBf8',
        'token': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
        'description': 'Wallet with WETH transactions'
    },
    # Test case 2: Stablecoin (USDC)
    {
        'wallet': '0x5a52E96BAcdaBb82fd05763E25335261B270Efcb',
        'token': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',  # USDC
        'description': 'Wallet with USDC stablecoin transactions'
    },
    # Test case 3: Wrapped BTC
    {
        'wallet': '0x28C6c06298d514Db089934071355E5743bf21d60',
        'token': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',  # WBTC
        'description': 'Wallet with WBTC transactions'
    },
    # Test case 4: Chainlink with stablecoin swaps
    {
        'wallet': '0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296',
        'token': '0x514910771AF9Ca656af840dff83E8264EcF986CA',  # LINK
        'description': 'Wallet with LINK transactions and stablecoin swaps'
    },
    # Test case 5: UNI token
    {
        'wallet': '0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503',
        'token': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',  # UNI
        'description': 'Wallet with UNI token transactions using both ETH and stablecoins'
    }
]

# Known transactions for detailed verification
VERIFICATION_TRANSACTIONS = [
    # Buy with ETH
    {
        'hash': '0x8a1957e3f2d108d3e4816d38629e0a377ec40b55e3ceb104b3965e3def9c6535',
        'expected_type': 'buy',
        'wallet': '0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503',
        'token': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',  # UNI
        'description': 'Buy UNI with ETH'
    },
    # Sell for ETH
    {
        'hash': '0x621e7dcfd3a3e2f2f796e68eb8df5acb926acb8fffb16e6ec6d94bc2dc4582c1',
        'expected_type': 'sell',
        'wallet': '0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503',
        'token': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',  # UNI
        'description': 'Sell UNI for ETH'
    },
    # Buy with USDC
    {
        'hash': '0x3ca5db544a6c20e0c923369ef5f4fa8fae494a39ee787714e5fcc87443aa9397',
        'expected_type': 'buy',
        'wallet': '0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296',
        'token': '0x514910771AF9Ca656af840dff83E8264EcF986CA',  # LINK
        'description': 'Buy LINK with USDC'
    },
    # Sell for USDT
    {
        'hash': '0x91be607125faee3ce70f1af7a2e299244e5e5087ce24e52663e5cf99da3dfe1c',
        'expected_type': 'sell',
        'wallet': '0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503',
        'token': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',  # UNI
        'description': 'Sell UNI for USDT'
    }
]

def fetch_etherscan_balance(wallet, token):
    """Fetch token balance from Etherscan"""
    params = {
        'module': 'account',
        'action': 'tokenbalance',
        'contractaddress': token,
        'address': wallet,
        'tag': 'latest',
        'apikey': ETHERSCAN_API_KEY
    }
    
    try:
        response = requests.get(ETHERSCAN_API_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '1':
                # Get token decimals
                token_decimals = 18  # Default
                try:
                    token_contract = analyzer.w3.eth.contract(
                        address=analyzer.w3.to_checksum_address(token),
                        abi=analyzer.token_abi
                    )
                    token_decimals = token_contract.functions.decimals().call()
                except Exception:
                    pass
                
                return int(data['result']) / (10 ** token_decimals)
    except Exception as e:
        print(f"Error fetching Etherscan balance: {str(e)}")
    
    return None

def fetch_etherscan_transactions(wallet, token):
    """Fetch token transactions from Etherscan"""
    params = {
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': token,
        'address': wallet,
        'sort': 'asc',
        'apikey': ETHERSCAN_API_KEY
    }
    
    try:
        response = requests.get(ETHERSCAN_API_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '1':
                return data['result']
    except Exception as e:
        print(f"Error fetching Etherscan transactions: {str(e)}")
    
    return []

def verify_transaction_type(tx_hash):
    """Verify transaction type against our analyzer"""
    print(f"\nVerifying transaction {tx_hash}...")
    
    # Find matching verification case
    verification_case = None
    for case in VERIFICATION_TRANSACTIONS:
        if case['hash'] == tx_hash:
            verification_case = case
            break
    
    if not verification_case:
        print(f"No verification case found for transaction {tx_hash}")
        return False
    
    # Get our analysis
    tx_details = analyzer.get_transaction(tx_hash)
    tx_type, token_amount = analyzer.analyze_transaction_type(
        tx_hash, 
        verification_case['wallet'], 
        verification_case['token']
    )
    
    # Get Etherscan data for comparison
    params = {
        'module': 'proxy',
        'action': 'eth_getTransactionByHash',
        'txhash': tx_hash,
        'apikey': ETHERSCAN_API_KEY
    }
    
    etherscan_data = {}
    try:
        response = requests.get(ETHERSCAN_API_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and data['result']:
                etherscan_data = data['result']
    except Exception as e:
        print(f"Error fetching Etherscan transaction: {str(e)}")
    
    # Get token transfers for this transaction
    token_transfers = analyzer.get_token_transaction_transfers(tx_hash)
    
    result = {
        'transaction_hash': tx_hash,
        'description': verification_case['description'],
        'expected_type': verification_case['expected_type'],
        'analyzer_type': tx_type,
        'match': tx_type == verification_case['expected_type'],
        'token_amount': token_amount,
        'eth_value': tx_details['eth_value'],
        'involved_tokens': tx_details['involved_tokens'],
        'etherscan_value': int(etherscan_data.get('value', '0x0'), 16) / 1e18 if etherscan_data else 0,
        'transfer_count': len(token_transfers)
    }
    
    print(f"Expected type: {verification_case['expected_type']}")
    print(f"Analyzer type: {tx_type}")
    print(f"Match: {result['match']}")
    print(f"Token amount: {token_amount}")
    print(f"ETH value: {tx_details['eth_value']}")
    
    return result

def analyze_and_verify(case):
    """Run analysis and verify results against Etherscan"""
    print("\n" + "="*80)
    print(f"ANALYZING: {case['description']}")
    print(f"Wallet: {case['wallet']}")
    print(f"Token: {case['token']}")
    print("="*80)
    
    # Start time for tracking execution
    start_time = time.time()
    
    # Run the analysis
    try:
        results = analyzer.analyze_pnl(case['wallet'], case['token'])
        
        if not results:
            print("No results returned from analyzer")
            return None
        
        # Get Etherscan balance for verification
        etherscan_balance = fetch_etherscan_balance(case['wallet'], case['token'])
        
        # Get transactions from Etherscan for counting
        etherscan_txs = fetch_etherscan_transactions(case['wallet'], case['token'])
        
        # Count transfers in and out from Etherscan
        etherscan_in = 0
        etherscan_out = 0
        etherscan_unique_txs = set()
        
        for tx in etherscan_txs:
            etherscan_unique_txs.add(tx['hash'])
            if tx['to'].lower() == case['wallet'].lower():
                etherscan_in += 1
            elif tx['from'].lower() == case['wallet'].lower():
                etherscan_out += 1
        
        # Execution time
        execution_time = time.time() - start_time
        
        # Build verification results
        verification = {
            'wallet': case['wallet'],
            'token': case['token'],
            'token_name': results['token_name'],
            'token_symbol': results['token_symbol'],
            'analyzer_balance': results['current_balance'],
            'etherscan_balance': etherscan_balance,
            'balance_match': abs(results['current_balance'] - etherscan_balance) < 0.0001 if etherscan_balance is not None else None,
            'analyzer_buy_count': results['buy_count'],
            'analyzer_sell_count': results['sell_count'],
            'etherscan_in_count': etherscan_in,
            'etherscan_out_count': etherscan_out,
            'analyzer_unique_tx_count': len(results['transactions']) if 'transactions' in results else 0,
            'etherscan_unique_tx_count': len(etherscan_unique_txs),
            'total_tokens_bought': results['total_tokens_bought'],
            'total_tokens_sold': results['total_tokens_sold'],
            'total_in_eth': results['total_in_eth'],
            'total_out_eth': results['total_out_eth'],
            'realized_pnl_eth': results['realized_pnl_eth'],
            'unrealized_pnl_eth': results['unrealized_pnl_eth'],
            'execution_time': execution_time
        }
        
        # Print summary
        print("\nRESULTS SUMMARY:")
        print(f"Token: {results['token_name']} ({results['token_symbol']})")
        print(f"Analyzer Balance: {results['current_balance']:.4f} {results['token_symbol']}")
        print(f"Etherscan Balance: {etherscan_balance:.4f} {results['token_symbol']} (Match: {verification['balance_match']})")
        print(f"Analyzer Buy Count: {results['buy_count']}")
        print(f"Analyzer Sell Count: {results['sell_count']}")
        print(f"Etherscan In Count: {etherscan_in}")
        print(f"Etherscan Out Count: {etherscan_out}")
        print(f"Analyzer Unique Transactions: {verification['analyzer_unique_tx_count']}")
        print(f"Etherscan Unique Transactions: {verification['etherscan_unique_tx_count']}")
        print(f"Total Bought: {results['total_tokens_bought']:.4f} {results['token_symbol']} for {results['total_in_eth']:.4f} ETH")
        print(f"Total Sold: {results['total_tokens_sold']:.4f} {results['token_symbol']} for {results['total_out_eth']:.4f} ETH")
        print(f"Realized PnL: {results['realized_pnl_eth']:.4f} ETH (${results['realized_pnl_usd']:.2f})")
        print(f"Unrealized PnL: {results['unrealized_pnl_eth']:.4f} ETH (${results['unrealized_pnl_usd']:.2f})")
        print(f"Execution Time: {execution_time:.2f} seconds")
        
        # Save full results and verification to file
        result_file = os.path.join(RESULTS_DIR, f"result_{case['token'].lower()[:8]}_{case['wallet'].lower()[:8]}.json")
        with open(result_file, 'w') as f:
            json.dump({
                'analysis': results,
                'verification': verification
            }, f, indent=2)
            
        print(f"Full results saved to {result_file}")
        
        return verification
        
    except Exception as e:
        import traceback
        print(f"ERROR analyzing case: {str(e)}")
        print(traceback.format_exc())
        return None

def test_specific_transaction_types():
    """Test specific transaction types against known transactions"""
    print("\n" + "="*80)
    print("TESTING SPECIFIC TRANSACTION TYPES")
    print("="*80)
    
    results = []
    for tx_hash in [case['hash'] for case in VERIFICATION_TRANSACTIONS]:
        result = verify_transaction_type(tx_hash)
        if result:
            results.append(result)
    
    # Save results
    result_file = os.path.join(RESULTS_DIR, "transaction_type_verification.json")
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"Transaction type verification results saved to {result_file}")
    
    # Calculate success rate
    success_count = sum(1 for r in results if r['match'])
    print(f"\nTransaction Type Verification: {success_count}/{len(results)} correct ({success_count/len(results)*100:.1f}%)")
    
    return results

def generate_summary_report(case_results, tx_results):
    """Generate a summary report of all tests"""
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'test_cases': len(case_results),
        'transaction_verifications': len(tx_results),
        'balance_accuracy': sum(1 for r in case_results if r.get('balance_match')) / len(case_results) if case_results else 0,
        'transaction_type_accuracy': sum(1 for r in tx_results if r.get('match')) / len(tx_results) if tx_results else 0,
        'average_execution_time': sum(r.get('execution_time', 0) for r in case_results) / len(case_results) if case_results else 0,
        'token_summary': [],
        'transaction_summary': []
    }
    
    # Add token summaries
    for result in case_results:
        report['token_summary'].append({
            'token_symbol': result.get('token_symbol', 'Unknown'),
            'wallet': result.get('wallet', 'Unknown'),
            'balance_match': result.get('balance_match'),
            'buy_count': result.get('analyzer_buy_count', 0),
            'sell_count': result.get('analyzer_sell_count', 0),
            'total_bought': result.get('total_tokens_bought', 0),
            'total_sold': result.get('total_tokens_sold', 0)
        })
    
    # Add transaction summaries
    for result in tx_results:
        report['transaction_summary'].append({
            'hash': result.get('transaction_hash', 'Unknown'),
            'description': result.get('description', 'Unknown'),
            'expected_type': result.get('expected_type', 'unknown'),
            'analyzer_type': result.get('analyzer_type', 'unknown'),
            'match': result.get('match', False)
        })
    
    # Save report
    report_file = os.path.join(RESULTS_DIR, "summary_report.json")
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Also save a human-readable version
    report_txt = os.path.join(RESULTS_DIR, "summary_report.txt")
    with open(report_txt, 'w') as f:
        f.write("TOKEN PNL ANALYZER TEST REPORT\n")
        f.write("===========================\n\n")
        f.write(f"Generated: {report['timestamp']}\n")
        f.write(f"Test Cases: {report['test_cases']}\n")
        f.write(f"Transaction Verifications: {report['transaction_verifications']}\n")
        f.write(f"Balance Accuracy: {report['balance_accuracy']*100:.1f}%\n")
        f.write(f"Transaction Type Accuracy: {report['transaction_type_accuracy']*100:.1f}%\n")
        f.write(f"Average Execution Time: {report['average_execution_time']:.2f} seconds\n\n")
        
        f.write("TOKEN SUMMARY\n")
        f.write("------------\n")
        for i, summary in enumerate(report['token_summary']):
            f.write(f"{i+1}. {summary['token_symbol']} - Wallet: {summary['wallet'][:8]}...\n")
            f.write(f"   Balance Match: {summary['balance_match']}\n")
            f.write(f"   Buy Count: {summary['buy_count']}\n")
            f.write(f"   Sell Count: {summary['sell_count']}\n")
            f.write(f"   Total Bought: {summary['total_bought']:.4f}\n")
            f.write(f"   Total Sold: {summary['total_sold']:.4f}\n\n")
        
        f.write("TRANSACTION VERIFICATION\n")
        f.write("-----------------------\n")
        for i, summary in enumerate(report['transaction_summary']):
            f.write(f"{i+1}. {summary['description']} - {summary['hash'][:16]}...\n")
            f.write(f"   Expected Type: {summary['expected_type']}\n")
            f.write(f"   Analyzer Type: {summary['analyzer_type']}\n")
            f.write(f"   Match: {summary['match']}\n\n")
    
    print(f"\nSummary report saved to {report_file} and {report_txt}")
    
    return report

def run_test_suite():
    """Run the complete test suite"""
    print(f"Starting test suite at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Results will be saved to {RESULTS_DIR}")
    
    # Run full analysis tests
    case_results = []
    for case in TEST_CASES:
        result = analyze_and_verify(case)
        if result:
            case_results.append(result)
        # Delay to avoid rate limiting
        time.sleep(random.uniform(1.0, 2.0))
    
    # Test specific transaction types
    tx_results = test_specific_transaction_types()
    
    # Generate summary report
    generate_summary_report(case_results, tx_results)
    
    print("\nTest suite completed!")

if __name__ == "__main__":
    run_test_suite() 