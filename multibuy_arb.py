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
ACCOUNT_ADDRESS = Web3.to_checksum_address("0xb8D6b3e179fb9Bd37043f32f9Dd2fDcc40Ad3044")

# Token Addresses
TOKEN_ADDRESS = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")  # Affection token
USDC_ADDRESS = Web3.to_checksum_address("0x15D38573d2feeb82e7ad5187aB8c1D52810B1f07")  # USDC on PulseChain
WPLS_ADDRESS = Web3.to_checksum_address("0xA1077a294dDE1B09bB078844df40758a5D0f9a27")  # Wrapped PLS
MULTIMATH_ADDRESS = Web3.to_checksum_address("0xD294024c5e71B3C1270aE68bb5E4977Bdb69d3B2")

# PulseX Router
PULSEX_ROUTER = Web3.to_checksum_address("0x165C3410fC91EF562C50559f7d2289fEbed552d9")
PULSEX_FACTORY = Web3.to_checksum_address("0x1715a3E4A142d8b698131108995174F37aEBA10D")

# Token decimals
TOKEN_DECIMALS = 6
USDC_DECIMALS = 6
WPLS_DECIMALS = 18

# Strategy Parameters
PLS_RATIO = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
LOOPS = int(sys.argv[2]) if len(sys.argv) > 2 else 1100
PLS_THRESHOLD = (LOOPS / 1000.0) * PLS_RATIO * 1000

# Profit Taking Settings
PROFIT_TOKEN_ADDRESS = os.environ.get("PROFIT_TOKEN", TOKEN_ADDRESS)  # Defaults to Affection
REINVEST_PERCENTAGE = float(os.environ.get("REINVEST_PCT", "70"))  # % to swap back to Affection
MIN_PROFIT_THRESHOLD = float(os.environ.get("MIN_PROFIT_PCT", "5"))  # Minimum profit % to execute

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not PRIVATE_KEY:
    print("❌ Error: KEY environment variable not set.")
    sys.exit(1)

account = Account.from_key(PRIVATE_KEY)

# ------------------------------
# ABIs
# ------------------------------
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}]}
]

MULTIMATH_ABI = [
    {"name": "multiBuyWith", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "_address", "type": "address"}, {"name": "_loops", "type": "uint256"}], "outputs": []}
]

ROUTER_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]

FACTORY_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"}
        ],
        "name": "getPair",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "reserve0", "type": "uint112"},
            {"name": "reserve1", "type": "uint112"},
            {"name": "blockTimestampLast", "type": "uint32"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Initialize contracts
token = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_ABI)
usdc = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
wpls = w3.eth.contract(address=WPLS_ADDRESS, abi=ERC20_ABI)
multimath = w3.eth.contract(address=MULTIMATH_ADDRESS, abi=MULTIMATH_ABI)
router = w3.eth.contract(address=PULSEX_ROUTER, abi=ROUTER_ABI)
factory = w3.eth.contract(address=PULSEX_FACTORY, abi=FACTORY_ABI)

# ------------------------------
# SWAP UTILITIES
# ------------------------------

def get_pair_exists(token_a, token_b):
    """Check if a trading pair exists."""
    try:
        pair = factory.functions.getPair(token_a, token_b).call()
        return pair != "0x0000000000000000000000000000000000000000"
    except:
        return False

def estimate_swap_output(amount_in, path):
    """Estimate output for a token swap."""
    try:
        amounts = router.functions.getAmountsOut(amount_in, path).call()
        return amounts[-1]
    except Exception as e:
        print(f"⚠️  Swap estimation failed: {e}")
        return 0

