# 設定指南

從零到每天早上收到 Telegram 摘要，總共四步：**Telegram → X → Claude → 排程**。

---

## 0. 先安裝

**需要 Python 3.10 以上**（建議 3.11 或更新）。分析用的 `anthropic` 套件本身
就要求 3.10+，Python 3.9 裝不起來。先確認版本：

```bash
python --version
```

版本太舊的話到 <https://www.python.org/downloads/> 安裝新版，
Windows 安裝時記得勾選 **Add python.exe to PATH**。

**先確認電腦上已經有哪些版本**，再決定要不要安裝：

```cmd
py -0
```

它會列出所有偵測到的 Python，標著 `*` 的是 `py` 的預設版本，例如：

```
-V:3.14 *        Python 3.14 (64-bit)
-V:3.9           Python 3.9 (64-bit)
```

**清單裡只要有 3.10 以上的版本就不必安裝**，直接用 Python launcher 指定它即可
（把下面的 `3.14` 換成你清單裡的版本號）：

```cmd
py -3.14 --version
py -3.14 -m pip install -r requirements.txt
py -3.14 -m x_stock_tracker --check
```

有多套 Python 時，用 `py -<版本>` 指定比改 PATH 乾淨——不會動到系統設定，
也不會影響其他還在用舊版的專案。

清單裡沒有 3.10 以上的版本才需要安裝，到
<https://www.python.org/downloads/> 下載，或用 winget：

```cmd
winget install -e --id Python.Python.3.13
```

> `py -3.11` 回報 `No suitable Python runtime found`，通常只是**你裝的不是 3.11**，
> 不是 PATH 設錯。先看 `py -0` 的清單，用清單上實際有的版本號。

只想先確認 Telegram 通不通、還不想動 Python 版本的話，
`pip install requests` 之後就能單獨執行 `scripts/telegram_get_chat_id.py`，
那支腳本不需要 anthropic。

```bash
git clone https://github.com/sclu198/Python_Stock.git
cd Python_Stock
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
```

之後所有金鑰都填在 `.env`，這個檔案已經被 `.gitignore` 排除，不會被推上 GitHub。

---

## 1. Telegram：建立 bot 並取得 chat id

Telegram 沒有地區限制，設定也比 LINE 單純，只有兩個值要填。

### 步驟

1. 在 Telegram 搜尋 **@BotFather**，送 `/newbot`。
2. 依提示取兩個名字：顯示名稱（隨意，例如「股市摘要小幫手」）和
   使用者名稱（必須以 `bot` 結尾）。BotFather 會給你一串 token，
   長得像 `123456789:AAH...`。
3. **在 Telegram 搜尋你剛建立的 bot，按下 Start**（或隨便傳一句話給它）。
   這步不能跳過——Telegram 規定 bot 不能主動私訊沒互動過的人。
4. 一行指令完成設定：

   ```bash
   python scripts/telegram_get_chat_id.py --token 你的token --save
   ```

   它會驗證 token、找出你的數字 chat id、把設定寫進 `.env`，
   並發一則測試訊息到你的 Telegram。收到測試訊息就代表通了。

   token 已經自己填進 `.env` 的話，直接跑
   `python scripts/telegram_get_chat_id.py --save` 就好；
   加上 `--no-test` 可以不發測試訊息。

### ⚠️ token 外洩就要重新產生

token 等同於 bot 的密碼，任何人拿到都能控制你的 bot。不小心貼到聊天室、
截圖或推上 GitHub 的話，到 @BotFather 送 `/revoke` 產一組新的，舊的立刻失效。
`.env` 已經被 `.gitignore` 排除，正常使用不會進版控。

### ⚠️ chat id 不能用 @使用者名稱

你的 Telegram 帳號是 `@SCLU0215`，但**私訊不能拿使用者名稱當收件人**，
Telegram Bot API 只接受數字 chat id（個人帳號是正數，群組是負數）。
只有公開頻道才可以用 `@頻道名稱`。

### 驗證

```bash
python -m x_stock_tracker --check
```

看到 `✅ Telegram：token 有效，bot 是 @你的bot名稱` 就對了。

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

# 確認沒問題後正式跑一次（會真的發 Telegram）
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
| `TELEGRAM_BOT_TOKEN` | BotFather 給的 bot token |
| `TELEGRAM_CHAT_ID` | 你的數字 chat id |

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
| `UnicodeDecodeError: 'cp950' codec can't decode byte`（跑 pip 時） | pip 太舊。先 `python -m pip install --upgrade pip` 再重跑 |
| `ModuleNotFoundError: No module named 'requests'` | 上一步的 `pip install -r requirements.txt` 沒成功，先把它跑過 |
| `Could not find a version that satisfies the requirement anthropic` 且提到 `require a different python version` | Python 版本低於 3.10。安裝 Python 3.11+ 後改用 `py -3.11 -m pip install -r requirements.txt` |
| `py -3.x`：`No suitable Python runtime found` | 那個版本沒安裝（不是 PATH 問題）。先跑 `py -0` 看清單，改用上面實際有的版本號 |
| `環境不符：這個程式需要 Python 3.10 以上` | 同上，執行時用到的仍是舊版 Python，改用 `py -3.11 -m x_stock_tracker` |
| `Telegram 回傳「chat not found」` | chat id 填錯，或還沒對 bot 按過 Start |
| `TELEGRAM_CHAT_ID 格式不對` | 填成 `@SCLU0215` 了，私訊要用數字 chat id |
| `Telegram 回傳 401` | bot token 不對，跟 @BotFather 重新確認 |
| `Telegram 回傳 403` | 你把 bot 封鎖了，解除封鎖即可 |
| `目前沒有任何訊息`（取 chat id 時） | 先對 bot 傳一則訊息再跑一次腳本 |
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

---

## 附錄：改用 LINE 推播

LINE 的 Messaging API 仍然保留在程式裡（`NOTIFIER=line`），如果之後區域限制
解除或你另外開了日本帳號，可以切回去用：

1. 到 [LINE Developers Console](https://developers.line.biz/console/) 建立
   Provider 與 **Messaging API channel**。
2. 在該 channel 的 Messaging API 分頁產生 **Channel access token**，填進
   `LINE_CHANNEL_ACCESS_TOKEN`；用手機掃 QR code 把 bot 加為好友。
3. 同一頁的 **Your user ID**（`U` 開頭）填進 `LINE_TO_USER_ID`；
   看不到的話用 `python scripts/line_get_user_id.py` 搭配 ngrok 取得。
4. `.env` 設 `NOTIFIER=line`。

注意 LINE ID（`brucelu215` 這種）不能當推播對象，只能用 `U` 開頭的 userId；
另外 LINE Notify 已於 2025/3/31 停止服務。
