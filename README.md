# Enhanced Multibuy Arbitrage Bot v2

## Overview

This bot automates the complete multibuy arbitrage cycle on PulseChain:
1. Start with **USDC** (minter token) and **PLS** (for gas)
2. Execute multibuy to acquire **Affection** tokens
3. Automatically execute 3-step profit-taking sequence

## The 3-Step Profit Sequence

After each successful multibuy, the bot automatically:

### Step 1: Recover Gas in PLS 🔄
- Swaps just enough Affection → PLS to recover the gas cost
- Ensures the operation is self-sustaining
- Example: Spent 100 PLS on gas → Swap ~10% of Affection to get 100 PLS back

### Step 2: Recover USDC Investment 💵
- Swaps X% of remaining Affection back to USDC
- Controlled by `USDC_RECOVERY_PCT` (default: 100%)
- 100% = full recovery of initial capital
- 50% = recover half, let rest ride as profit
- Example: Swap 70% of remaining Affection → USDC

### Step 3: Take Profit in Chosen Token 💎
- Remaining Affection is your profit
- Choose how to hold it via `PROFIT_TOKEN`:
  - `"AFFECTION"` = Hold as Affection tokens
  - `"PLS"` = Convert to PLS
  - `0x...` = Convert to custom token address

## Configuration

### Required Environment Variables
```bash
export KEY="your_private_key"
export RPC_URL="https://rpc.pulsechain.com"
```

### Strategy Settings
```bash
# Minimum profit percentage to execute trade
export MIN_PROFIT_PCT=5

# Percentage of USDC to recover (0-100)
# 100 = recover all initial capital
# 50 = recover half, let half ride
export USDC_RECOVERY_PCT=100

# How to take profit: "AFFECTION", "PLS", or token address
export PROFIT_TOKEN="PLS"
```

## Usage Examples

### Conservative Strategy (Recover Everything, Take Profit in PLS)
```bash
export MIN_PROFIT_PCT=10
export USDC_RECOVERY_PCT=100
export PROFIT_TOKEN="PLS"
python multibuy_arb_enhanced.py 5.0 1100
```

### Aggressive Strategy (Let It Ride, Hold Affection)
```bash
export MIN_PROFIT_PCT=3
export USDC_RECOVERY_PCT=50
export PROFIT_TOKEN="AFFECTION"
python multibuy_arb_enhanced.py 5.0 1100
```

### Compound Growth Strategy (Reinvest in USDC)
```bash
export MIN_PROFIT_PCT=5
export USDC_RECOVERY_PCT=150  # Recover MORE than you started with
export PROFIT_TOKEN="AFFECTION"
python multibuy_arb_enhanced.py 5.0 1100
```

## How It Works

### Starting Position
```
Wallet Contains:
├─ 10,000 PLS (for gas)
└─ 5,000 USDC (minting/trading capital)
```

### Profitability Check
Before executing, the bot calculates:

```
Expected Affection = 1,100 tokens
Affection Value = 1,100 × current_price = $2,500 USDC

Costs:
├─ Gas Cost: 100 PLS (≈ $150 USDC equivalent)
└─ USDC Spent: $0 (multibuy costs only gas)
Total Costs = $150

Profit = $2,500 - $150 = $2,350 USDC
Profit % = ($2,350 / $150) × 100 = 1,566%

✅ Profitable! (1,566% > 5% threshold)
```

### Execution Flow

```
1. MULTIBUY TRANSACTION
   ├─ Spend: 100 PLS gas
   └─ Receive: 1,100 Affection tokens

2. PROFIT SEQUENCE - STEP 1: Recover Gas
   ├─ Need: 100 PLS
   ├─ Swap: ~110 Affection → 100 PLS
   └─ Remaining: 990 Affection

3. PROFIT SEQUENCE - STEP 2: Recover USDC (100%)
   ├─ Target: Recover USDC capital
   ├─ Swap: 990 Affection → 2,250 USDC
   └─ Remaining: 0 Affection (all converted)

4. PROFIT SEQUENCE - STEP 3: Take Profit (PLS)
   ├─ Profit USDC: $2,250
   ├─ Swap: $2,250 USDC → 150 PLS
   └─ Final: 150 PLS profit

RESULT:
├─ PLS: 10,000 + 150 = 10,150 PLS (+150 profit)
└─ USDC: 5,000 USDC (fully recovered)
```

