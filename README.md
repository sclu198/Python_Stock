# Python_Stock

台股相關的小工具集合。

## x_stock_tracker — X 貼文每日投資摘要

每天自動抓取指定 X（Twitter）帳號（預設 [@qq_timmy](https://x.com/qq_timmy)）的新貼文，
用 Claude 分析成投資備忘錄格式，再推播到自己的 Telegram。

每則貼文會整理出六件事：

1. 貼文提到的**公司名稱**與**所屬國家／股票市場**
2. **股票代號** —— 台股一律用證交所／櫃買中心的開放資料查證，查不到就標示「未上市」
3. **三層產業分類**：第一層大產業 → 第二層次產業 → 第三層商業模式／供應鏈角色
4. 貼文內容的**條列式摘要**
5. 這則內容對**市場或公司的影響、市場如何解讀**
6. 對投資這家公司是**利多還是利空**，以及理由

### 實際收到的訊息長這樣

```
📊 X 貼文投資摘要
👤 @qq_timmy｜2026-09-12 07:30
📝 1 則貼文、2 家公司
🏷 台積電（TSMC）、輝達（NVIDIA）

──────────────
【貼文 1/1】09/12 01:30
🔗 https://x.com/qq_timmy/status/180...

📝 內容摘要
  ・台積電 CoWoS 產能在 2026 年再度上修
  ・傳輝達追加訂單

🏢 台積電（TSMC）
  📍 市場：台灣／上市（TWSE）
  🔢 代號：2330
  🏭 產業：半導體業 ＞ 晶圓代工
  🔧 商業模式／供應鏈角色：替 IC 設計公司代工先進製程晶圓，並提供 CoWoS 先進封裝
  📈 影響與市場看法：市場視為 AI 需求延續的訊號，法人上修明年營收預估
  💡 投資影響：🔺 利多｜先進封裝為瓶頸環節，產能上修代表訂單能見度高
```

### 快速開始

```bash
pip install -r requirements.txt
cp .env.example .env     # 填入 X、Claude、Telegram 三組金鑰
python -m x_stock_tracker --check      # 檢查設定與連線
python -m x_stock_tracker --dry-run    # 試跑，只印在畫面上
python -m x_stock_tracker              # 正式執行，推播到 Telegram
```

完整設定步驟（含如何取得 Telegram chat id、X API 的方案限制）請看
**[docs/SETUP.md](docs/SETUP.md)**。

兩件開始前要知道的事：

- **Telegram 的收件人不能用 @使用者名稱。** Bot API 私訊只接受數字 chat id，
  而且你必須先對自己的 bot 按過 Start；執行
  `python scripts/telegram_get_chat_id.py` 就會印出來。
- **X 的免費 API 方案不能讀取推文**，需要 Basic 以上方案，或改用
  `X_SOURCE=rss` 走自架的 RSS 鏡像。

推播管道用 `NOTIFIER` 切換：`telegram`（預設）、`line`、`stdout`（測試用）。

### 每天自動執行

`.github/workflows/daily-x-stock-digest.yml` 已設定每天台北時間 07:30 執行，
只要在 repo 的 Actions secrets 填好金鑰即可；也可以改用 Windows 工作排程器或 cron。

### 台股代號怎麼查的

| 範圍 | 來源 |
| --- | --- |
| 上市 | [TWSE `t187ap03_L`](https://openapi.twse.com.tw/v1/opendata/t187ap03_L) |
| 上櫃 | [TPEx `mopsfin_t187ap03_O`](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O) |
| 公開發行、興櫃 | [TWSE `t187ap03_P`](https://openapi.twse.com.tw/v1/opendata/t187ap03_P) |

模型可能記錯股票代號，所以台股的代號、市場別與第一層產業一律以這三份官方資料為準，
模型的答案只用在它們沒涵蓋的地方（外國股票、次產業、商業模式判斷）。

### 開發

```bash
python -m unittest discover -s tests -t .   # 52 個測試，不需連網
python scripts/verify_open_data.py          # 檢查三個開放資料 API 的欄位
```

程式結構：

```
x_stock_tracker/
  cli.py            流程進入點
  sources/          貼文來源（X API v2 / RSS 備援）
  tw_market/        台股名錄：下載、快取、公司名 → 代號查詢
  analysis/         Claude 分析 + 用名錄校正結果
  report.py         排版成推播訊息
  notify/           Telegram Bot API 推播（另含 LINE 備用管道）
```

## TW_Stock Crawler.py

盤中即時報價爬蟲（原有工具），從證交所 MIS API 抓指定股票的成交價並在
Jupyter Notebook 中每秒更新。
