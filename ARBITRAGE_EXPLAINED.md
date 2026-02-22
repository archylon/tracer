# Arbitrage Profit Calculation - CORRECT VERSION

## Understanding the Multibuy Minting Engine

The multibuy contract is a **token minting engine**:
- You SPEND USDC (the minter token)
- You RECEIVE Affection tokens
- The profit comes from the price difference (arbitrage)

## The Complete Flow

### STEP 1: Mint Affection Tokens
```
INPUT:  100 USDC (spent to the minting contract)
OUTPUT: 100 Affection tokens (received from mint)
COST:   Gas fees in PLS
```

### STEP 2: Check Market Price
```
Market Price Check:
- Swap 100 Affection → ? USDC on PulseX
- If market price is 150 USDC
- Then we have a 50 USDC arbitrage opportunity!
```

### STEP 3: Calculate Profit
```
REVENUE:  150 USDC (what we can sell Affection for)
COSTS:
  - USDC spent: 100 USDC (paid to mint)
  - Gas costs:  5 USDC equivalent (PLS converted to USDC value)
  - Total:      105 USDC

NET PROFIT = 150 - 105 = 45 USDC
PROFIT % = (45 / 105) × 100 = 42.9%
```

## Real Example

```
═══════════════════════════════════════════════════════════
EXAMPLE: 1,100 Loop Multibuy
═══════════════════════════════════════════════════════════

INPUTS (what you spend):
├─ USDC to mint:       $100.00
└─ PLS for gas:        50 PLS

MULTIBUY TRANSACTION:
├─ Function call:      multiBuyWith(USDC_ADDRESS, 1100)
├─ USDC spent:         $100.00 → minting contract
├─ Gas cost:           50 PLS (≈ $75 USDC value)
└─ Affection received: 1,100 tokens

MARKET CHECK:
├─ Estimated swap:     1,100 Affection → $150 USDC
├─ Market price:       $0.136 per Affection
└─ Mint cost:          $0.091 per Affection

ARBITRAGE CALCULATION:
┌────────────────────────────────────────────┐
│ Revenue (sell at market):    $150.00       │
│ Cost (mint price):           $100.00       │
│ ──────────────────────────────────         │
│ Gross Arbitrage:             $50.00        │
│                                            │
│ Minus gas costs:             $75.00        │
│ ──────────────────────────────────         │
│ NET PROFIT:                  -$25.00  ❌   │
│ (NOT PROFITABLE - SKIP!)                   │
└────────────────────────────────────────────┘

This trade would LOSE money, so bot skips it!
═══════════════════════════════════════════════════════════
```

## Profitable Example

```
═══════════════════════════════════════════════════════════
PROFITABLE ARBITRAGE EXAMPLE
═══════════════════════════════════════════════════════════

Assume better market conditions:

INPUTS:
├─ USDC to mint:       $100.00
└─ PLS for gas:        50 PLS (≈ $75 value)

MULTIBUY:
├─ USDC spent:         $100.00
├─ Gas cost:           50 PLS
└─ Affection got:      1,100 tokens

MARKET VALUE (high demand!):
├─ Swap estimate:      1,100 Affection → $350 USDC
└─ Market price:       $0.318 per Affection

PROFIT CALCULATION:
┌────────────────────────────────────────────┐
│ Revenue:                     $350.00       │
│ Costs:                                     │
│   - USDC (mint):             $100.00       │
│   - Gas (USDC equiv):        $75.00        │
│   Total costs:               $175.00       │
│ ──────────────────────────────────         │
│ NET PROFIT:                  $175.00  ✅   │
│ PROFIT %:                    100.0%        │
│ (EXECUTE THIS TRADE!)                      │
└────────────────────────────────────────────┘

Bot executes because 100% > 5% threshold!
═══════════════════════════════════════════════════════════
```

## The 3-Step Profit Taking Sequence

After minting Affection at a profit:

### Step 1: Recover Gas (in PLS)
```
Need: 50 PLS (what we spent on gas)
Action: Swap ~110 Affection → 50 PLS
Remaining: 990 Affection
```

