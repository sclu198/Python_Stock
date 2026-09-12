# 設定指南

從零到每天早上收到 LINE 摘要，總共四步：**LINE → X → Claude → 排程**。

---

## 0. 先安裝

```bash
git clone https://github.com/sclu198/Python_Stock.git
cd Python_Stock
pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
```

之後所有金鑰都填在 `.env`，這個檔案已經被 `.gitignore` 排除，不會被推上 GitHub。

---

## 1. LINE：建立 bot 並取得 userId

### ⚠️ 先講一件重要的事

**LINE 的推播 API 沒辦法用 LINE ID（`brucelu215` 這種）當收件人。**
LINE ID 是給人在 App 裡搜尋好友用的，官方 API 完全不開放用它發訊息。
程式要發訊息給你，只能用 `U` 開頭的 33 碼 **userId**，而且這個 userId
是「某個 bot 眼中的你」——每個 bot 看到的 userId 都不一樣。

另外，以前很多人用的 **LINE Notify 已經在 2025/3/31 停止服務**，
所以現在正規做法是自己開一個 Messaging API bot，讓它發訊息給你。

### 步驟

1. 到 [LINE Developers Console](https://developers.line.biz/console/) 用你的 LINE 帳號登入。
2. 建立 **Provider**（隨便取名，例如 `bruce-personal`）。
3. 在該 Provider 底下建立 **Messaging API channel**（頻道名稱例如「股市摘要小幫手」）。
4. 進入該 channel 的 **Messaging API** 分頁：
   - 找到 **Channel access token (long-lived)**，按 Issue 產生 → 填進 `.env` 的
     `LINE_CHANNEL_ACCESS_TOKEN`
   - 同一頁有 **Bot basic ID** 與 QR code，**用你的手機掃描把這個 bot 加為好友**
     （沒加好友的話推播會被擋，回 403）
   - 同一頁往下找 **Your user ID**（`U` 開頭那串）→ 填進 `.env` 的 `LINE_TO_USER_ID`
5. 建議把同一頁的自動回覆訊息（Auto-reply messages）關掉，比較清爽。

### 如果 Console 上看不到 Your user ID

用附的臨時 webhook 抓：

```bash
python scripts/line_get_user_id.py     # 監聽 8000 埠
ngrok http 8000                        # 另開一個終端機
```

把 ngrok 給的 `https://xxxx.ngrok.io/webhook` 填進 Console 的 Webhook URL 並啟用，
然後用手機對這個 bot 隨便傳一則訊息，userId 就會印在終端機上。

### 驗證

```bash
python -m x_stock_tracker --check
```

看到 `✅ LINE 設定：userId 格式正確` 就對了。

---

## 2. X：取得貼文來源

程式支援兩種來源，`.env` 裡用 `X_SOURCE` 切換。

### 方案 A：官方 X API（`X_SOURCE=api`，推薦）

1. 到 [developer.x.com](https://developer.x.com/) 申請開發者帳號並建立 App。
2. 在 App 的 **Keys and tokens** 產生 **Bearer Token** → 填進 `X_BEARER_TOKEN`。

**費用注意：X 的 Free 方案不能讀取推文**（只能發文），要讀別人的貼文
至少需要 Basic 方案（目前約 US$200／月）。如果程式回報
`X API 回傳 403：目前的 API 方案沒有讀取推文的權限`，就是卡在這裡。

每天只抓一個帳號、一天一次，用量遠低於 Basic 方案的額度。

### 方案 B：RSS 鏡像（`X_SOURCE=rss`，省錢但不保證穩定）

自架一份 [RSSHub](https://docs.rsshub.app/)，然後：

```
X_SOURCE=rss
X_RSS_URL=https://你的rsshub網址/twitter/user/qq_timmy
```

公開的 Nitter / RSSHub 實例常常被 X 擋掉而失效，要長期穩定就自己架。
這個方案拿不到長貼文的完整內容時會只有前段，屬於已知限制。

---

## 3. Claude：分析用的 API 金鑰

1. 到 [console.anthropic.com](https://console.anthropic.com/) 建立 API key。
2. 填進 `.env` 的 `ANTHROPIC_API_KEY`。

預設用 `claude-opus-5` 搭配網路搜尋。想省錢可以在 `.env` 改成：

```
ANTHROPIC_MODEL=claude-sonnet-5
ANTHROPIC_EFFORT=medium
ENABLE_WEB_SEARCH=false
```

一天十幾則貼文的量，成本大約落在每月數美元的等級（實際依貼文長度而定）。

---

## 4. 先試跑一次

```bash
# 不推播，只把結果印在畫面上，也不會更新已讀狀態
python -m x_stock_tracker --dry-run

# 確認沒問題後正式跑一次（會真的發 LINE）
python -m x_stock_tracker
```

第一次執行會往回抓 `LOOKBACK_HOURS`（預設 24）小時內的貼文，
之後每次只抓「上次處理過的最後一則之後」的新貼文，不會重複推播。

---

## 5. 設定每天自動執行

### 方式 A：GitHub Actions（不用開電腦，推薦）

`.github/workflows/daily-x-stock-digest.yml` 已經寫好，只要到 repo 的
**Settings → Secrets and variables → Actions** 新增這些 secrets：

| Secret | 內容 |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude API 金鑰 |
| `X_BEARER_TOKEN` | X API Bearer Token |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE channel access token |
| `LINE_TO_USER_ID` | 你的 `U` 開頭 userId |

用 RSS 方案的話，另外加 `X_RSS_URL` secret，並在 **Variables** 加
`X_SOURCE=rss`。

預設排程是每天台北時間 07:30。想改時間就改 workflow 裡的 cron
（注意那是 UTC，台北時間要減 8 小時）。也可以在 Actions 分頁手動
`Run workflow` 立即跑一次。

> GitHub 的排程不保證準時，尖峰時段可能延遲幾分鐘到半小時，屬正常現象。

### 方式 B：自己的 Windows 電腦（工作排程器）

1. 開「工作排程器」→ 建立基本工作 → 每天 07:30。
2. 動作選「啟動程式」：
   - 程式：`python`
   - 引數：`-m x_stock_tracker`
   - 開始位置：`C:\path\to\Python_Stock`

### 方式 C：Linux / macOS cron

```cron
30 7 * * * cd /path/to/Python_Stock && /usr/bin/python3 -m x_stock_tracker >> logs/digest.log 2>&1
```

---

## 常見狀況

| 訊息 | 原因與處理 |
| --- | --- |
| `LINE 回傳 403：沒有推播權限` | 還沒把 bot 加為好友，或 userId 不屬於這個 channel |
| `LINE_TO_USER_ID 看起來不是 userId` | 填成 LINE ID 了，要填 `U` 開頭那串 |
| `X API 回傳 403` | X API 方案不含讀取推文，升級方案或改用 `X_SOURCE=rss` |
| `X API 回傳 429` | 超出流量限制，等額度重置後再跑 |
| `台股名錄無法使用` | 證交所／櫃買中心的 API 暫時無法連線，程式會改用快取或只靠模型判斷 |
| 台股代號看起來怪怪的 | 執行 `python scripts/verify_open_data.py` 看開放資料的實際欄位 |

---

## 台股名錄的資料來源

| 範圍 | 來源 | 網址 |
| --- | --- | --- |
| 上市 | 臺灣證券交易所 | `https://openapi.twse.com.tw/v1/opendata/t187ap03_L` |
| 上櫃 | 櫃買中心 | `https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O` |
| 公開發行、興櫃 | 公開資訊觀測站／TWSE | `https://openapi.twse.com.tw/v1/opendata/t187ap03_P` |

三份資料每天下載一次並存成本機快取（`data/tw_company_registry.json`）。
比對順序是 上市 → 上櫃 → 公開發行，所以同名時會優先給上市公司。

**這三個 API 的欄位名稱不一致**（證交所用中文欄位名、櫃買中心用英文欄位名），
程式用「候選欄位名 + 關鍵字推斷」來解析，對方改欄位名通常不會直接壞掉。
如果哪天真的解析不到，執行 `python scripts/verify_open_data.py`，
它會印出實際欄位名稱，再把名稱補進
`x_stock_tracker/tw_market/registry.py` 最上面的 `*_KEYS` 常數即可。
