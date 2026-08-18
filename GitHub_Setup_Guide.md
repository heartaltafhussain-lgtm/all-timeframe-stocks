# 🚀 GitHub Setup Guide — All Timeframe Stocks

> Is guide ko **upar se neeche** follow karo. Total time: ~10-15 minute.
> Agar kahin atak jao, sabse end me **Common Problems** section hai.

---

## ✅ Step 0 — Tayaari (kya kya chahiye)

- [ ] **GitHub account** — aapke paas pehle se hai (aapka purana repo `heartaltafhussain-lgtm/nse500-gtf-scanner` hai), to wahi login karo.
      Nahi hai to: [github.com](https://github.com) → **Sign up** (free, email chahiye).
- [ ] **All Timeframe Stocks files** — workspace me `all-timeframe-stocks/` folder ready hai (saari updated files ke saath).
      Zaroorat ho to `all-timeframe-stocks.zip` bhi hai — **pehle extract karna hoga** (GitHub zip ke andar ki files khud nahi uthata).

---

## 📦 Option A — GitHub website se upload (easy, bina commands ke)

1. [github.com](https://github.com) pe login karo.
2. Top-right **"+"** button → **New repository**.
3. Form bharo:
   - **Repository name:** `all-timeframe-stocks`
   - **Description:** `All Timeframe Stocks - NSE 500 GTF Strict Top-3 (backtest-tested)`
   - **Public** ✅ (Private pe GitHub Pages free me nahi chalta)
   - ⚠️ **"Add a README file" ko UNCHECK rakho** (files khud upload karenge)
   - **Create repository** dabao
4. Agle page pe **"uploading an existing file"** link pe click karo.
5. **Apne computer pe `all-timeframe-stocks` folder kholo** aur **folder ke ANDAR ki saari files** drag-drop karo:
   - `index.html`, `all_timeframe_scanner.py`, `gtf_live_data.json`, `nifty500_universe.csv`, `requirements.txt`, `README.md`, `.gitignore`
   - **`history` folder bhi** (andar `all.json` hai — dashboard ke 📅 Date-wise History filter ki data)
     ⚠️ Pehli baar upload karna zaroori hai, uske baad bot khud har din ise update karta rahega
   - **`.github` folder bhi** (is andar workflow hai) — ⚠️ Windows me ye folder hidden hota hai:
     Explorer me **View → Show → Hidden items** ✅ karo, tab dikhega.
   - Agar `.github` folder drag nahi ho raha, to pehle `.github` folder ke andar `workflows` → `daily_scan.yml`
     file ko alag se drag karo (GitHub khud folder bana dega).
6. Neeche **Commit changes** → **Commit changes** button dabao.
7. ✅ Done! Ab neeche **"⚙️ Do Zaroori Settings"** section pe jao.

---

## 💻 Option B — Git commands se (recommended, copy-paste)

Apne computer pe **terminal / command prompt / PowerShell** kholo aur neeche ki commands ek-ek karke paste karo.

```bash
# 1) GitHub pe pehle repo banao (Option A ke steps 1-3 jaisa hi),
#    phir yahan commands chalao:

# 2) Git identity set karo (sirf pehli baar chahiye)
git config --global user.name "Aapka Naam"
git config --global user.email "aapka@email.com"

# 3) all-timeframe-stocks folder me jao
cd all-timeframe-stocks

# 4) Git repo banao aur files add karo
git init
git add .
git commit -m "All Timeframe Stocks v4.0 - strict backtest-tested filters"

# 5) Branch ka naam main rakho
git branch -M main

# 6) Apne GitHub repo se connect karo  (USERNAME ki jagah apna username)
git remote add origin https://github.com/USERNAME/all-timeframe-stocks.git

# 7) Upload karo
git push -u origin main
```

> Username/email maange to `gh auth login` ya browser popup se login ho jayega.

---

## ⚙️ DO ZAROORI SETTINGS (inke bina dashboard nahi chalega!)

### Setting 1 — Actions ko write permission (⚠️ SABSE IMPORTANT)

Iske bina bot roz ka data **commit nahi kar payega**.

1. Apne repo pe jao → **Settings** tab
2. Left menu me: **Actions → General**
3. Neeche scroll karo → **Workflow permissions**
4. Select karo: **"Read and write permissions"** ✅
5. **Save** dabao

### Setting 2 — GitHub Pages on karo

Iske bina website live nahi hogi.

1. Repo → **Settings** tab
2. Left menu me: **Pages**
3. **Build and deployment → Source:** `Deploy from a branch`
4. **Branch:** `main` → folder `/(root)` → **Save**
5. 1-2 minute wait karo, page refresh karo — upar green box me URL dikhega:
   ```
   https://USERNAME.github.io/all-timeframe-stocks/
   ```

---

## 🧪 Step — Pehla test (manual scan chalao)

1. Repo me **Actions** tab kholo.
2. Left me workflow: **"All Timeframe Stocks — NSE 500 Scan"**
3. Right side **"Run workflow"** button → branch `main` → **Run workflow**
4. Yellow circle → click karke **live logs** dekho (scanner 500 stocks download karta hai, ~3-5 minute lagenge).
5. **Green tick ✔️** aaye = sab sahi.
6. Ab apna URL kholo: `https://USERNAME.github.io/all-timeframe-stocks/`
7. 🔒 Password: **`7004602`**
8. Top-3 picks / watchlist / sector cards dikh rahe hain? **Setup complete! 🎉**

---

## 📱 Optional — Telegram alerts

Bot aapko Telegram pe picks bhej sakta hai:

1. Telegram pe [@BotFather](https://t.me/BotFather) ko message karo → `/newbot` → bot banao → **token** milega
2. Apne naye bot ko message karo (Start dabao)
3. Token se chat ID nikalo: browser me kholo
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → `"chat":{"id":123456...}`
4. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**
   - `TELEGRAM_BOT_TOKEN` = token
   - `TELEGRAM_CHAT_ID` = chat id
5. Agle scan se alerts aayenge ✅

---

## ⏰ Roz kya hoga (automation explained)

| Time (IST) | Kya hota hai |
|---|---|
| 15:45 (Mon–Fri) | GitHub Actions khud scanner chalata hai |
| ~15:50 | Naya `gtf_live_data.json` + CSV commit hota hai |
| Turant | Pages pe dashboard update ho jata hai |
| Picks mile to | Telegram alert |

> ⚠️ GitHub ka cron kabhi-kabhi 10-15 minute late ho sakta hai — normal hai.
> Market holiday pe bhi run hota hai, data wahi rahega (koi nuksan nahi).

---

## 🛠 Common Problems & Fixes

| Problem | Fix |
|---|---|
| **404 page / site not found** | Pages enable nahi hua (Setting 2) ya URL galat hai. `Settings → Pages` me green URL check karo. |
| **Actions fail at `git push` step** | Setting 1 miss hui — `Settings → Actions → General → Workflow permissions → Read and write` ✅ |
| **Commit says "No changes to commit"** | Normal hai — matlab data same hai. Fail nahi hai. |
| **`.github` folder dikh nahi raha** | Windows: Explorer me `View → Show → Hidden items` on karo. |
| **Pages me branch select nahi ho rahi** | Pehle kam se kam 1 commit karo (upload ya git push), tabhi branch dikhegi. |
| **Dashboard data purana dikh raha** | `index.html` me embedded demo data hota hai jab fetch fail ho. Browser me `Ctrl+F5` (hard refresh) karo. |
| **Private repo + Pages chahiye** | Free account pe Pages sirf Public repo me chalta hai. Public rakho (password se locked hai). |
| **Scanner fail, yfinance error** | Kabhi-kabhi Yahoo data slow hota hai — Actions me manually "Run workflow" dobara karo. |

---

## 🔄 Future me update kaise karein

- **Scanner filter badalna ho:** repo me `all_timeframe_scanner.py` kholo → **pencil icon ✏️** se edit karo → **Commit changes**. Agle scan se naya logic chalega.
- **Password badalna ho:** `index.html` kholo → `const PASSWORD = "7004602"` change karo → commit.
- **Nayi files add karni ho:** website se "Add file → Upload files", ya git commands se `git add . && git commit -m "update" && git push`.

---

⚠️ **Ek baar phir:** yeh project educational hai — investment advice nahi. Past performance ≠ future guarantee.
