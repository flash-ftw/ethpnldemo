from flask import Flask, render_template, request, jsonify
from token_pnl_analyzer import TokenPnLAnalyzer
import os
from dotenv import load_dotenv

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # Get input data
        token_address = request.form.get('token_address')
        wallet_address = request.form.get('wallet_address')
        etherscan_key = request.form.get('etherscan_key')
        
        # Set environment variable
        os.environ['ETHERSCAN_API_KEY'] = etherscan_key
        
        # Initialize analyzer
        analyzer = TokenPnLAnalyzer()
        
        # Get analysis results
        results = analyzer.analyze_pnl(wallet_address, token_address)
        
        if results:
            return jsonify({
                'success': True,
                'data': {
                    'token_name': results['token_name'],
                    'token_symbol': results['token_symbol'],
                    'buy_count': results['buy_count'],
                    'sell_count': results['sell_count'],
                    'total_tokens_bought': float(results['total_tokens_bought']),
                    'total_tokens_sold': float(results['total_tokens_sold']),
                    'current_balance': float(results['current_balance']),
                    'total_in_eth': float(results['total_in_eth']),
                    'total_out_eth': float(results['total_out_eth']),
                    'total_gas_eth': float(results['total_gas_eth']),
                    'current_price_eth': float(results['current_price_eth']),
                    'current_holdings_eth': float(results['current_holdings_eth']),
                    'current_holdings_usd': float(results['current_holdings_usd']),
                    'realized_pnl_eth': float(results['realized_pnl_eth']),
                    'realized_pnl_usd': float(results['realized_pnl_usd']),
                    'unrealized_pnl_eth': float(results['unrealized_pnl_eth']),
                    'unrealized_pnl_usd': float(results['unrealized_pnl_usd'])
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No transactions found for this token and wallet combination'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True) 