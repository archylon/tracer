import os
import sys
import time
import signal
from decimal import Decimal
from web3 import Web3
from eth_account import Account

# ------------------------------
# CONFIGURATION
# ------------------------------
RPC_URL = os.environ.get("RPC_URL", "https://rpc.pulsechain.com")
PRIVATE_KEY = os.environ.get("KEY2")
ACCOUNT_ADDRESS = Web3.to_checksum_address("0x24dB019d2EB8f869698Cd5F2eCfB1DA9Ff92666B")

# Contract Addresses
MAIN_CONTRACT = Web3.to_checksum_address("0xCF138a83D739eE98D7A54159E94e5BFaa4B61988")
AFFECTION_TOKEN = Web3.to_checksum_address("0x24F0154C1dCe548AdF15da2098Fdd8B8A3B8151D")
MATH_TOKEN = Web3.to_checksum_address("0xB680F0cc810317933F234f67EB6A9E923407f05D")

# Inputs from CLI
PLS_RATIO = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
LOOPS = int(sys.argv[2]) if len(sys.argv) > 2 else 500
PLS_THRESHOLD = (LOOPS*3 / 1000.0) * PLS_RATIO * 1000

# Global Session Stats
session_affection_total = 0

w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not PRIVATE_KEY:
    print("❌ Error: KEY environment variable not set.")
    sys.exit(1)

account = Account.from_key(PRIVATE_KEY)

# ABIs
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}]}
]
MAIN_ABI = [
    {"name": "multiGenerate", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "loops", "type": "uint256"}], "outputs": []},
    {"name": "multiBuyWith", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "token", "type": "address"}, {"name": "loops", "type": "uint256"}], "outputs": []}
]

main_contract = w3.eth.contract(address=MAIN_CONTRACT, abi=MAIN_ABI)
math_contract = w3.eth.contract(address=MATH_TOKEN, abi=ERC20_ABI)
aff_contract = w3.eth.contract(address=AFFECTION_TOKEN, abi=ERC20_ABI)

# ------------------------------
# LOGIC ENGINE
# ------------------------------

def get_gas_params():
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', w3.eth.gas_price)
    priority_fee = w3.to_wei(2.5, 'gwei') 
    max_fee = int(base_fee * 1.5) + priority_fee
    return {"maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority_fee, "type": 2}

def ensure_approvals():
    for token_contract, name in [(math_contract, "MATH"), (aff_contract, "AFFECTION")]:
        allowance = token_contract.functions.allowance(ACCOUNT_ADDRESS, MAIN_CONTRACT).call()
        if allowance < (10**30):
            print(f"🔓 Approving {name}...")
            params = get_gas_params()
            tx = token_contract.functions.approve(MAIN_CONTRACT, 2**256 - 1).build_transaction({
                'from': ACCOUNT_ADDRESS,
                'nonce': w3.eth.get_transaction_count(ACCOUNT_ADDRESS),
                **params
            })
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"✅ {name} Approved.")

# ... [Keep previous imports and setup] ...

def execute_function(func_name, *args):
    global session_affection_total
    nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS, 'latest')
    params = get_gas_params()
    
    # 1. Precise Gas Estimation
    try:
        # Estimate based on a smaller batch to find the "per-loop" cost
        est_batch = min(LOOPS, 100)
        if func_name == "multiGenerate":
            raw_est = main_contract.functions.multiGenerate(est_batch).estimate_gas({'from': ACCOUNT_ADDRESS})
        else:
            raw_est = main_contract.functions.multiBuyWith(MATH_TOKEN, est_batch).estimate_gas({'from': ACCOUNT_ADDRESS})
            
        exec_only = raw_est - 21000
        gas_limit = int((21000 + (exec_only / est_batch) * LOOPS) * 1.1)
    except:
        gas_limit = LOOPS * 4500 # Fallback safety limit

    # 2. CALCULATION & COMPARISON BLOCK
    max_fee_gwei = params['maxFeePerGas'] / 1e9
    est_total_pls = (gas_limit * params['maxFeePerGas']) / 1e18
    
    print(f"\n🔍 --- {func_name} Pre-Flight Check ---")
    print(f"⛽ Gas Limit:       {gas_limit:,}")
    print(f"💹 Max Fee Rate:    {max_fee_gwei:,.2f} Gwei")
    print(f"📊 Estimated Cost:  {est_total_pls:.4f} PLS")
    print(f"🛡️ Your Threshold:  {PLS_THRESHOLD:.4f} PLS")
    
    if est_total_pls*0.5 > PLS_THRESHOLD:
        diff = est_total_pls - PLS_THRESHOLD
        print(f"🛑 SKIPPED: Transaction cost is {diff:.4f} PLS over your limit.")
        print(f"{'─'*40}")
        return False
    else:
        print(f"✅ WITHIN LIMIT: Proceeding with execution...")
        print(f"{'─'*40}")

    # 3. Execution (build and sign)
    try:
        fn = getattr(main_contract.functions, func_name)(*args)
        tx = fn.build_transaction({
            'from': ACCOUNT_ADDRESS,
            'nonce': nonce,
            'gas': gas_limit,
            'chainId': 369,
            **params
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=240)
        
        if receipt.status == 1:
            gwei_price = receipt.effectiveGasPrice / 1e9
            prod_affection = LOOPS * 3
            purchase_power = (100_000_000 / gwei_price) * LOOPS
            session_affection_total += prod_affection

            print(f"💎 SUCCESS: {prod_affection:,} Affection created.")
            print(f"📈 Session Total: {session_affection_total:,}")
            return True
        return False
    except Exception as e:
        print(f"🧨 Execution Error: {e}")
        return False

# ... [Rest of the loop logic] ...

# ------------------------------
# MAIN LOOP
# ------------------------------
def signal_handler(sig, frame):
    print(f"\n👋 Shutting down. Final Session Total: {session_affection_total:,} Affection tokens.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print(f"🚀 Bot Started. Target Loops: {LOOPS} | Ratio: {PLS_RATIO}")
    ensure_approvals()
    
    while True:
        math_bal = math_contract.functions.balanceOf(ACCOUNT_ADDRESS).call()
        if math_bal == 0:
            print("🏁 No MATH balance left. Bot Finished.")
            break

        # Call sequence
        if execute_function("multiGenerate", LOOPS):
            execute_function("multiBuyWith", MATH_TOKEN, LOOPS)
        
        time.sleep(4)