## Profit Calculation Explained

The bot calculates profit in USDC terms for accuracy:

```
Revenue = Total Affection × Price_in_USDC
Costs = USDC_Spent + (Gas_PLS × PLS_to_USDC_Rate)
Profit = Revenue - Costs
```

This ensures accurate profitability across different market conditions.

## Example Output

```
============================================================
🔗 PULSECHAIN MULTIBUY ARBITRAGE BOT v2
============================================================
👤 Account:        0xb8D6...3044
🔄 Loops:          1100
💰 Gas Threshold:  5,500 PLS
🎯 Min Profit:     5%
💵 USDC Recovery:  100%
💎 Profit Token:   PLS

📋 PROFIT SEQUENCE:
   1. Recover gas → PLS
   2. Recover 100% → USDC
   3. Take profit → PLS

💹 Target: 100M PLS → 60,000 Affection

============================================================
Iteration #1
============================================================
📋 TX Details (Nonce 42)
────────────────────────────────────────────────────────────
⛽ Gas Limit:      4,180,000
💰 Max Gas Price:  25.50 gwei
💵 Est. Max Cost:  106.59 PLS

============================================================
💰 PROFITABILITY CHECK
============================================================
📊 Expected Affection gain: 1,100
📊 Total Affection value: $2,500.00 USDC
📊 Gas costs:
   MultiBuy: 106.59 PLS ($159.89 USDC)
   Swaps:    0.75 PLS ($1.12 USDC)
   Total:    $161.01 USDC

💰 PROFIT ANALYSIS:
   Revenue:           $2,500.00 USDC
   Costs:
     USDC spent:      $0.00
     Gas (in USDC):   $161.01
     ────────────────────────
     Total costs:     $161.01
   ────────────────────────
   Net Profit:        $2,338.99
   Profit %:          1,452.5%

────────────────────────────────────────────────────────────
✅ PROFITABLE
💵 Net profit: $2,338.99 (1,452.5%)
🎯 Minimum threshold: 5%
============================================================

🚀 Sent: 0xabc123...

============================================================
✅ TRANSACTION CONFIRMED
============================================================
📦 Block:          18,234,567
⛽ Gas Used:       4,123,456
💰 Gas Price:      24 gwei
💵 Actual Cost:    98.96 PLS
💎 Affection:      1,100 tokens
────────────────────────────────────────────────────────────
📊 Buy Rate: 100M PLS buys 3,333,333 Affection tokens
============================================================

============================================================
💎 PROFIT TAKING SEQUENCE (3 STEPS)
============================================================
📊 Current Affection balance: 2,234.56
📊 Expected from multibuy: 1,100.00
💸 Total gas spent: 98.96 PLS

────────────────────────────────────────────────────────────
STEP 1: Recover Gas (98.96 PLS)
────────────────────────────────────────────────────────────
💱 Swapping 110.00 Affection → ~98.96 PLS
🔄 Affection → PLS (gas recovery) sent: 0xdef456...
✅ Affection → PLS (gas recovery) confirmed (Gas: 0.25 PLS, Got: ~98.96 PLS)
✅ Step 1 complete. Remaining Affection: 990.00

────────────────────────────────────────────────────────────
STEP 2: Recover USDC (100%)
────────────────────────────────────────────────────────────
💱 Swapping 990.00 Affection → ~$2,250.00 USDC
🔄 Affection → USDC (recovery) sent: 0x789abc...
✅ Affection → USDC (recovery) confirmed (Gas: 0.30 PLS)
✅ Step 2 complete. Remaining Affection: 0.00

────────────────────────────────────────────────────────────
STEP 3: Take Profit (Target: PLS)
────────────────────────────────────────────────────────────
💎 Profit Affection available: 0.00
💵 Note: All Affection converted to USDC in Step 2
   You now have $2,250 USDC profit to manually swap to PLS

============================================================
✅ PROFIT SEQUENCE COMPLETE
============================================================
```

