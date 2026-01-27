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
# Threshold is compared against the TOTAL cost of both txs
PLS_THRESHOLD = (LOOPS * 3 / 1000.0) * PLS_RATIO * 1000

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

def get_estimation(func_name):
    try:
        est_batch = min(LOOPS, 100)
        if func_name == "multiGenerate":
            raw_est = main_contract.functions.multiGenerate(est_batch).estimate_gas({'from': ACCOUNT_ADDRESS})
        else:
            raw_est = main_contract.functions.multiBuyWith(MATH_TOKEN, est_batch).estimate_gas({'from': ACCOUNT_ADDRESS})
        exec_only = raw_est - 21000
        return int((21000 + (exec_only / est_batch) * LOOPS) * 1.1)
    except:
        return LOOPS * 4500

def execute_tx(func_name, gas_limit, params, nonce):
    try:
        if func_name == "multiGenerate":
            fn = main_contract.functions.multiGenerate(LOOPS)
        else:
            fn = main_contract.functions.multiBuyWith(MATH_TOKEN, LOOPS)
            
        tx = fn.build_transaction({
            'from': ACCOUNT_ADDRESS,
            'nonce': nonce,
            'gas': gas_limit,
            'chainId': 369,
            **params
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=240)
    except Exception as e:
        print(f"🧨 {func_name} Failed: {e}")
        return None

# ------------------------------
# MAIN LOOP
# ------------------------------
def signal_handler(sig, frame):
    print(f"\n👋 Shutdown. Final Session Total: {session_affection_total:,} Affection.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print(f"🚀 Bot Started. Loops: {LOOPS} | Ratio: {PLS_RATIO} | Threshold: {PLS_THRESHOLD:.2f} PLS")
    ensure_approvals()
    
    while True:
        math_bal = math_contract.functions.balanceOf(ACCOUNT_ADDRESS).call()
        if math_bal == 0:
            print("🏁 No MATH balance left.")
            break

        # 1. Pre-Flight Summary for the Sequence
        params = get_gas_params()
        gen_gas = get_estimation("multiGenerate")
        buy_gas = get_estimation("multiBuyWith")
        total_gas = gen_gas + buy_gas
        
        est_total_pls = (total_gas * params['maxFeePerGas']) / 1e18
        
        print(f"\n🔍 --- Sequence Pre-Flight (Total for both calls) ---")
        print(f"⛽ Combined Gas Limit: {total_gas:,}")
        print(f"📊 Estimated Total:    {est_total_pls:.4f} PLS")
        print(f"🛡️ Your Threshold:     {PLS_THRESHOLD:.4f} PLS")

        if est_total_pls/PLS_THRESHOLD > 1.035:
            print(f"🛑 SKIPPED: Sequence cost is {est_total_pls - PLS_THRESHOLD:.4f} PLS over limit.")
            time.sleep(10)
            continue

        # 2. Execute Sequence
        nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS, 'latest')
        
        # Call 1
        rec1 = execute_tx("multiGenerate", gen_gas, params, nonce)
        if rec1 and rec1.status == 1:
            # Call 2 (increment nonce)
            rec2 = execute_tx("multiBuyWith", buy_gas, params, nonce + 1)
            
            if rec2 and rec2.status == 1:
                # 3. Final Summary Reporting
                total_actual_pls = ((rec1.gasUsed * rec1.effectiveGasPrice) + 
                                    (rec2.gasUsed * rec2.effectiveGasPrice)) / 1e18
                
                prod_affection = LOOPS * 3
                session_affection_total += prod_affection
                
                # Purchase Power Logic
                avg_gwei = ((rec1.effectiveGasPrice + rec2.effectiveGasPrice) / 2) / 1e9
                purchase_power = (100_000_000 / avg_gwei) * LOOPS

                print(f"\n{'='*60}")
                print(f"💎 SEQUENCE COMPLETE")
                print(f"{'─'*60}")
                print(f"⛽ Actual Gas Spent:   {total_actual_pls:.4f} PLS")
                print(f"📉 Math Spent:         (Loops applied)")
                print(f"💝 Affection Gained:   {prod_affection:,} tokens")
                print(f"📊 Purchasing Power:   100M PLS buys {purchase_power:,.0f} tokens")
                print(f"📈 Session Total:      {session_affection_total:,} Affection")
                print(f"{'='*60}\n")
            else:
                print("⚠️ Second call failed. Sequence broken.")
        else:
            print("⚠️ First call failed. Sequence aborted.")
        
        time.sleep(4)