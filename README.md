# Token PnL Analyzer

A Python tool to analyze token trading profit and loss (PnL) on Ethereum. This tool tracks buys, sells, gas costs, and calculates both realized and unrealized PnL for any ERC20 token.

## Features

- Track token buys and sells
- Calculate gas costs
- Historical price tracking
- Real-time price fetching from DexScreener
- Support for both direct token addresses and trading pairs
- Detailed PnL analysis including realized and unrealized gains/losses

## Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd <repo-directory>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp config/default.env .env
```

4. Edit `.env` file and add your Etherscan API key:
```
ETHERSCAN_API_KEY=your_api_key_here
```

## Usage

Run the analyzer:
```bash
python src/token_pnl_analyzer.py
```

You will be prompted to enter:
1. Token contract address or pair address (e.g., TOKEN/WETH)
2. Trader wallet address

## Example Output

```
==========================================
📊 Token Name (SYMBOL) Analysis
==========================================

🔄 Transaction Overview
   • Buy Transactions:  X
   • Sell Transactions: Y

💰 Token Position
   • Tokens Bought:   XXX.XX
   • Tokens Sold:     YYY.YY
   • Current Balance: ZZZ.ZZ

💸 Investment Summary
   • Total Invested: XX.XXXX ETH
   • Total Returned: YY.YYYY ETH
   • Gas Costs:      Z.ZZZZ ETH

📈 Current Value
   • Token Price:    0.XXXXXXXX ETH
   • Holdings Value: XX.XXXX ETH ($YYY.YY)

📊 Profit/Loss Summary
   Realized:
   • ETH: XX.XXXX
   • USD: $XXX.XX
   Unrealized:
   • ETH: YY.YYYY
   • USD: $YYY.YY

💫 Total Position PnL
   • ETH: ZZ.ZZZZ
   • USD: $ZZZ.ZZ
==========================================
```

## GitHub Codespaces

This project is configured to work with GitHub Codespaces. When creating a new codespace:

1. The required dependencies will be automatically installed
2. Copy the default.env to .env and add your Etherscan API key
3. Run the analyzer as described in the Usage section

## Environment Variables

- `ETHERSCAN_API_KEY`: Your Etherscan API key (required)
- `ETH_RPC_URL`: Ethereum RPC endpoint (defaults to Ankr's public endpoint)
- `WEB3_PROVIDER`: Web3 provider URL (defaults to Ankr's public endpoint)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 