### Step 2: Recover USDC (configurable %)
```
Setting: USDC_RECOVERY_PCT = 100
Need: $100 USDC (what we spent on mint)
Action: Swap ~330 Affection → $100 USDC
Remaining: 660 Affection
```

### Step 3: Take Profit (your choice)
```
Setting: PROFIT_TOKEN = "PLS"
Have: 660 Affection (worth ~$210)
Action: Swap 660 Affection → 140 PLS
Result: 140 PLS pure profit!
```

## Final Position After One Cycle

```
BEFORE:
├─ USDC: $500
└─ PLS:  200

AFTER (successful arb):
├─ USDC: $500 (recovered!)
└─ PLS:  290 (200 - 50 + 140 = +90 profit!)
```

## Key Configuration: USDC_PER_LOOP

You need to know how much USDC the minting contract charges per loop:

```bash
# If the contract charges 0.10 USDC per loop:
export USDC_PER_LOOP=0.10

# For 1,100 loops:
# Total USDC spent = 0.10 × 1,100 = $110
```

If you don't know this value:
- Set `USDC_PER_LOOP=0`
- Bot will calculate actual spend by checking balance before/after
- Less accurate for profitability check, but still works

## Profit Formula (Final)

```python
# What we get
revenue_usdc = affection_tokens × market_price_usdc

# What we pay
cost_usdc = usdc_spent_to_mint
cost_gas_usdc = pls_gas_cost × pls_to_usdc_rate
total_costs = cost_usdc + cost_gas_usdc

# Profit
gross_arbitrage = revenue_usdc - cost_usdc
net_profit = revenue_usdc - total_costs
profit_pct = (net_profit / total_costs) × 100

# Decision
if profit_pct >= MIN_PROFIT_PCT:
    EXECUTE_TRADE()
else:
    SKIP_TRADE()
```

## Why This Matters

### ❌ WRONG (what we had before):
- Ignored USDC spent on minting
- Only counted gas costs
- Calculated "profit" without accounting for initial investment
- Would execute losing trades!

### ✅ CORRECT (what we have now):
- Tracks USDC spent to mint
- Compares market price vs mint price (true arbitrage)
- Accounts for ALL costs (USDC + gas)
- Only executes when real profit exists!

## Example Bot Output

```
============================================================
💰 PROFITABILITY CHECK
============================================================
📊 INPUTS:
   USDC to spend (mint):     $100.00
   Expected Affection out:   1,100 tokens

📊 MARKET VALUE:
   Affection → USDC swap:    $350.00
   Implied price:            $0.3182 per Affection

💸 COSTS:
   USDC spent (minting):     $100.00
   MultiBuy gas:             50.00 PLS ($75.00 USDC)
   Swap gas:                 0.75 PLS ($1.13 USDC)
   ────────────────────────────────
   Total gas:                $76.13
   TOTAL COSTS:              $176.13

💰 ARBITRAGE ANALYSIS:
   Revenue (sell Affection): $350.00
   Cost (buy Affection):     $100.00
   ────────────────────────────────
   Gross profit (arb):       $250.00 (250.0%)
   Minus gas costs:          $76.13
   ────────────────────────────────
   NET PROFIT:               $173.87
   Net profit %:             98.7%

────────────────────────────────────────────────────────────
✅ PROFITABLE
💵 Net profit: $173.87 (98.7%)
📈 Arbitrage spread: 250.0%
🎯 Minimum threshold: 5%
============================================================
```

## Summary

The bot now correctly:
1. ✅ Tracks USDC spent on minting
2. ✅ Calculates true arbitrage (market price - mint price)
3. ✅ Subtracts ALL costs (USDC + gas in USDC terms)
4. ✅ Only executes profitable trades
5. ✅ Recovers both gas and USDC investment
6. ✅ Takes profit in your chosen token

This is a **true arbitrage bot** that profits from the price difference between the minting contract and the open market!
