import os
import sys
import time
import signal
from decimal import Decimal
from web3 import Web3
from eth_account import Account

# Import Swapper library from magoob2 directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../magoob2'))
from swap import Swapper

# ------------------------------
# CONFIGURATION
# ------------------------------
RPC_URL = os.environ.get("RPC_URL", "https://rpc.pulsechain.com")
PRIVATE_KEY = os.environ.get("KEY")

# Token Addresses
TOKEN_ADDRESS = Web3.to_checksum_address("0x24F0154C1dCe548AdF15da2098Fdd8B8A3B8151D")  # Affection token
USDC_ADDRESS = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")  # USDC on PulseChain
WPLS_ADDRESS = Web3.to_checksum_address("0xA1077a294dDE1B09bB078844df40758a5D0f9a27")  # Wrapped PLS
MULTIMATH_ADDRESS = Web3.to_checksum_address("0x3dF517a0FaA3fe70ae00698451997ae596a9A711")  # Updated contract
PULSEX_ROUTER = Web3.to_checksum_address("0x165C3410fC91EF562C50559f7d2289fEbed552d9")

# Token decimals
TOKEN_DECIMALS = 18
USDC_DECIMALS = 6
WPLS_DECIMALS = 18

# Strategy Parameters
PLS_RATIO = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
LOOPS = int(sys.argv[2]) if len(sys.argv) > 2 else 1100
PLS_THRESHOLD = (LOOPS / 1000.0) * PLS_RATIO * 1000

# Profit Taking Settings
USDC_RECOVERY_PCT = 50 #float(os.environ.get("USDC_RECOVERY_PCT", "0"))  # % of profits to convert to USDC (0 = skip)
PROFIT_TOKEN = "AFFECTION" #os.environ.get("PROFIT_TOKEN", "PLS")  # "PLS", "AFFECTION", or token address
MIN_PROFIT_THRESHOLD = float(os.environ.get("MIN_PROFIT_PCT", ".5"))  # Minimum profit % to execute

# Initialize Web3 and Swapper
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not PRIVATE_KEY:
    print("❌ Error: KEY environment variable not set.")
    sys.exit(1)

account = Account.from_key(PRIVATE_KEY)
ACCOUNT_ADDRESS = account.address
swapper = Swapper(json_rpc_url=RPC_URL, private_key=PRIVATE_KEY)

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
    {
        "inputs": [{"internalType": "uint256", "name": "_loops", "type": "uint256"}],
        "name": "ultimateSequence",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Initialize contracts
token = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_ABI)
usdc = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
wpls = w3.eth.contract(address=WPLS_ADDRESS, abi=ERC20_ABI)
multimath = w3.eth.contract(address=MULTIMATH_ADDRESS, abi=MULTIMATH_ABI)

# ------------------------------
# SWAP UTILITIES (using Swapper library)
# ------------------------------

def get_pair_exists(token_a, token_b):
    """Check if a trading pair exists using Swapper library."""
    pair = swapper.get_pair_address(token_a, token_b)
    return pair is not None

