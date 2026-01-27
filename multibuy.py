import os
import sys
import time
import signal
from decimal import Decimal
from web3 import Web3
from eth_account import Account
from web3.exceptions import TransactionNotFound, TimeExhausted

# ------------------------------
# CONFIGURATION
# ------------------------------
RPC_URL = os.environ.get("RPC_URL", "https://rpc.pulsechain.com")
PRIVATE_KEY = os.environ.get("KEY")
ACCOUNT_ADDRESS = Web3.to_checksum_address("0xCeC3cdcbaaD459b2b7bEe596eA70A5300E5Aa834")

TOKEN_ADDRESS = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
MULTIMATH_ADDRESS = Web3.to_checksum_address("0x3dF517a0FaA3fe70ae00698451997ae596a9A711")
TOKEN_DECIMALS = 6

# Arguments
PLS_RATIO = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
LOOPS = int(sys.argv[2]) if len(sys.argv) > 2 else 1100
PLS_THRESHOLD = (LOOPS / 1000.0) * PLS_RATIO * 1000

w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not PRIVATE_KEY:
    print("❌ Error: KEY environment variable not set.")
    sys.exit(1)

account = Account.from_key(PRIVATE_KEY)

# ABIs
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}]}
]
MAIN_ABI = [{"inputs":[],"stateMutability":"nonpayable","type":"constructor"},{"inputs":[],"name":"affection","outputs":[{"internalType":"contract IAffection","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"math","outputs":[{"internalType":"contract IMath","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"_loops","type":"uint256"}],"name":"multiGenerate","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"_loops","type":"uint256"}],"name":"multiRandom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"_loops","type":"uint256"}],"name":"ultimateSequence","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"_token","type":"address"}],"name":"withdrawToken","outputs":[],"stateMutability":"nonpayable","type":"function"}]


token = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_ABI)
multimath = w3.eth.contract(address=MULTIMATH_ADDRESS, abi=MAIN_ABI)

# ------------------------------
# DIAGNOSTICS
# ------------------------------

def check_balances():
    print("="*60)
    print("ACCOUNT DIAGNOSTICS")
    print("="*60)
    
    pls_balance = w3.eth.get_balance(ACCOUNT_ADDRESS)
    print(f"💰 PLS Balance: {pls_balance / 1e18:,.0f} PLS")
    
    try:
        symbol = token.functions.symbol().call()
        token_bal = token.functions.balanceOf(ACCOUNT_ADDRESS).call()
        allowance = token.functions.allowance(ACCOUNT_ADDRESS, MULTIMATH_ADDRESS).call()
        
        print(f"🪙 Token: {symbol}")
        print(f"   Balance:   {token_bal / (10**TOKEN_DECIMALS):,.2f}")
        print(f"   Allowance: {allowance / (10**TOKEN_DECIMALS):,.2f}")
        
        if allowance < token_bal:
            print("⚠️  Warning: Allowance is less than balance.")
    except Exception as e:
        print(f"❌ Diagnostic Error: {e}")
    print("="*60 + "\n")

# ------------------------------
# CORE ENGINE
# ------------------------------

def get_gas_params():
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', w3.eth.gas_price)
    priority_fee = w3.to_wei(2.5, 'gwei') 
    max_fee = int(base_fee * 1.5) + priority_fee
    return {"maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority_fee, "type": 2}

def run_multibuy(iteration):
    print(f"\n{'='*60}")
    print(f"Iteration #{iteration}")
    print(f"{'='*60}")

    confirmed_nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS, 'latest')
    pending_nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS, 'pending')
    
    if pending_nonce > confirmed_nonce:
        print(f"⏳ Waiting for Nonce {confirmed_nonce} to clear the mempool...")
        return False

    gas_prices = get_gas_params()
    
    # Gas Estimation with Linear Scaling
    try:
        est_batch = 100
        raw_est = multimath.functions.ultimateSequence(est_batch).estimate_gas({'from': ACCOUNT_ADDRESS})
        exec_only = raw_est - 21000
        gas_limit = int((21000 + (exec_only / est_batch) * LOOPS) * 1.1)
    except Exception as e:
        gas_limit = LOOPS * 3800 

    # Cost Calculation
    est_total_pls = (gas_limit * gas_prices['maxFeePerGas']) / 1e18*0.75
    
    print(f"📋 TX Details (Nonce {confirmed_nonce})")
    print(f"{'─'*60}")
    print(f"⛽ Gas Limit:      {gas_limit:,}")
    print(f"💰 Max Gas Price:  {gas_prices['maxFeePerGas']/1e9:,.2f} gwei")
    print(f"💵 Est. Max Cost:  {est_total_pls:,.2f} PLS")
    print(f"{'─'*60}")

    if (est_total_pls/PLS_THRESHOLD) > 1.035:
        print(f"🛑 Threshold Exceeded! {est_total_pls:.2f} > {PLS_THRESHOLD}. Waiting...")
        return False

    try:
        tx = multimath.functions.ultimateSequence(LOOPS).build_transaction({
            'from': ACCOUNT_ADDRESS,
            'nonce': confirmed_nonce,
            'gas': gas_limit,
            'chainId': 369,
            **gas_prices
        })
        
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"🚀 Sent: {tx_hash.hex()}")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

        # --- AFTER SUCCESSFUL RECEIPT ---
        actual_gas = receipt.get('gasUsed', 0)
        actual_price = receipt.get('effectiveGasPrice', 0)
        actual_cost = (actual_gas * actual_price) / 1e18
        
        # Affection Calculation: 100M / gasprice * #ofloops
        # Convert gas price to Gwei for the denominator to match standard "Affection" math
        gwei_price = actual_price / 1e9
        bought_affection = LOOPS

        print(f"\n{'='*60}")
        print(f"✅ TRANSACTION CONFIRMED")
        print(f"{'='*60}")
        print(f"📦 Block:          {receipt.blockNumber:,}")
        print(f"⛽ Gas Used:       {actual_gas:,.0f}")
        print(f"💰 Gas Price:      {gwei_price:,.0f} gwei")
        print(f"💵 Actual Cost:    {actual_cost:,.0f} PLS")
        print(f"💎 Affection:      {bought_affection:,.0f} tokens")
        print(f"{'─'*60}")
        buyrate = (100000000 / actual_cost) * LOOPS*3
        print(f"📊 Buy Rate: 100M PLS buys {buyrate:,.0f} Affection tokens")
        print(f"{'='*60}\n")
        
        return True

    except Exception as e:
        print(f"🧨 Error: {e}")
        time.sleep(5)
        return False

# ------------------------------
# MAIN LOOP
# ------------------------------
def signal_handler(sig, frame):
    print("\n👋 Shutdown requested.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🔗 PULSECHAIN MULTIBUY BOT")
    print(f"{'='*60}")
    print(f"👤 Account:    {ACCOUNT_ADDRESS}")
    print(f"🔄 Loops:      {LOOPS:,}")
    print(f"💰 Threshold:  {PLS_THRESHOLD:,.0f} PLS")
    buyrate = (100000000 / PLS_THRESHOLD) * LOOPS*3

    print(f"💝 Buy Rate: 100M PLS buys # Affection:  {buyrate:,.0f}")
    
    check_balances()
    
    iteration = 1
    while True:
        success = run_multibuy(iteration)
        if success:
            iteration += 1
        time.sleep(3)