"""
Compare current LEAN factor files vs what they SHOULD be based on actual split history.
"""

print("""
============================================================
 TQQQ FACTOR FILE ANALYSIS
============================================================

ACTUAL SPLIT HISTORY (yfinance):
  2011-02-25: 2:1 forward split
  2012-05-11: 2:1 forward split
  2014-01-24: 2:1 forward split
  2017-01-12: 2:1 forward split
  2018-05-24: 3:1 forward split  
  2021-01-21: 2:1 forward split
  2022-01-13: 2:1 forward split
  2025-11-20: 2:1 forward split

EXPECTED FACTOR FILE (splitFactor = product of all SUBSEQUENT split ratios, inverted):
  Entry at IPO (20100209):   splitFactor = 1/(2*2*2*2*3*2*2*2) = 1/384 = 0.00260417
  After 2011-02-25 split:   splitFactor = 1/(2*2*2*3*2*2*2)   = 1/192 = 0.00520833
  After 2012-05-11 split:   splitFactor = 1/(2*2*3*2*2*2)     = 1/96  = 0.01041667
  After 2014-01-24 split:   splitFactor = 1/(2*3*2*2*2)       = 1/48  = 0.02083333
  After 2017-01-12 split:   splitFactor = 1/(3*2*2*2)         = 1/24  = 0.04166667
  After 2018-05-24 split:   splitFactor = 1/(2*2*2)           = 1/8   = 0.12500000
  After 2021-01-21 split:   splitFactor = 1/(2*2)             = 1/4   = 0.25000000
  After 2022-01-13 split:   splitFactor = 1/(2)               = 1/2   = 0.50000000
  After 2025-11-20 split:   splitFactor = 1                   = 1     = 1.00000000

CURRENT LEAN FACTOR FILE:
  20100209,1,0.04166667,0.22    ← WRONG! Should be 0.00260417 (we put 0.04166667)
  20180523,1,0.04166667,165.85  ← This is correct for "after 2017-01-12 split" period
  20210120,1,0.125,199.27       ← Correct  
  20220112,1,0.25,152.54        ← Correct
  20251119,1,0.5,104.63         ← Correct
  20501231,1,1,0                ← Correct

WHAT'S MISSING:
  The factor file is missing entries for the 4 splits BEFORE 2018:
    20110225 (2:1), 20120511 (2:1), 20140124 (2:1), 20170112 (2:1)
  
  The first entry (20100209) has splitFactor=0.04166667 but should be 0.00260417
  because there were 4 more 2:1 splits (total 16x) before the 3:1 split.

  Original file only had entries from 20180523 onward (covering 2018+ period).
  We added IPO entry 20100209 but gave it the SAME splitFactor as 20180523,
  which is wrong - it should account for the 4 earlier splits too.

CORRECTED TQQQ FACTOR FILE SHOULD BE:
  20100209,1,0.00260417,0.22     ← IPO date, all 8 splits ahead
  20110225,1,0.00520833,XX.XX    ← After first 2:1 split
  20120511,1,0.01041667,XX.XX    ← After second 2:1 split  
  20140124,1,0.02083333,XX.XX    ← After third 2:1 split
  20170112,1,0.04166667,XX.XX    ← After fourth 2:1 split (matches original first entry!)
  20180523,1,0.04166667,165.85   ← Wait - this should be 20180524 and splitFactor 0.125?

Hmm, the date 20180523 is the day BEFORE the split on 20180524.
LEAN convention: factor file dates are the LAST day the OLD factor applies
(i.e., the day before the split takes effect).

So:
  20100209 = IPO date (first trading day)
  20180523 = day before 2018-05-24 split → splitFactor for period BEFORE this split
  20210120 = day before 2021-01-21 split
  20220112 = day before 2022-01-13 split
  20251119 = day before 2025-11-20 split

The splitFactor ON the entry date represents the factor for data UP TO that date.
After this date, the NEXT entry's factor applies.

So 20180523 with splitFactor=0.04166667 means: from 20170112 to 20180523,
the cumulative remaining splits = 3*2*2*2 = 24, so splitFactor = 1/24 = 0.04166667 ✓

But our IPO entry 20100209 with 0.04166667 says "from IPO to 20180523, 
splitFactor = 0.04166667" - this is WRONG because there were 4 more splits 
in that range (2011, 2012, 2014, 2017) = 16x more.

True IPO splitFactor = 0.04166667 / 16 = 0.00260417

============================================================
 SQQQ FACTOR FILE ANALYSIS  
============================================================

ACTUAL SPLIT HISTORY (yfinance):
  2012-05-11: 1:4 reverse split (0.25:1)
  2014-01-24: 1:4 reverse split (0.25:1)
  2017-01-12: 1:4 reverse split (0.25:1)
  2019-05-24: 1:4 reverse split (0.25:1)
  2020-08-18: 1:5 reverse split (0.20:1)
  2022-01-13: 1:5 reverse split (0.20:1)
  2024-11-07: 1:5 reverse split (0.20:1)
  2025-11-20: 1:5 reverse split (0.20:1)

For reverse splits, splitFactor > 1 for older dates.
  IPO splitFactor = (1/0.25)^4 * (1/0.2)^4 = 4^4 * 5^4 = 256 * 625 = 160,000

CURRENT LEAN FACTOR FILE:
  20101105,1,2500,12316800       ← WRONG! Should be 160,000
  20190523,1,2500,10.29          ← Correct (4^3 * 5^4 = 64*625 = ... wait)
  
  Let me recalculate:
  After 2012-05-11: remaining = 4^3 * 5^4 = 64 * 625 = 40,000
  After 2014-01-24: remaining = 4^2 * 5^4 = 16 * 625 = 10,000  
  After 2017-01-12: remaining = 4^1 * 5^4 = 4 * 625 = 2,500
  After 2019-05-24: remaining = 5^4 = 625
  After 2020-08-18: remaining = 5^3 = 125
  After 2022-01-13: remaining = 5^2 = 25
  After 2024-11-07: remaining = 5^1 = 5
  After 2025-11-20: remaining = 1

CURRENT vs EXPECTED:
  20101105,1,2500,12316800    ← Should be 160,000 (not 2,500!)
  20190523,1,2500,10.29       ← Correct! (after 2017 split, remaining = 4*625 = 2500)
  20200817,1,625,5.26         ← Correct
  20220112,1,125,6.36         ← Correct
  20241106,1,25,6.65          ← Correct
  20251119,1,5,14.43          ← Correct
  20501231,1,1,0              ← Correct

WHAT'S MISSING for SQQQ:
  Entries for the 3 splits before 2019:
    20120511 (1:4 reverse), 20140124 (1:4 reverse), 20170112 (1:4 reverse)
  
  IPO entry should have splitFactor = 160,000 (not 2,500)

============================================================
 SUMMARY - BOTH FILES NEED FIXING
============================================================

TQQQ: Our IPO entry has wrong splitFactor (0.04166667 instead of 0.00260417)
      AND missing 4 intermediate split entries (2011, 2012, 2014, 2017)

SQQQ: Our IPO entry has wrong splitFactor (2500 instead of 160000)
      AND missing 3 intermediate split entries (2012, 2014, 2017)
""")
