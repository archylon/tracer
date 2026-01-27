import os
import sys
import time
from web3 import Web3
import sys

# --- CONFIG ---
RPC_URL = os.environ.get("RPC_URL", "https://pulsechain.publicnode.com")
PRIVATE_KEY = os.environ.get(sys.argv[1])
CHAIN_ID = 369 

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)
address = account.address

def clear_nonce_legacy(nonce):
    """
    Uses a Legacy (Type 0) transaction to force-clear a nonce.
    Legacy is often more reliable for overrides on PulseChain.
    """
    # 1. Fetch current network gas price
    current_gas_price = w3.eth.gas_price
    
    # 2. Apply a massive multiplier. 
    # Since PLS is cheap, we can afford to be aggressive (e.g., 5x - 10x)
    # This ensures we beat whatever is currently stuck.
    forced_gas_price = int(current_gas_price * 5) 

    print(f"🛠️ Attempting Legacy override for Nonce {nonce}")
    print(f"⛽ Current Gas: {w3.from_wei(current_gas_price, 'gwei')} Gwei")
    print(f"🚀 Forced Gas:  {w3.from_wei(forced_gas_price, 'gwei')} Gwei")

    tx = {
        'to': address,
        'value': 0,
        'gas': 21000,
        'gasPrice': forced_gas_price, # No maxFee/priorityFee, just raw gasPrice
        'nonce': nonce,
        'chainId': CHAIN_ID
    }

    try:
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"📡 Broadcast successful: {tx_hash.hex()}")
        
        print("⏳ Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"✅ Confirmed in block {receipt.blockNumber}!")
        return True
    except Exception as e:
        # If this still fails, the RPC might not even 'see' the transaction in its mempool
        print(f"❌ RPC rejected the replacement: {e}")
        return False

def main():
    if not w3.is_connected():
        print("❌ Failed to connect to RPC.")
        return

    latest = w3.eth.get_transaction_count(address, 'latest')
    pending = w3.eth.get_transaction_count(address, 'pending')

    print(f"Wallet: {address}")
    print(f"Confirmed Nonce: {latest}")
    print(f"Pending Nonce:   {pending}")

    if pending <= latest:
        print("🎉 No stuck transactions found.")
        return

    # Clear every nonce from the first stuck one to the current pending one
    for n in range(latest, pending):
        success = clear_nonce_legacy(n)
        if not success:
            print("\n💡 TIP: If 'INTERNAL_ERROR' persists, try a different RPC:")
            print("- https://pulsechain.publicnode.com")
            print("- https://rpc-pulsechain.gopulse.com")
            break
        time.sleep(2) # Brief pause between broadcasts

if __name__ == "__main__":
    main()
