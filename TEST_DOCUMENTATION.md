# Token PnL Analyzer Testing Documentation

This document describes the testing environment and procedures for validating the Token PnL Analyzer against real Etherscan data.

## Overview

The testing framework consists of two main components:

1. **General Testing** (`test_analyzer.py`): Runs the Token PnL Analyzer on a set of predefined wallets and tokens to verify overall functionality.

2. **Detailed Validation** (`test_validation.py`): Performs focused tests on specific aspects of the analyzer, such as stablecoin detection, transaction type classification, and balance verification.

## Test Setup

### Requirements

- Python 3.6+
- Dependencies in `requirements.txt`
- Etherscan API key (in `.env` file)

### Configuration

Create a `.env` file with your Etherscan API key:

```
ETHERSCAN_API_KEY=your_api_key_here
```

## Test Cases

### General Testing

The `test_analyzer.py` script includes the following test cases:

1. **WETH Transactions**: Tests basic ETH/WETH handling
2. **USDC Transactions**: Tests stablecoin operations
3. **WBTC Transactions**: Tests transactions for a non-ETH token
4. **LINK with Stablecoins**: Tests transactions involving stablecoin swaps
5. **UNI with Mixed Payments**: Tests transactions using both ETH and stablecoins

### Validation Testing

The `test_validation.py` script performs detailed validation of specific components:

1. **Stablecoin Detection**: Verifies the correct identification of stablecoin addresses
2. **Buy/Sell Detection**: Validates transaction type classification
3. **Stablecoin Transaction Analysis**: Tests the handling of transactions involving stablecoins
4. **Balance Verification**: Compares calculated balances with blockchain data

## How to Run Tests

1. Run the general tests:
   ```
   python test_analyzer.py
   ```

2. Run the detailed validation tests:
   ```
   python test_validation.py
   ```

## Verification Process

For each test case, the following verification steps are performed:

1. **Balance Verification**: Compare calculated token balances with Etherscan data
2. **Transaction Count Verification**: Check if all transactions are correctly counted
3. **Buy/Sell Identification**: Ensure transactions are correctly classified
4. **Value Calculation**: Verify ETH values for transactions are accurate
5. **PnL Calculation**: Validate realized and unrealized PnL calculations

## Etherscan Verification

To manually verify results against Etherscan:

1. Visit the wallet address page: `https://etherscan.io/address/{wallet_address}`
2. Check token transfers: `https://etherscan.io/token/{token_address}?a={wallet_address}`
3. Inspect specific transactions using their hash

## Transaction Types

The analyzer classifies transactions into the following types:

- **Buy**: Wallet receives tokens in exchange for ETH or stablecoins
- **Sell**: Wallet sends tokens in exchange for ETH or stablecoins
- **Unknown**: Cannot determine transaction type

## Stablecoin Support

The following stablecoins are supported for transaction analysis:

- USDC (`0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`)
- USDT (`0xdAC17F958D2ee523a2206206994597C13D831ec7`)
- DAI (`0x6B175474E89094C44Da98b954EedeAC495271d0F`)
- FRAX (`0x853d955aCEf822Db058eb8505911ED77F175b99e`)
- BUSD (`0x4Fabb145d64652a948d72533023f6E7A623C7C53`)
- And several others

## Troubleshooting

Common issues and their solutions:

1. **API Key Issues**: Ensure your Etherscan API key is valid and has sufficient quota
2. **RPC Connection Errors**: The analyzer will automatically try alternative RPC endpoints
3. **Transaction Type Misclassification**: This can happen with complex DeFi interactions
4. **Missing Transactions**: Ensure enough time has passed for transactions to be indexed by Etherscan

## Example Results

Example result from test_analyzer.py:
```json
{
  "token_name": "ChainLink Token",
  "token_symbol": "LINK",
  "buy_count": 3,
  "sell_count": 2,
  "total_tokens_bought": 150.0,
  "total_tokens_sold": 75.0,
  "current_balance": 75.0,
  "total_in_eth": 0.5,
  "total_out_eth": 0.3,
  "total_gas_eth": 0.02,
  "current_price_eth": 0.005,
  "current_holdings_eth": 0.375,
  "current_holdings_usd": 750.0,
  "realized_pnl_eth": 0.05,
  "realized_pnl_usd": 100.0,
  "unrealized_pnl_eth": 0.125,
  "unrealized_pnl_usd": 250.0,
  "total_pnl_eth": 0.175,
  "total_pnl_usd": 350.0,
  "eth_price_usd": 2000.0
}
``` 