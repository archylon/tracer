from web3 import Web3
import json
import os
import sys
from web3 import Web3


def ensure_approval(token_address, spender_address, amount_required):
    """
    Checks if MY_CONTRACT is allowed to spend TBILLs from my wallet.
    If not, it sends an approval transaction.
    """
    # 1. Setup the Token Contract
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    
    # 2. Check current allowance
    current_allowance = token_contract.functions.allowance(
        account.address, 
        spender_address
    ).call()
    
    if current_allowance >= amount_required:
        print(f"✅ Already approved: {current_allowance} is enough.")
        return True

    # 3. Build the Approval Transaction
    print(f"⚠️ Approval needed. Approving {amount_required} tokens...")
    
    # Use 'unlimited' approval to save gas on future trips? 
    # Max uint256: 2**256 - 1
    approve_tx = token_contract.functions.approve(
        spender_address, 
        amount_required 
    ).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 100000, # Approvals are cheap
        'gasPrice': w3.eth.gas_price
    })

    # 4. Sign and Send
    signed_tx = w3.eth.account.sign_transaction(approve_tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    
    # 5. Wait for confirmation
    print(f"⏳ Waiting for approval... {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("🚀 Approval confirmed!")
    return True

if __name__ == "__main__":
    # 1. SETUP
    RPC_URL = "https://safe.piteas.io"
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    private_key = os.environ.get("KEY")
    account = w3.eth.account.from_key(private_key)

    # 2. ADDRESSES (CLI Arguments)
    MY_CONTRACT = sys.argv[1]
    FLASH_POOL = sys.argv[2]   # Deep pool to borrow TBILL (e.g. PLS/TBILL)
    PUMP_POOL = sys.argv[3]    # Thin pool to pump (e.g. FED/TBILL)
    MINT_CONTRACT = sys.argv[4]
    TBILL_ADDRESS = sys.argv[5]
    FED_ADDRESS = sys.argv[6]  # NEW: Need the token you are dumping
    DUMP_POOL = sys.argv[7]    # NEW: Usually the same as PUMP_POOL

    # 3. MISSION PARAMETERS
    borrow_amount = w3.to_wei(150000, 'ether')
    repay_amount = int(borrow_amount * 1.0031) # 0.3% PulseX fee + margin
    
    # 4. ENCODE THE PUMP (Buy FED with borrowed TBILL)
    # Adjust args[0] or args[1] based on whether FED is token0 or token1
    pump_data = w3.eth.contract(address=PUMP_POOL, abi=PAIR_ABI).encodeABI(
        fn_name="swap",
        args=[w3.to_wei(5000, 'ether'), 0, MY_CONTRACT, b''] 
    )

    # 5. ENCODE THE MINT
    mint_data = w3.eth.contract(address=MINT_CONTRACT, abi=MINT_ABI).encodeABI(
        fn_name="mint", 
        args=[w3.to_wei(140000, 'ether')] # Use remaining borrowed TBILL
    )

    # 6. ENCODE THE DUMP (Sell FED for TBILL)
    # We calculate the amountOut using the constant product formula or a simple target
    # For a 'Guerilla' trip, we request the exact amount needed to repay + profit
    expected_tbill_out = repay_amount + w3.to_wei(1000, 'ether') 
    
    dump_data = w3.eth.contract(address=DUMP_POOL, abi=PAIR_ABI).encodeABI(
        fn_name="swap",
        args=[0, expected_tbill_out, MY_CONTRACT, b''] # Swapping FED -> TBILL
    )

    # 7. PACKAGE THE MISSION BRIEF (9 Parameters)
    mission_brief = w3.eth.abi.encode(
        ['address','bytes','address','bytes','address','address','bytes','address','uint256'],
        [
            PUMP_POOL, pump_data, 
            MINT_CONTRACT, mint_data, 
            FED_ADDRESS, DUMP_POOL, dump_data, 
            TBILL_ADDRESS, repay_amount
        ]
    )

    # 8. EXECUTE
    contract = w3.eth.contract(address=MY_CONTRACT, abi=MY_ENGINE_ABI)
    # Added tokenToBorrow parameter to match updated Solidity entry point
    tx = contract.functions.executeGuerilla(
        FLASH_POOL,
        TBILL_ADDRESS,
        borrow_amount,
        mission_brief
    ).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 1500000, # Increased for the extra Dump swap
        'gasPrice': w3.eth.gas_price
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"🚀 Mission Dispatched: {tx_hash.hex()}")