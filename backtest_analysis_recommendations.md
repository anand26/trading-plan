# Backtest Analysis & Parameter Recommendations

## Current Results Summary

All 12 backtests showed **negative returns** ranging from -1.91% to -10.57%.

### Best Performing (Still Negative)
1. **BT_20260128_015146_9c8a7388**: -1.91% return, 51.06% win rate, 0.83 profit factor
   - RSI Oversold: 25, Stop Loss: 1%, Take Profit: 2.5%
   - 47 trades (fewest)

2. **BT_20260128_015305_0804b398**: -6.25% return, 47.95% win rate, 0.69 profit factor
   - RSI Oversold: 28, Stop Loss: 1%, Take Profit: 2.5%
   - 73 trades

### Worst Performing
- **BT_20260128_015630_129b522a**: -10.57% return, 50.71% win rate
- **BT_20260128_020014_93bfc539**: -10.57% return, 50.71% win rate
  - RSI Oversold: 32 (too high - entering too late)

---

## Key Observations

### 🔴 Problems Identified

1. **Stop Loss Too Tight**: All backtests use **1% stop loss**
   - Average losing trades are hitting stop loss quickly
   - Not giving trades room to breathe in volatile TQQQ

2. **RSI Oversold Too High**: Higher RSI oversold (32-35) performed WORST
   - More trades (140-213) but worse returns (-8% to -10.5%)
   - Entering too late in the move

3. **Win Rate > 50% but Still Losing**: Indicates **losses are bigger than wins**
   - Profit factors all < 1.0 (range: 0.69 - 0.84)
   - Need better risk/reward ratio

4. **Too Many Trades with High RSI**: 200+ trades when RSI oversold = 35
   - Overtrading = more commissions/slippage

---

## 💡 Recommended Parameter Improvements

### Priority 1: Widen Stop Loss
**Current**: 1% (too tight for TQQQ volatility)
**Recommended**: Test **2.0% - 2.5% - 3.0%**

Reasoning: TQQQ can swing 2-3% intraday. A 1% stop gets triggered by normal noise.

### Priority 2: Lower RSI Oversold (Enter Earlier)
**Current**: 25-35
**Recommended**: Test **20 - 22 - 25**

Reasoning: Lower RSI oversold = fewer but higher quality entries. Your best result used RSI 25.

### Priority 3: Increase Take Profit Ratio
**Current**: 2.5% (2.5:1 reward/risk)
**Recommended**: Test **3.0% - 3.5%** with wider stop

Reasoning: With 2.5% stop loss, aim for 5-7% profit (2:1 to 3:1 ratio)

### Priority 4: Adjust Bollinger Bands
**Current**: BB Period 15-22, Std Dev 1.5-2.5
**Recommended**: Test **BB Period 20, Std Dev 2.0**

Reasoning: Standard BB(20,2) is proven. Your variations didn't help.

---

## 🎯 Suggested Test Combinations

### Test Set A: Focus on Stop Loss + RSI
```json
{
  "rsi_oversold": 22,
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.04,
  "bb_period": 20,
  "bb_std_dev": 2.0
}

{
  "rsi_oversold": 22,
  "stop_loss_pct": 0.025,
  "take_profit_pct": 0.05,
  "bb_period": 20,
  "bb_std_dev": 2.0
}

{
  "rsi_oversold": 20,
  "stop_loss_pct": 0.025,
  "take_profit_pct": 0.05,
  "bb_period": 20,
  "bb_std_dev": 2.0
}
```

### Test Set B: Conservative (Fewer Trades)
```json
{
  "rsi_oversold": 20,
  "rsi_overbought": 80,
  "stop_loss_pct": 0.03,
  "take_profit_pct": 0.06,
  "bb_period": 20,
  "bb_std_dev": 2.0
}

{
  "rsi_oversold": 18,
  "rsi_overbought": 82,
  "stop_loss_pct": 0.025,
  "take_profit_pct": 0.05,
  "bb_period": 20,
  "bb_std_dev": 2.0
}
```

### Test Set C: Aggressive (More Trades)
```json
{
  "rsi_oversold": 25,
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.035,
  "bb_period": 20,
  "bb_std_dev": 2.0
}

{
  "rsi_oversold": 25,
  "stop_loss_pct": 0.015,
  "take_profit_pct": 0.03,
  "bb_period": 20,
  "bb_std_dev": 1.8
}
```

---

## 📊 Expected Improvements

If hypotheses are correct:
- **Wider stop loss** → Less premature exits → Higher win rate
- **Lower RSI oversold** → Better entry timing → Higher profit per trade
- **Higher take profit** → Better risk/reward → Profit factor > 1.0

**Target Metrics**:
- Total Return: > 0% (break even first)
- Win Rate: > 55%
- Profit Factor: > 1.2
- Sharpe Ratio: > 0.0

---

## 🛠️ Next Steps

1. **Run Test Set A** (3 backtests) - Focus on stop loss
2. **Analyze results** - Compare to best current result (-1.91%)
3. **If improved**: Run Test Set B (conservative approach)
4. **If still negative**: Consider:
   - Different entry signals (not just RSI + BB)
   - Market regime filtering (only trade in uptrends)
   - Time-of-day filters (avoid choppy open/close)
   - Mean reversion might not work in this time period

---

## 🚨 Alternative Hypothesis

**TQQQ might have been in a downtrend during your backtest period**. If the market was bearish:
- Mean reversion (RSI oversold) will keep losing money
- Consider:
  - Adding trend filter (only buy when above 50-day EMA)
  - Testing shorter timeframe (15-min instead of 1-min)
  - Switching to momentum strategy instead of mean reversion

**Check your backtest date range** - if it was a bearish period, mean reversion RSI strategy will naturally lose money.
