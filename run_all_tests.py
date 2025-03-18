#!/usr/bin/env python3
import os
import sys
import json
import time
import datetime
import subprocess
from pathlib import Path

# Set up output directory
RESULTS_DIR = "test_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Configure test suites
TEST_SUITES = [
    {
        "name": "Full Token PnL Analysis",
        "script": "run_test_suite.py",
        "description": "Comprehensive PnL analysis for various token and wallet combinations"
    },
    {
        "name": "Stablecoin Transaction Tests",
        "script": "test_stablecoin_transactions.py",
        "description": "Focused tests on stablecoin transaction detection and handling"
    },
    {
        "name": "Buy/Sell Calculation Tests",
        "script": "test_buysell_calculations.py",
        "description": "Validation of buy/sell transaction counting and value calculation"
    }
]

def run_test_suite(suite):
    """Run a single test suite"""
    print("\n" + "="*80)
    print(f"RUNNING TEST SUITE: {suite['name']}")
    print(f"Script: {suite['script']}")
    print(f"Description: {suite['description']}")
    print("="*80 + "\n")
    
    start_time = time.time()
    
    # Run the test script
    try:
        result = subprocess.run(
            [sys.executable, suite['script']], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        output = result.stdout
        error = result.stderr
        success = result.returncode == 0
    except subprocess.CalledProcessError as e:
        output = e.stdout
        error = e.stderr
        success = False
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Save output
    output_file = os.path.join(RESULTS_DIR, f"{suite['script'].replace('.py', '')}_output.txt")
    with open(output_file, "w") as f:
        f.write(output)
    
    if error:
        error_file = os.path.join(RESULTS_DIR, f"{suite['script'].replace('.py', '')}_error.txt")
        with open(error_file, "w") as f:
            f.write(error)
    
    return {
        "name": suite['name'],
        "script": suite['script'],
        "success": success,
        "duration": duration,
        "output_file": output_file,
        "error_file": error_file if error else None
    }

def collect_test_results():
    """Collect and summarize results from all test suites"""
    all_results = {}
    
    # Collect stablecoin test results
    stablecoin_results_file = os.path.join(RESULTS_DIR, "stablecoin_test_results.json")
    if os.path.exists(stablecoin_results_file):
        with open(stablecoin_results_file, "r") as f:
            all_results["stablecoin_tests"] = json.load(f)
    
    # Collect buy/sell test results
    buysell_results_file = os.path.join(RESULTS_DIR, "buysell_test_results.json")
    if os.path.exists(buysell_results_file):
        with open(buysell_results_file, "r") as f:
            all_results["buysell_tests"] = json.load(f)
    
    # Collect transaction type verification results
    tx_verification_file = os.path.join(RESULTS_DIR, "transaction_type_verification.json")
    if os.path.exists(tx_verification_file):
        with open(tx_verification_file, "r") as f:
            all_results["transaction_verification"] = json.load(f)
    
    # Look for individual token analysis results
    token_results = []
    for file in os.listdir(RESULTS_DIR):
        if file.startswith("result_") and file.endswith(".json"):
            with open(os.path.join(RESULTS_DIR, file), "r") as f:
                token_results.append(json.load(f))
    
    if token_results:
        all_results["token_analysis"] = token_results
    
    return all_results

def generate_final_report(suite_results, test_results):
    """Generate a comprehensive final report"""
    report = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_suites": suite_results,
        "test_results": test_results,
        "summary": {
            "total_test_suites": len(suite_results),
            "successful_test_suites": sum(1 for s in suite_results if s["success"]),
            "total_duration": sum(s["duration"] for s in suite_results)
        }
    }
    
    # Calculate overall success metrics
    if "stablecoin_tests" in test_results:
        stablecoin = test_results["stablecoin_tests"]
        report["summary"]["stablecoin_type_accuracy"] = stablecoin.get("type_match_percentage", 0)
        report["summary"]["stablecoin_detection_accuracy"] = stablecoin.get("stablecoin_match_percentage", 0)
    
    if "buysell_tests" in test_results:
        buysell = test_results["buysell_tests"]
        report["summary"]["buy_count_accuracy"] = buysell.get("buy_count_match_percentage", 0)
        report["summary"]["sell_count_accuracy"] = buysell.get("sell_count_match_percentage", 0)
    
    if "token_analysis" in test_results:
        token_analysis = test_results["token_analysis"]
        balance_matches = sum(1 for t in token_analysis if t.get("verification", {}).get("balance_match"))
        report["summary"]["balance_accuracy"] = (balance_matches / len(token_analysis)) * 100 if token_analysis else 0
    
    # Save JSON report
    report_file = os.path.join(RESULTS_DIR, "final_report.json")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    # Generate human-readable report
    report_txt = os.path.join(RESULTS_DIR, "final_report.txt")
    with open(report_txt, "w") as f:
        f.write("TOKEN PNL ANALYZER - COMPREHENSIVE TEST REPORT\n")
        f.write("==========================================\n\n")
        f.write(f"Generated: {report['timestamp']}\n")
        f.write(f"Test Suites Run: {report['summary']['total_test_suites']}\n")
        f.write(f"Successful Test Suites: {report['summary']['successful_test_suites']}\n")
        f.write(f"Total Duration: {report['summary']['total_duration']:.2f} seconds\n\n")
        
        f.write("ACCURACY METRICS\n")
        f.write("---------------\n")
        if "stablecoin_type_accuracy" in report["summary"]:
            f.write(f"Stablecoin Transaction Type Accuracy: {report['summary']['stablecoin_type_accuracy']:.1f}%\n")
        if "stablecoin_detection_accuracy" in report["summary"]:
            f.write(f"Stablecoin Detection Accuracy: {report['summary']['stablecoin_detection_accuracy']:.1f}%\n")
        if "buy_count_accuracy" in report["summary"]:
            f.write(f"Buy Count Accuracy: {report['summary']['buy_count_accuracy']:.1f}%\n")
        if "sell_count_accuracy" in report["summary"]:
            f.write(f"Sell Count Accuracy: {report['summary']['sell_count_accuracy']:.1f}%\n")
        if "balance_accuracy" in report["summary"]:
            f.write(f"Balance Accuracy: {report['summary']['balance_accuracy']:.1f}%\n")
        
        f.write("\nTEST SUITE RESULTS\n")
        f.write("-----------------\n")
        for i, suite in enumerate(suite_results):
            f.write(f"{i+1}. {suite['name']} ({suite['script']})\n")
            f.write(f"   Success: {suite['success']}\n")
            f.write(f"   Duration: {suite['duration']:.2f} seconds\n")
            f.write(f"   Output: {Path(suite['output_file']).name}\n")
            if suite['error_file']:
                f.write(f"   Errors: {Path(suite['error_file']).name}\n")
            f.write("\n")
        
        # Include summary of stablecoin tests
        if "stablecoin_tests" in test_results:
            stablecoin = test_results["stablecoin_tests"]
            f.write("\nSTABLECOIN TEST RESULTS\n")
            f.write("----------------------\n")
            f.write(f"Total Tests: {stablecoin.get('total_tests', 0)}\n")
            f.write(f"Transaction Type Match: {stablecoin.get('type_match_count', 0)}/{stablecoin.get('total_tests', 0)} ")
            f.write(f"({stablecoin.get('type_match_percentage', 0):.1f}%)\n")
            f.write(f"Stablecoin Detection Match: {stablecoin.get('stablecoin_match_count', 0)}/{stablecoin.get('total_tests', 0)} ")
            f.write(f"({stablecoin.get('stablecoin_match_percentage', 0):.1f}%)\n\n")
        
        # Include summary of buy/sell tests
        if "buysell_tests" in test_results:
            buysell = test_results["buysell_tests"]
            f.write("\nBUY/SELL CALCULATION RESULTS\n")
            f.write("--------------------------\n")
            f.write(f"Total Tests: {buysell.get('total_tests', 0)}\n")
            f.write(f"Buy Count Matches: {buysell.get('buy_count_matches', 0)}/{buysell.get('total_tests', 0)} ")
            f.write(f"({buysell.get('buy_count_match_percentage', 0):.1f}%)\n")
            f.write(f"Sell Count Matches: {buysell.get('sell_count_matches', 0)}/{buysell.get('total_tests', 0)} ")
            f.write(f"({buysell.get('sell_count_match_percentage', 0):.1f}%)\n\n")
        
        f.write("\nCONCLUSION\n")
        f.write("----------\n")
        
        # Calculate overall success percentage
        success_metrics = []
        if "stablecoin_type_accuracy" in report["summary"]:
            success_metrics.append(report["summary"]["stablecoin_type_accuracy"])
        if "buy_count_accuracy" in report["summary"]:
            success_metrics.append(report["summary"]["buy_count_accuracy"])
        if "sell_count_accuracy" in report["summary"]:
            success_metrics.append(report["summary"]["sell_count_accuracy"])
        if "balance_accuracy" in report["summary"]:
            success_metrics.append(report["summary"]["balance_accuracy"])
        
        overall_accuracy = sum(success_metrics) / len(success_metrics) if success_metrics else 0
        
        f.write(f"Overall Accuracy: {overall_accuracy:.1f}%\n")
        
        if overall_accuracy >= 90:
            f.write("STATUS: EXCELLENT - The token PnL analyzer performs exceptionally well with high accuracy.\n")
        elif overall_accuracy >= 80:
            f.write("STATUS: GOOD - The token PnL analyzer performs well with good accuracy.\n")
        elif overall_accuracy >= 70:
            f.write("STATUS: ACCEPTABLE - The token PnL analyzer performs adequately but has room for improvement.\n")
        else:
            f.write("STATUS: NEEDS IMPROVEMENT - The token PnL analyzer requires further refinement for better accuracy.\n")
    
    print(f"\nFinal report saved to {report_file} and {report_txt}")
    return report

def run_all_tests():
    """Run all test suites and generate a comprehensive report"""
    print(f"Starting complete test run at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Results will be saved to {RESULTS_DIR}")
    
    suite_results = []
    for suite in TEST_SUITES:
        result = run_test_suite(suite)
        suite_results.append(result)
        # Add delay between test suites
        time.sleep(2)
    
    # Collect all test results
    test_results = collect_test_results()
    
    # Generate final report
    generate_final_report(suite_results, test_results)
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    run_all_tests() 