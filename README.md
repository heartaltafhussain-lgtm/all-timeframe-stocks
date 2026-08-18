# ⏱ All Timeframe Stocks — NSE 500 GTF Multi-Timeframe Scanner (v5.0)

Naya repo (Strict Pure Stocks ke baad ka next level): har stock ka **1D aur 1M zone alag-alag**
filter hota hai, sector index ka **apna zone status** bhi, aur **TRADE STOCKS** = dono timeframes
me ek saath zone wale stocks.

## 🗂 Dashboard ke sections
- **🏆 STRICT TOP-3** — backtest-tested strict picks (SUPER + FRESH + whitelist + Course veto)
- **🔥 TRADE STOCKS** — 1D aur 1M DONO zones me wale stocks (asli trade candidates)
- **📅 DAILY (1D)** — sirf daily zone ke IN/NEAR stocks
- **🗓 MONTHLY (1M)** — sirf monthly zone ke IN/NEAR stocks
- **🗂 SECTOR ZONES** — har sector index ka apna monthly zone status (IN DEMAND / IN SUPPLY)
- **📡 ALL ZONE STOCKS** — full table + timeframe filter + date history

## ✅ Features
- Sector card click = sab tables filter (daily, monthly, trade, all)
- 🟢 **DEMAND stocks ka naam GREEN**, 🔴 **SUPPLY stocks ka naam RED** (har table me)
- SYMBOL column fixed (left/right slide pe apni jagah)
- Stock name click = TradingView chart
- Har table ka filtered CSV download
- Har baar open pe password (7004602)
- Refresh feedback + scan-date line (Last scan ⏳ badge)
- Date-wise history filter (purane din ka poora scan)

## 🔒 Password
`7004602` (index.html me change kar sakte ho)

## 🚀 GitHub setup
1. Naya repo banao: **all-timeframe-stocks** (Public)
2. Saari files upload karo (`.github` folder aur `history` folder bhi — hidden folders dikhao!)
3. Settings → Actions → General → Workflow permissions → **Read and write** ✅
4. Settings → Pages → Deploy from branch → **main → root** ✅
5. Actions tab → Run workflow → green tick ✔️ → `https://USERNAME.github.io/all-timeframe-stocks/`

## 📁 Files
| File | Kaam |
|---|---|
| `all_timeframe_scanner.py` | Scanner v5.0 — 1D/1M subsets + sector zones + strict top-3 (Course veto) |
| `gtf_v2.py` | Course-faithful zone detector (Ep 3-8) |
| `index.html` | All Timeframe dashboard |
| `history/all.json` | Date-wise history (77+ din ka seed pehle se hai) |
| `.github/workflows/daily_scan.yml` | Mon–Fri 15:45 IST auto-scan |

⚠️ Educational project — investment advice nahi. Past performance ≠ future guarantee.