## Strategy Comparison

### Full Recovery Strategy (Recommended for Beginners)
```bash
USDC_RECOVERY_PCT=100
PROFIT_TOKEN="PLS"
```
**Effect:** Always get your USDC back, take profit in PLS
**Risk:** Low - capital is always protected
**Growth:** Linear - profit compounds in PLS

### Partial Recovery Strategy (Balanced)
```bash
USDC_RECOVERY_PCT=70
PROFIT_TOKEN="AFFECTION"
```
**Effect:** Recover most USDC, leave 30% riding
**Risk:** Medium - 30% stays exposed
**Growth:** Faster - compounds in Affection

### Let It Ride Strategy (Aggressive)
```bash
USDC_RECOVERY_PCT=0
PROFIT_TOKEN="AFFECTION"
```
**Effect:** Keep all Affection, maximize position
**Risk:** High - all capital stays in Affection
**Growth:** Fastest - full compounding

### Over-Recovery Strategy (Compounding Capital)
```bash
USDC_RECOVERY_PCT=150
PROFIT_TOKEN="PLS"
```
**Effect:** Recover initial USDC + 50% more
**Risk:** Medium - reduces profit but grows capital
**Growth:** Balanced - both capital and profit grow

## Token Addresses (PulseChain)

```python
AFFECTION = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
USDC      = "0x15D38573d2feeb82e7ad5187aB8c1D52810B1f07"  # Minter token
WPLS      = "0xA1077a294dDE1B09bB078844df40758a5D0f9a27"
ROUTER    = "0x165C3410fC91EF562C50559f7d2289fEbed552d9"  # PulseX
```

⚠️ **Verify these addresses for your deployment!**

## Safety Features

1. **Profitability Pre-Check:** Never executes unprofitable trades
2. **Gas Recovery:** Always recovers gas costs first
3. **Flexible Capital Recovery:** Control how much USDC to recover
4. **Approval Management:** Automatic token approvals when needed
5. **Slippage Protection:** 2% slippage tolerance on all swaps
6. **Error Handling:** Graceful failures with detailed logging

## Troubleshooting

### "Trade not profitable enough"
- Market conditions changed
- Lower `MIN_PROFIT_PCT` or increase `LOOPS`
- Check Affection/USDC liquidity

### "Gas recovery failed"
- Insufficient liquidity in Affection/PLS pair
- Try lowering the loops count
- Check that pools exist

### "USDC recovery failed"
- Set `USDC_RECOVERY_PCT` lower
- Check Affection/USDC pair liquidity
- Verify USDC address is correct

## Risk Warnings

⚠️ **This bot executes real transactions with real funds**

- Test with small amounts first
- Verify all token addresses
- Monitor gas prices during execution
- Be aware of impermanent loss
- Smart contract risks apply
- No guarantee of profit

## Advanced Tips

1. **Optimal Loop Count:** Test 500-1500 range for your gas budget
2. **Best Execution Times:** Low network congestion = lower gas
3. **Recovery Percentage:** Higher USDC_RECOVERY_PCT = safer but slower growth
4. **Profit Token Choice:**
   - PLS = Liquid, easy to use
   - AFFECTION = Compound growth
   - Custom = Diversification

## Support

For issues:
1. Check error messages carefully
2. Verify configuration in diagnostics
3. Test with minimal settings first
4. Review the PROFIT_EXPLAINED.md document

---

**Trade Responsibly! 🚀**





APPROVALS for MULTI_BUY_ARB_ENHANCED

1. aff approve contract
2. usdc approve contract
3. math approve contract

4. aff approve math
5. usdc approve math
