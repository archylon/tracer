from web3 import Web3
from collections import defaultdict
import plotly.graph_objects as go

# -----------------------------
# CONFIG
# -----------------------------

RPC_URL = "https://rpc.pulsechain.com"
WALLET = Web3.to_checksum_address("0x90a5137ba8999407a7f94b5bf6cd949a66c26921")
TOKEN = Web3.to_checksum_address("0x6b175474e89094c44da98b954eedeac495271d0f")

START_BLOCK = 17_000_000

# -----------------------------
# SETUP
# -----------------------------

w3 = Web3(Web3.HTTPProvider(RPC_URL))
END_BLOCK = w3.eth.block_number

TRANSFER_TOPIC = "0x" + w3.keccak(text="Transfer(address,address,uint256)").hex()
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# -----------------------------
# FETCH TRANSFER LOGS (RECURSIVE, WALLET-FILTERED)
# -----------------------------

def fetch_logs(token, wallet, start_block, end_block, max_span=1000):
    logs = []

    wallet_topic = "0x" + wallet.lower()[2:].rjust(64, "0")

    def query(frm, to, topics):
        return w3.eth.get_logs({
            "fromBlock": hex(frm),
            "toBlock": hex(to),
            "address": token,
            "topics": topics
        })

    def recursive_fetch(frm, to, topics):
        if frm > to:
            return

        # small enough → try directly
        if to - frm <= max_span:
            try:
                logs.extend(query(frm, to, topics))
            except Exception as e:
                print(f"⚠️ failed blocks {frm}-{to}: {e}")
            return

        # otherwise split
        mid = (frm + to) // 2
        recursive_fetch(frm, mid, topics)
        recursive_fetch(mid + 1, to, topics)

    # Incoming: Transfer(* → wallet)
    recursive_fetch(
        start_block,
        end_block,
        [TRANSFER_TOPIC, None, wallet_topic]
    )

    # Outgoing: Transfer(wallet → *)
    recursive_fetch(
        start_block,
        end_block,
        [TRANSFER_TOPIC, wallet_topic, None]
    )

    return logs

# -----------------------------
# DECODE TRANSFERS
# -----------------------------

def decode(log):
    return {
        "tx": log["transactionHash"].hex(),
        "from": Web3.to_checksum_address("0x" + log["topics"][1].hex()[-40:]),
        "to": Web3.to_checksum_address("0x" + log["topics"][2].hex()[-40:]),
        "amount": int.from_bytes(log["data"], "big")
    }

# -----------------------------
# CLASSIFY FLOWS
# -----------------------------

def classify(transfers):
    by_tx = defaultdict(list)
    for t in transfers:
        by_tx[t["tx"]].append(t)

    incoming = defaultdict(int)
    outgoing = defaultdict(int)

    for tx, events in by_tx.items():
        ins = [e for e in events if e["to"] == WALLET]
        outs = [e for e in events if e["from"] == WALLET]

        # Swap (token out + token in in same tx)
        if ins and outs:
            for o in outs:
                outgoing["Swap"] += o["amount"]
            continue

        # Incoming
        for i in ins:
            src = "Mint" if i["from"] == ZERO_ADDRESS else i["from"]
            incoming[src] += i["amount"]

        # Outgoing
        for o in outs:
            outgoing[o["to"]] += o["amount"]

    return incoming, outgoing

# -----------------------------
# BUILD SANKEY
# -----------------------------

def build_sankey(incoming, outgoing):
    nodes = []
    links = []

    center = f"Wallet\n{WALLET[:6]}…"

    def add_node(label):
        if label not in nodes:
            nodes.append(label)
        return nodes.index(label)

    center_idx = add_node(center)

    # Incoming → wallet
    for src, amt in incoming.items():
        src_label = "Mint" if src == "Mint" else f"From\n{src[:6]}…"
        s = add_node(src_label)
        links.append(dict(source=s, target=center_idx, value=amt))

    # Wallet → outgoing
    for dst, amt in outgoing.items():
        dst_label = "Swap" if dst == "Swap" else f"To\n{dst[:6]}…"
        d = add_node(dst_label)
        links.append(dict(source=center_idx, target=d, value=amt))

    return nodes, links

# -----------------------------
# MAIN
# -----------------------------

print("Fetching logs...")
raw_logs = fetch_logs(TOKEN, WALLET, START_BLOCK, END_BLOCK)
decoded = [decode(l) for l in raw_logs]

print("Classifying flows...")
incoming, outgoing = classify(decoded)

print("Building Sankey...")
nodes, links = build_sankey(incoming, outgoing)

fig = go.Figure(data=[go.Sankey(
    node=dict(
        label=nodes,
        pad=20,
        thickness=20
    ),
    link=dict(
        source=[l["source"] for l in links],
        target=[l["target"] for l in links],
        value=[l["value"] for l in links]
    )
)])

fig.update_layout(
    title="Token Flow Sankey (PulseChain)",
    font_size=12
)

fig.show()