def estimate_swap_output(amount_in_wei, path):
    """Estimate output for a token swap using Swapper library."""
    try:
        return swapper.getAmountsOut(amount_in_wei, path, base_units=True)
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
    """Execute a token swap using Swapper library."""
    try:
        deadline = int(time.time()) + 600
        
        swap_tx = swapper.router_contract.functions.swapExactTokensForTokens(
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

def swap_to_pls(amount_in_wei, token_in_address, description="Swap to PLS"):
    """Swap tokens to PLS using swapExactTokensForETH."""
    try:
        deadline = int(time.time()) + 600
        path = [token_in_address, WPLS_ADDRESS]
        
        estimated_out = estimate_swap_output(amount_in_wei, path)
        min_out = int(estimated_out * 0.98)
        
        # Use swapExactTokensForETH from router
        swap_tx = swapper.router_contract.functions.swapExactTokensForETH(
            amount_in_wei,
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
            actual_pls_out = estimated_out / 1e18
            print(f"✅ {description} confirmed (Gas: {gas_cost_pls:.2f} PLS, Got: ~{actual_pls_out:.2f} PLS)")
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
    Check if the arbitrage is profitable.
    
    ultimateSequence: 1 USDC per loop → 1 Affection per loop
    Profit = (Affection Market Value in PLS) - (USDC Cost in PLS) - (Gas in PLS)
    """
    print(f"\n{'='*60}")
    print(f"💰 PROFITABILITY CHECK (All values in PLS)")
    print(f"{'='*60}")
    
    # USDC spent (1 per loop)
    usdc_spent = expected_affection_gain
    
    # Determine best path for Affection → USDC
    affection_to_usdc_path = [TOKEN_ADDRESS, USDC_ADDRESS]
    if not get_pair_exists(TOKEN_ADDRESS, USDC_ADDRESS):
        print("ℹ️  No direct Affection/USDC pair, routing via WPLS")
        affection_to_usdc_path = [TOKEN_ADDRESS, WPLS_ADDRESS, USDC_ADDRESS]
    
    # Estimate Affection market value
    expected_affection_wei = int(expected_affection_gain * (10 ** TOKEN_DECIMALS))
    estimated_usdc_out_wei = estimate_swap_output(expected_affection_wei, affection_to_usdc_path)
    market_value_usdc = estimated_usdc_out_wei / (10 ** USDC_DECIMALS)
    market_value_usdc = 1.9*LOOPS

    # Convert to PLS
    usdc_to_pls_path = [USDC_ADDRESS, WPLS_ADDRESS]
    market_value_pls_wei = estimate_swap_output(market_value_usdc*(10**USDC_DECIMALS), usdc_to_pls_path)
    market_value_pls = market_value_pls_wei / 1e18

    # USDC cost in PLS
    usdc_spent_wei = int(usdc_spent * (10 ** USDC_DECIMALS))
    usdc_spent_pls_wei = estimate_swap_output(usdc_spent_wei, usdc_to_pls_path)
    usdc_spent_pls = usdc_spent_pls_wei / 1e18
    
    # Total costs
    swap_gas_pls = 0.25 * 3
    total_gas_pls = estimated_gas_cost_pls + swap_gas_pls
    total_costs_pls = usdc_spent_pls + total_gas_pls
    
    print(f"📊 COSTS:")
    print(f"   USDC spent:               {usdc_spent:,.2f} USDC (≈ {usdc_spent_pls:,.2f} PLS)")
    print(f"   MultiBuy gas:             {estimated_gas_cost_pls:,.2f} PLS")
    print(f"   Swap gas (est):           {swap_gas_pls:,.2f} PLS")
    print(f"   ────────────────────────────────")
    print(f"   TOTAL COSTS:              {total_costs_pls:,.2f} PLS")
    
    print(f"\n📊 REVENUE:")
    print(f"   Affection tokens:         {expected_affection_gain:,.0f}")
    print(f"   Market value:             {market_value_usdc:,.2f} USDC")
    print(f"   Market value (PLS):       {market_value_pls:,.2f} PLS")
    
    # Profit calculation
    gross_profit_pls = market_value_pls - usdc_spent_pls
    net_profit_pls = market_value_pls - total_costs_pls
    profit_pct = (net_profit_pls / total_costs_pls) * 100 if total_costs_pls > 0 else 0
    arbitrage_pct = (gross_profit_pls / usdc_spent_pls) * 100 if usdc_spent_pls > 0 else 0
    
    is_profitable = profit_pct >= MIN_PROFIT_THRESHOLD
    
    print(f"\n💰 PROFIT ANALYSIS:")
    print(f"   Gross arb profit:         {gross_profit_pls:,.2f} PLS ({arbitrage_pct:,.1f}%)")
    print(f"   Minus gas:                {total_gas_pls:,.2f} PLS")
    print(f"   ────────────────────────────────")
    print(f"   NET PROFIT:               {net_profit_pls:,.2f} PLS")
    print(f"   ROI:                      {profit_pct:,.1f}%")
    
    print(f"\n{'─'*60}")
    print(f"{'✅ PROFITABLE' if is_profitable else '❌ NOT PROFITABLE'}")
    print(f"💵 Net profit: {net_profit_pls:,.2f} PLS ({profit_pct:,.1f}%)")
    print(f"🎯 Threshold: {MIN_PROFIT_THRESHOLD}%")
    print(f"{'='*60}\n")
    
    breakdown = {
        'expected_affection': expected_affection_gain,
        'usdc_spent': usdc_spent,
        'usdc_spent_pls': usdc_spent_pls,
        'market_value_usdc': market_value_usdc,
        'market_value_pls': market_value_pls,
        'total_costs_pls': total_costs_pls,
        'net_profit_pls': net_profit_pls,
        'profit_pct': profit_pct
    }
    
    return is_profitable, profit_pct, net_profit_pls, breakdown

# ------------------------------
# PROFIT TAKING SEQUENCE
# ------------------------------

def take_profit_sequence(actual_affection_gained, total_gas_spent_pls):
    """
    Execute 2-3 step profit sequence:
    1. Recover gas in PLS
    2. (Optional) Convert some to USDC  
    3. Take profit in chosen token
    """
    print(f"\n{'='*60}")
    print(f"💎 PROFIT TAKING SEQUENCE")
    print(f"{'='*60}")
    
    affection_balance = token.functions.balanceOf(ACCOUNT_ADDRESS).call()
    affection_amount = affection_balance / (10 ** TOKEN_DECIMALS)
    
    print(f"📊 Affection balance: {affection_amount:,.2f}")
    print(f"💸 Gas spent: {total_gas_spent_pls:,.2f} PLS")
    
    total_affection = min(affection_balance, int(actual_affection_gained * (10 ** TOKEN_DECIMALS)))
    
    if not check_and_approve(token, PULSEX_ROUTER, total_affection):
        print("❌ Approval failed")
        return False
    
    # Step 1: Recover Gas
    print(f"\n{'─'*60}")
    print(f"STEP 1: Recover Gas ({total_gas_spent_pls:,.2f} PLS)")
    print(f"{'─'*60}")
    
    gas_recovery_path = [TOKEN_ADDRESS, WPLS_ADDRESS] if get_pair_exists(TOKEN_ADDRESS, WPLS_ADDRESS) else [TOKEN_ADDRESS, USDC_ADDRESS, WPLS_ADDRESS]
    
    # Estimate how much Affection needed
    target_pls_wei = int(total_gas_spent_pls * 1e18)
    affection_for_gas_wei = int(total_affection * 0.10)
    
    for _ in range(5):
        est_pls = estimate_swap_output(affection_for_gas_wei, gas_recovery_path)
        if est_pls == 0:
            break
        ratio = target_pls_wei / est_pls if est_pls > 0 else 1
        affection_for_gas_wei = int(affection_for_gas_wei * ratio)
        if abs(est_pls - target_pls_wei) / target_pls_wei < 0.05:
            break
    
    
    print(f"💱 Swapping {affection_for_gas_wei/(10**TOKEN_DECIMALS):,.2f} Affection → PLS")
    
    success, _, _ = swap_to_pls(affection_for_gas_wei, TOKEN_ADDRESS, "Affection → PLS (gas)")
    remaining_affection = actual_affection_gained*10**18 - affection_for_gas_wei # from the minting.
    print(f"✅ Remaining: {remaining_affection/(10**TOKEN_DECIMALS):,.2f} Affection from mint")
    time.sleep(3)
    
    # Step 2: Optional USDC conversion
    if USDC_RECOVERY_PCT > 0:
        print(f"\n{'─'*60}")
        print(f"STEP 2: Convert to USDC ({USDC_RECOVERY_PCT}%)")
        print(f"{'─'*60}")
        
        affection_for_usdc_wei = int(remaining_affection * (USDC_RECOVERY_PCT / 100))
        usdc_path = [TOKEN_ADDRESS, USDC_ADDRESS] if get_pair_exists(TOKEN_ADDRESS, USDC_ADDRESS) else [TOKEN_ADDRESS, WPLS_ADDRESS, USDC_ADDRESS]
        
        est_usdc = estimate_swap_output(affection_for_usdc_wei, usdc_path)
        min_usdc = int(est_usdc * 0.98)
        
        print(f"💱 Swapping {affection_for_usdc_wei/(10**TOKEN_DECIMALS):,.2f} Affection → {min_usdc/(10**TOKEN_DECIMALS):.0f} USDC")
        
        success, _, _ = execute_swap(affection_for_usdc_wei, usdc_path, min_usdc, "Affection → USDC")
        remaining_affection = remaining_affection - affection_for_usdc_wei if success else remaining_affection
        
        time.sleep(3)
    
    # Step 3: Take profit
    print(f"\n{'─'*60}")
    print(f"STEP 3: Take Profit ({PROFIT_TOKEN})")
    print(f"{'─'*60}")
    
    profit_affection = remaining_affection / (10 ** TOKEN_DECIMALS)
    print(f"💎 Profit: {profit_affection:,.2f} Affection")
    
    if PROFIT_TOKEN.upper() == "AFFECTION":
        print(f"✅ Holding as Affection")
    elif PROFIT_TOKEN.upper() == "PLS":
        print(f"💱 Converting to PLS...")
        swap_to_pls(remaining_affection, TOKEN_ADDRESS, "Affection → PLS (profit)")
    else:
        print(f"💱 Converting to {PROFIT_TOKEN}...")
        # Custom token swap logic here
    
    print(f"\n{'='*60}")
    print(f"✅ PROFIT SEQUENCE COMPLETE")
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
    print(f"💰 PLS: {pls_balance / 1e18:,.2f} PLS")
    
    try:
        token_bal = token.functions.balanceOf(ACCOUNT_ADDRESS).call()
        usdc_bal = usdc.functions.balanceOf(ACCOUNT_ADDRESS).call()
        
        print(f"💎 Affection: {token_bal / (10**TOKEN_DECIMALS):,.2f}")
        print(f"💵 USDC: {usdc_bal / (10**USDC_DECIMALS):,.2f} USDC")
    except Exception as e:
        print(f"❌ Error: {e}")
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
        print(f"⏳ Waiting for nonce {confirmed_nonce}...")
        return False

    # Check USDC before
    usdc_before = usdc.functions.balanceOf(ACCOUNT_ADDRESS).call() / (10 ** USDC_DECIMALS)
    
    gas_prices = gas_params = get_gas_params()

    # Gas Estimation with Linear Scaling
    # try:
    #     est_batch = 100
    #     raw_est = multimath.functions.ultimateSequence(est_batch).estimate_gas({'from': ACCOUNT_ADDRESS})
    #     exec_only = raw_est - 21000
    #     gas_limit = int((21000 + (exec_only / est_batch) * LOOPS) * 1.1)
    # except Exception as e:
    #     gas_limit = LOOPS * 3800 


    # Gas Estimation with safety margins
    # Gas Estimation with Linear Scaling
    try:
        est_batch = 100
        raw_est = multimath.functions.ultimateSequence(est_batch).estimate_gas({'from': ACCOUNT_ADDRESS})
        exec_only = raw_est - 21000
        gas_limit = int((21000 + (exec_only / est_batch) * LOOPS) * 1.1)
    except Exception as e:
        gas_limit = LOOPS * 3800 

    # Cost Calculation    
    
    est_total_pls = (gas_limit * gas_prices['maxFeePerGas']) / 1e18*0.3
    
    print(f"📋 TX Details (Nonce {confirmed_nonce})")
    print(f"{'─'*60}")
    print(f"⛽ Gas Limit:      {gas_limit:,}")
    print(f"💰 Gas Price:      {gas_prices['maxFeePerGas']/1e9:,.2f} gwei")
    print(f"💵 Est Gas Cost:   {est_total_pls:,.2f} PLS")
    print(f"💵 USDC Balance:   {usdc_before:,.2f} USDC")
    print(f"💵 USDC to spend:  {LOOPS:,.0f} USDC (1 per loop)")
    print(f"{'─'*60}")

    # Profitability check
    is_profitable, profit_pct, net_profit, breakdown = check_profitability(LOOPS, est_total_pls)
    
    if not is_profitable and not "--force" in sys.argv:
        print(f"🛑 Not profitable ({profit_pct:.1f}% < {MIN_PROFIT_THRESHOLD}%)")
        return False

    if (est_total_pls/PLS_THRESHOLD) > 1.035 and not "--force" in sys.argv:
        print(f"🛑 Threshold exceeded! {est_total_pls:.2f} > {PLS_THRESHOLD}")
        return False

#try:
    tx = multimath.functions.ultimateSequence(LOOPS).build_transaction({
        'from': ACCOUNT_ADDRESS,
        'nonce': confirmed_nonce,
        'gas': gas_limit,
        'chainId': 369,
        **gas_params
    })
    
    # Print full transaction details before sending
    print(f"\n{'='*60}")
    print(f"📤 TRANSACTION DATA")
    print(f"{'='*60}")
    print(f"From:          {tx['from']}")
    print(f"To:            {tx['to']}")
    print(f"Nonce:         {tx['nonce']}")
    print(f"Chain ID:      {tx['chainId']}")
    print(f"Gas Limit:     {tx['gas']:,}")
    
    if 'gasPrice' in tx:
        # Legacy transaction
        print(f"Gas Price:     {tx['gasPrice']:,} wei ({tx['gasPrice']/1e9:,.2f} gwei)")
        print(f"Max Cost:      {(tx['gas'] * tx['gasPrice'])/1e18:,.4f} PLS")
        print(f"Type:          Legacy")
    else:
        # EIP-1559 transaction
        print(f"Max Fee:       {tx['maxFeePerGas']:,} wei ({tx['maxFeePerGas']/1e9:,.2f} gwei)")
        print(f"Priority Fee:  {tx['maxPriorityFeePerGas']:,} wei ({tx['maxPriorityFeePerGas']/1e9:,.2f} gwei)")
        print(f"Max Cost:      {(tx['gas'] * tx['maxFeePerGas'])/1e18:,.4f} PLS")
        print(f"Type:          EIP-1559 (Type 2)")
    
    print(f"Value:         {tx.get('value', 0)} wei")
    print(f"Data length:   {len(tx.get('data', '0x'))} bytes")
    print(f"{'='*60}\n")
    
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"🚀 Sent: {tx_hash.hex()}")
        
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    # Results
    actual_gas = receipt.get('gasUsed', 0)
    actual_price = receipt.get('effectiveGasPrice', 0)
    actual_cost_pls = (actual_gas * actual_price) / 1e18
    
    time.sleep(3)
    usdc_after = usdc.functions.balanceOf(ACCOUNT_ADDRESS).call() / (10 ** USDC_DECIMALS)
    actual_usdc_spent = usdc_before - usdc_after
    
    affection_balance = token.functions.balanceOf(ACCOUNT_ADDRESS).call()
    affection_received = affection_balance / (10 ** TOKEN_DECIMALS)

    print(f"\n{'='*60}")
    print(f"✅ CONFIRMED")
    print(f"{'='*60}")
    print(f"📦 Block:          {receipt.blockNumber:,}")
    print(f"⛽ Gas Used:       {actual_gas:,.0f}")
    print(f"💵 Gas Cost:       {actual_cost_pls:,} PLS")
    print(f"💵 USDC spent:     {actual_usdc_spent:,} USDC")
    print(f"💎 Affection Balance:  {affection_received:,}")
    print(f"{'='*60}\n")
    
    # Execute profit sequence
    time.sleep(5)
    take_profit_sequence(LOOPS, actual_cost_pls)
    
    return True

    # except Exception as e:
    #     print(f"🧨 Error: {e}")
    #     time.sleep(5)
    #     return False

# ------------------------------
# MAIN LOOP
# ------------------------------

def signal_handler(sig, frame):
    print("\n👋 Shutdown requested.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🔗 PULSECHAIN MULTIBUY ARB BOT (with Swapper library)")
    print(f"{'='*60}")
    print(f"👤 Account:        {ACCOUNT_ADDRESS}")
    print(f"🔄 Loops:          {LOOPS:,}")
    print(f"💰 Gas Threshold:  {PLS_THRESHOLD:,.0f} PLS")
    print(f"🎯 Min Profit:     {MIN_PROFIT_THRESHOLD}%")
    print(f"💎 Profit Token:   {PROFIT_TOKEN}")
    
    check_balances()
    
    iteration = 1
    while True:
        success = run_multibuy(iteration)
        if success:
            iteration += 1
        time.sleep(3)
