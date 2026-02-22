import time
from web3 import Web3

# 1. Setup Connection
RPC_URL = "https://rpc.pulsechain.com" # PulseChain Mainnet
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# 2. Configuration
PRIVATE_KEY = "YOUR_PRIVATE_KEY"
MY_ADDRESS = w3.eth.account.from_key(PRIVATE_KEY).address
GUERILLA_CONTRACT = "0x..." # Your deployed Flash Loan contract address

# Token Addresses (Replace with actual PulseChain addresses)
TOKENS_TO_APPROVE = {
    "Gaping": "0x...",
    "pINDEPENDENCE": "0x...",
    "MATH": "0x..."
}

# Minimal ERC-20 ABI for the 'approve' function
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

def batch_approve():
    if not w3.is_connected():
        print("Failed to connect to PulseChain")
        return

    # Use max uint256 for "infinite" approval
    max_amount = 2**256 - 1
    
    for name, token_address in TOKENS_TO_APPROVE.items():
        token_contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
        
        # Build transaction
        nonce = w3.eth.get_transaction_count(MY_ADDRESS)
        tx = token_contract.functions.approve(
            w3.to_checksum_address(GUERILLA_CONTRACT), 
            max_amount
        ).build_transaction({
            'from': MY_ADDRESS,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        # Sign and Send
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        print(f"✅ Sent approval for {name}. Hash: {tx_hash.hex()}")
        
        # Wait a few seconds for the nonce to update on-chain
        time.sleep(5)

if __name__ == "__main__":
    batch_approve()