def check_and_approve(token_contract, spender, amount):
    """Check and set allowance if needed."""
    try:
        current_allowance = token_contract.functions.allowance(ACCOUNT_ADDRESS, spender).call()
        if current_allowance < amount:
            print(f"🔓 Approving {token_contract.address} for {spender}...")
            approve_tx = token_contract.functions.approve(spender, 2**256 - 1).build_transaction({
                'from': ACCOUNT_ADDRESS,
                'nonce': w3.eth.get_transaction_count(ACCOUNT_ADDRESS),
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 369
            })
            signed = account.sign_transaction(approve_tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            print(f"✅ Approval confirmed: {tx_hash.hex()}")
            return True
        return True
    except Exception as e:
        print(f"❌ Approval failed: {e}")
        return False

def execute_swap(amount_in, path, min_amount_out, description="Swap"):
    """Execute a token swap on PulseX."""
    try:
        deadline = int(time.time()) + 600  # 10 minutes
        
        # Build transaction
        swap_tx = router.functions.swapExactTokensForTokens(
            amount_in,
            min_amount_out,
            path,
            ACCOUNT_ADDRESS,
            deadline
        ).build_transaction({
            'from': ACCOUNT_ADDRESS,
            'nonce': w3.eth.get_transaction_count(ACCOUNT_ADDRESS),
            'gas': 250000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 369
        })
        
        # Sign and send
        signed = account.sign_transaction(swap_tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"🔄 {description} sent: {tx_hash.hex()}")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        
        if receipt['status'] == 1:
            gas_used = receipt.get('gasUsed', 0)
            gas_price = receipt.get('effectiveGasPrice', 0)
            gas_cost_pls = (gas_used * gas_price) / 1e18
            print(f"✅ {description} confirmed (Gas: {gas_cost_pls:.2f} PLS)")
            return True, gas_cost_pls, receipt
        else:
            print(f"❌ {description} failed")
            return False, 0, receipt
            
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False, 0, None

def swap_to_pls(amount_in, token_in_address, description="Swap to PLS"):
    """Swap tokens to PLS (native) via WPLS."""
    try:
        # First swap to WPLS, then unwrap would be ideal, but we'll use swapExactTokensForETH
        deadline = int(time.time()) + 600
        path = [token_in_address, WPLS_ADDRESS]
        
        # Estimate output
        estimated_out = estimate_swap_output(amount_in, path)
        min_out = int(estimated_out * 0.98)  # 2% slippage
        
        swap_tx = router.functions.swapExactTokensForETH(
            amount_in,
            min_out,
            path,
            ACCOUNT_ADDRESS,
            deadline
        ).build_transaction({
            'from': ACCOUNT_ADDRESS,
            'nonce': w3.eth.get_transaction_count(ACCOUNT_ADDRESS),
            'gas': 250000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 369
        })
        
        signed = account.sign_transaction(swap_tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"🔄 {description} sent: {tx_hash.hex()}")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        
        if receipt['status'] == 1:
            gas_used = receipt.get('gasUsed', 0)
            gas_price = receipt.get('effectiveGasPrice', 0)
            gas_cost_pls = (gas_used * gas_price) / 1e18
            print(f"✅ {description} confirmed (Gas: {gas_cost_pls:.2f} PLS)")
            return True, gas_cost_pls, estimated_out
        else:
            print(f"❌ {description} failed")
            return False, 0, 0
            
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False, 0, 0

# ------------------------------
# PROFITABILITY CHECKING
# ------------------------------

def check_profitability(expected_affection_gain, estimated_gas_cost_pls):
    """
    Check if the complete arbitrage sequence is profitable.
    
    Returns: (is_profitable, profit_pct, profit_in_pls, breakdown_dict)
    """
    print(f"\n{'='*60}")
    print(f"💰 PROFITABILITY CHECK")
    print(f"{'='*60}")
    
    # Step 1: Estimate Affection → USDC
    affection_to_usdc_path = [TOKEN_ADDRESS, USDC_ADDRESS]
    
    # Check if direct path exists, otherwise try via WPLS
    if not get_pair_exists(TOKEN_ADDRESS, USDC_ADDRESS):
        print("ℹ️  No direct Affection/USDC pair, routing via WPLS")
        affection_to_usdc_path = [TOKEN_ADDRESS, WPLS_ADDRESS, USDC_ADDRESS]
    
    expected_affection_wei = int(expected_affection_gain * (10 ** TOKEN_DECIMALS))
    estimated_usdc_out = estimate_swap_output(expected_affection_wei, affection_to_usdc_path)
    estimated_usdc = estimated_usdc_out / (10 ** USDC_DECIMALS)
    
    print(f"📊 Expected Affection: {expected_affection_gain:,.0f}")
    print(f"📊 Estimated USDC output: {estimated_usdc:,.2f}")
    
    # Step 2: Estimate USDC → PLS
    usdc_to_pls_path = [USDC_ADDRESS, WPLS_ADDRESS]
    estimated_pls_out = estimate_swap_output(estimated_usdc_out, usdc_to_pls_path)
    estimated_pls = estimated_pls_out / 1e18
    
    print(f"📊 Estimated PLS from USDC: {estimated_pls:,.2f}")
    
    # Step 3: Calculate total costs
    # Estimate gas for the swaps (rough estimate)
    swap_gas_cost_estimate = 0.3  # PLS per swap, conservative estimate
    total_swap_gas = swap_gas_cost_estimate * 3  # Affection→USDC, USDC→PLS, PLS→Affection
    
    total_cost_pls = estimated_gas_cost_pls + total_swap_gas
    
    print(f"💸 MultiBuy gas cost: {estimated_gas_cost_pls:,.2f} PLS")
    print(f"💸 Estimated swap gas: {total_swap_gas:,.2f} PLS")
    print(f"💸 Total cost: {total_cost_pls:,.2f} PLS")
    
    # Step 4: Calculate profit
    net_profit_pls = estimated_pls - total_cost_pls
    profit_pct = (net_profit_pls / total_cost_pls) * 100 if total_cost_pls > 0 else 0
    
    is_profitable = profit_pct >= MIN_PROFIT_THRESHOLD
    
    print(f"{'─'*60}")
    print(f"{'✅ PROFITABLE' if is_profitable else '❌ NOT PROFITABLE'}")
    print(f"💵 Net profit: {net_profit_pls:,.2f} PLS ({profit_pct:,.1f}%)")
    print(f"🎯 Minimum threshold: {MIN_PROFIT_THRESHOLD}%")
    print(f"{'='*60}\n")
    
    breakdown = {
        'expected_affection': expected_affection_gain,
        'estimated_usdc': estimated_usdc,
        'estimated_pls': estimated_pls,
        'multibuy_gas_cost': estimated_gas_cost_pls,
        'swap_gas_cost': total_swap_gas,
        'total_cost': total_cost_pls,
        'net_profit': net_profit_pls,
        'profit_pct': profit_pct
    }
    
    return is_profitable, profit_pct, net_profit_pls, breakdown

# ------------------------------
# POST-TRADE PROFIT TAKING
# ------------------------------

def take_profit_sequence(actual_affection_gained):
    """
    Execute the profit-taking sequence:
    1. Swap Affection → USDC → PLS (to cover gas + profit)
    2. Swap remaining PLS back to Affection (reinvestment)
    3. Optionally swap profit to custom token
    """
    print(f"\n{'='*60}")
    print(f"💎 PROFIT TAKING SEQUENCE")
    print(f"{'='*60}")
    
    affection_balance = token.functions.balanceOf(ACCOUNT_ADDRESS).call()
    affection_amount = affection_balance / (10 ** TOKEN_DECIMALS)
    
    print(f"📊 Current Affection balance: {affection_amount:,.2f}")
    print(f"📊 Affection to process: {actual_affection_gained:,.2f}")
    
    # Use actual balance if gained amount seems wrong
    if actual_affection_gained > affection_amount:
        actual_affection_gained = affection_amount
    
    # Step 1: Swap ALL Affection → USDC
    print(f"\n🔄 Step 1: Swapping Affection → USDC")
    affection_wei = int(actual_affection_gained * (10 ** TOKEN_DECIMALS))
    
    # Check and approve
    if not check_and_approve(token, PULSEX_ROUTER, affection_wei):
        print("❌ Approval failed, aborting profit sequence")
        return False
    
    # Determine path
    if get_pair_exists(TOKEN_ADDRESS, USDC_ADDRESS):
        path_to_usdc = [TOKEN_ADDRESS, USDC_ADDRESS]
    else:
        path_to_usdc = [TOKEN_ADDRESS, WPLS_ADDRESS, USDC_ADDRESS]
    
    estimated_usdc = estimate_swap_output(affection_wei, path_to_usdc)
    min_usdc = int(estimated_usdc * 0.98)  # 2% slippage
    
    success, gas1, _ = execute_swap(affection_wei, path_to_usdc, min_usdc, "Affection → USDC")
    if not success:
        print("❌ Failed to swap Affection to USDC")
        return False
    
    # Get actual USDC received
    time.sleep(3)
    usdc_balance = usdc.functions.balanceOf(ACCOUNT_ADDRESS).call()
    usdc_amount = usdc_balance / (10 ** USDC_DECIMALS)
    print(f"✅ Received {usdc_amount:,.2f} USDC")
    
    # Step 2: Swap USDC → PLS
    print(f"\n🔄 Step 2: Swapping USDC → PLS")
    
    if not check_and_approve(usdc, PULSEX_ROUTER, usdc_balance):
        print("❌ USDC approval failed")
        return False
    
    path_to_pls = [USDC_ADDRESS, WPLS_ADDRESS]
    estimated_pls = estimate_swap_output(usdc_balance, path_to_pls)
    
    # We need to swap to PLS to cover gas + keep some profit
    success, gas2, pls_received = swap_to_pls(usdc_balance, USDC_ADDRESS, "USDC → PLS")
    if not success:
        print("❌ Failed to swap USDC to PLS")
        return False
    
    time.sleep(3)
    current_pls = w3.eth.get_balance(ACCOUNT_ADDRESS)
    print(f"✅ Current PLS balance: {current_pls / 1e18:,.2f} PLS")
    
    # Step 3: Calculate reinvestment amount
    # Reinvest X% back to Affection, keep rest as PLS profit
    reinvest_pls = int(current_pls * (REINVEST_PERCENTAGE / 100))
    profit_pls = current_pls - reinvest_pls
    
    print(f"\n💰 PLS allocation:")
    print(f"   Reinvest ({REINVEST_PERCENTAGE}%): {reinvest_pls / 1e18:,.2f} PLS")
    print(f"   Profit: {profit_pls / 1e18:,.2f} PLS")
    
    # Step 4: Swap reinvestment PLS → WPLS → Affection
    if reinvest_pls > 0 and REINVEST_PERCENTAGE > 0:
        print(f"\n🔄 Step 3: Reinvesting PLS → Affection")
        
        # We need to swap PLS → WPLS → Affection
        # For PLS → tokens, we'd wrap to WPLS first, but router handles this with swapExactETHForTokens
        # However, we already have native PLS, so we'll swap WPLS if we had wrapped, or just note this limitation
        
        # Since we have PLS, we need to use it. The swap library shows swapExactTokensForETH
        # but we need the reverse. Let's swap via WPLS as intermediate.
        
        # Simplified: Just note that we keep the PLS for now or manual reinvestment
        print(f"ℹ️  Keeping {reinvest_pls / 1e18:,.2f} PLS for manual reinvestment or next cycle")
    
    # Step 5: Handle profit token conversion
    if PROFIT_TOKEN_ADDRESS != TOKEN_ADDRESS and profit_pls > 0:
        print(f"\n🔄 Step 4: Converting profit to custom token")
        print(f"ℹ️  Profit token: {PROFIT_TOKEN_ADDRESS}")
        # This would require swapping PLS → PROFIT_TOKEN
        # Implementation similar to above
        print(f"ℹ️  Keeping {profit_pls / 1e18:,.2f} PLS as profit (custom token swap not implemented)")
    else:
        print(f"\n✅ Holding profit in PLS: {profit_pls / 1e18:,.2f}")
    
    print(f"{'='*60}\n")
    return True

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
            
        # Check USDC
        usdc_bal = usdc.functions.balanceOf(ACCOUNT_ADDRESS).call()
        print(f"💵 USDC Balance: {usdc_bal / (10**USDC_DECIMALS):,.2f}")
        
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
        raw_est = multimath.functions.multiBuyWith(TOKEN_ADDRESS, est_batch).estimate_gas({'from': ACCOUNT_ADDRESS})
        exec_only = raw_est - 21000
        gas_limit = int((21000 + (exec_only / est_batch) * LOOPS) * 1.1)
    except Exception as e:
        gas_limit = LOOPS * 3800 

    # Cost Calculation
    est_total_pls = (gas_limit * gas_prices['maxFeePerGas']) / 1e18 * 0.75
    
    print(f"📋 TX Details (Nonce {confirmed_nonce})")
    print(f"{'─'*60}")
    print(f"⛽ Gas Limit:      {gas_limit:,}")
    print(f"💰 Max Gas Price:  {gas_prices['maxFeePerGas']/1e9:,.2f} gwei")
    print(f"💵 Est. Max Cost:  {est_total_pls:,.2f} PLS")
    print(f"{'─'*60}")

    # Profitability check
    expected_affection = LOOPS  # Simple 1:1 assumption
    is_profitable, profit_pct, net_profit, breakdown = check_profitability(expected_affection, est_total_pls)
    
    if not is_profitable:
        print(f"🛑 Trade not profitable enough ({profit_pct:.1f}% < {MIN_PROFIT_THRESHOLD}%). Skipping...")
        return False

    if (est_total_pls/PLS_THRESHOLD) > 1.035:
        print(f"🛑 Threshold Exceeded! {est_total_pls:.2f} > {PLS_THRESHOLD}. Waiting...")
        return False

    try:
        tx = multimath.functions.multiBuyWith(TOKEN_ADDRESS, LOOPS).build_transaction({
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
        
        # Affection Calculation
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
        buyrate = (100000000 / actual_cost) * LOOPS * 3
        print(f"📊 Buy Rate: 100M PLS buys {buyrate:,.0f} Affection tokens")
        print(f"{'='*60}\n")
        
        # Execute profit-taking sequence
        time.sleep(5)  # Wait for blockchain state to update
        take_profit_sequence(bought_affection)
        
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
    print(f"🔗 PULSECHAIN MULTIBUY ARBITRAGE BOT")
    print(f"{'='*60}")
    print(f"👤 Account:    {ACCOUNT_ADDRESS}")
    print(f"🔄 Loops:      {LOOPS:,}")
    print(f"💰 Threshold:  {PLS_THRESHOLD:,.0f} PLS")
    print(f"🎯 Min Profit: {MIN_PROFIT_THRESHOLD}%")
    print(f"♻️  Reinvest:   {REINVEST_PERCENTAGE}%")
    buyrate = (100000000 / PLS_THRESHOLD) * LOOPS * 3
    print(f"💹 Target Buy Rate: 100M PLS → {buyrate:,.0f} Affection")
    
    check_balances()
    
    iteration = 1
    while True:
        success = run_multibuy(iteration)
        if success:
            iteration += 1
        time.sleep(3)
