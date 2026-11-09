---
name: openai-image
description: '使用 OpenAI 官方 Images API 產生靜態圖片與原生動畫 GIF。當使用者要求繪圖、畫圖、生圖、圖片生成、動畫貼圖、GIF、animated GIF、text-to-image、GPT Image 2.6、Sunburst、Flare，或要在 Codex / GitHub Copilot 呼叫 OpenAI 繪圖模型時使用。以 uv 執行隨附的零第三方依賴 Python CLI；GIF 直接由模型輸出，不逐格合成。'
---

# OpenAI 繪圖與原生 GIF

本 skill 僅安裝在目前專案的 `.agents/skills/openai-image`，供 Codex 與 Copilot 共用。所有 Python 命令必須透過 **uv** 執行，不使用裸 `python`、`pip` 或自行建立 venv。

## 能力與限制

- 靜態圖片：PNG、JPEG、WebP。
- **原生動畫 GIF**：使用 `output_format=gif`、`frame_count`、`frame_duration_ms`，單次呼叫 `/v1/images/generations`。
- 預設模型：`gpt-image-2.6-sunburst`；快速迭代可選 `gpt-image-2.6-flare`。不要把 `gpt-image2.6` 這種口語名稱直接當模型 ID。
- GIF 目前需要所選模型的 **GIF preview 存取權限**，不是只有 ChatGPT / Codex / Copilot 訂閱就能使用。
- GIF 支援 2–16 格，預設 9 格；每格預設 200 ms，最低 20 ms，API 四捨五入至 10 ms、編碼上限 655350 ms。預設動畫約 1.8 秒；實際時間以輸出資料為準。
- 不自行把同一張圖複製多格、不把 PNG 改名成 GIF，也不在失敗時偷偷改成多次生圖或其他付費服務。
- 此 CLI 專注文字生圖，不提供圖片編輯、串流、影片生成或本機動畫合成。沒有 Pillow、FFmpeg 或 OpenAI SDK 依賴。

## 工作流程

1. 判斷靜態圖片或動畫；保留使用者指定的主體、構圖、文字、風格與輸出路徑。
2. 對動畫補足「動作、固定鏡位、背景一致、首尾銜接」等描述。不要未經同意改變需求。影格數與速度未指定時採預設值；超過 API 限制時先說明並詢問取捨。
3. 提醒會使用 OpenAI API 額度；**只在使用者授權繪圖時呼叫**。僅建立 skill、查看說明或 dry-run 不代表授權付費測試。不得傳送原始碼、憑證或其他機密資料。
4. 確認 `uv --version`。若 uv 未安裝，請使用者安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/)，不要擅自安裝系統工具。
5. 透過 `uv run --env-file <專案根目錄的 .env 路徑>` 載入本機設定。確認 `OPENAI_API_KEY` 是否存在即可；絕不列印 `.env` 或 key 的內容、不要求貼到對話、不寫入原始碼或版本庫。此工具只連線到 `https://api.openai.com`，不讀取 `OPENAI_BASE_URL`。
6. 使用 [CLI](./scripts/openai_image.py) 先 dry-run 檢查參數，再執行一次真實請求。腳本與 `.env` 路徑必須從 **skill 所在位置解析**，不要假設使用者的 CWD 一定是專案根目錄。若 `.env` 不存在，提示使用者從 `.env.example` 建立；若改用既有程序環境變數，省略 `--env-file`，不得覆蓋使用者既有設定。
7. 檢查結束碼與結果 JSON。工具驗證回傳格式，對 GIF 解析區塊、確認至少兩格，回報實際尺寸、影格數及總時長，再寫入檔案。這是容器與格式檢查，不是完整像素解碼或視覺品質驗收；具備圖片預覽能力時再檢查畫面。
8. 提供產出檔案連結；GIF 若未預覽不可宣稱視覺效果已驗證。影格數不符時呈現 warning，不隱瞞。

## 初次設定（PowerShell）

專案根目錄已提供 `.env`，在本機編輯並填入 `OPENAI_API_KEY` 即可；`OPENAI_IMAGE_MODEL` 預設為 `gpt-image-2.6-sunburst`。`.env` 已被 Git 排除，不可提交，也不要將其內容貼到對話。

全新 clone 不會包含 `.env`，請先從可版控的 `.env.example` 複製：

```powershell
Copy-Item .env.example .env
```

只在 `.env` 不存在時執行複製，不要覆蓋既有憑證。之後使用下方含 `--env-file .env` 的命令，由 **uv** 載入 dotenv，不需要安裝 `python-dotenv` 或重新啟動 IDE。

也可選擇不使用檔案，在自己的終端機隱藏輸入：

```powershell
$secret = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
Remove-Variable secret
```

這只影響該 PowerShell 程序及其子程序；不會修改已在執行的 IDE / agent 環境。採此方式時可省略 `--env-file .env`，在同一終端機執行 CLI。Python 腳本本身不解析 `.env`，必須透過 uv 的 `--env-file` 載入；已存在的程序環境變數優先於檔案內的同名設定。

## 命令範例

以下以專案根目錄為 CWD；其他位置請改成腳本絕對路徑。需要 Python 3.11+，uv 會依 PEP 723 選擇環境；首次缺少 Python 時可能下載執行環境，但不安裝任何第三方 Python 套件。

### 靜態圖片

```powershell
uv run --env-file .env --script .agents\skills\openai-image\scripts\openai_image.py --prompt '原創水彩風格的台灣山林與晨霧，沒有文字' --output outputs\mountains.png --dry-run
uv run --env-file .env --script .agents\skills\openai-image\scripts\openai_image.py --prompt '原創水彩風格的台灣山林與晨霧，沒有文字' --output outputs\mountains.png
```

### 模型直接生成動畫 GIF

```powershell
uv run --env-file .env --script .agents\skills\openai-image\scripts\openai_image.py --prompt '原創像素風小貓輕輕揮手，固定鏡位，背景與角色一致，流暢循環，首尾自然銜接' --output outputs\cat-wave.gif --frames 9 --frame-duration-ms 200 --dry-run
uv run --env-file .env --script .agents\skills\openai-image\scripts\openai_image.py --prompt '原創像素風小貓輕輕揮手，固定鏡位，背景與角色一致，流暢循環，首尾自然銜接' --output outputs\cat-wave.gif --frames 9 --frame-duration-ms 200
```

預設不指定尺寸，由 API 使用模型及 GIF 格式適用的尺寸。需要尺寸時傳入 `--size auto` 或 `--size WIDTHxHEIGHT`；自訂尺寸須為 16 的倍數、長寬比介於 1:3 與 3:1，**GIF 另有模型限制**。不要假設靜態 1024×1024 尺寸一定可用於 GIF。

### 選用參數

- `--model gpt-image-2.6-flare`：指定模型；優先順序為命令列、`OPENAI_IMAGE_MODEL`、預設 Sunburst。
- `--quality low|medium|high|auto`：渲染品質；省略採 API 預設。
- `--complexity low|medium|high`：構圖規劃量，獨立於 quality；省略採模型預設。
- `--background transparent`：只供 PNG / WebP 使用。
- `--prompt-file <UTF-8檔案>`：多行提示詞，與 `--prompt` 二擇一。
- `--format png|jpeg|webp|gif`：通常不必指定，副檔名會自動判斷；明確指定時必須與副檔名相符。
- `--timeout 300`：逾時秒數；不自動重試。
- `--overwrite`：使用者明確允許時才覆寫；預設拒絕覆寫。
- `--dry-run`：不需要 API key、不連網、不產生檔案；只列出 endpoint、請求 JSON 及輸出路徑，**會包含提示詞，勿用機密內容**。

不傳送 `response_format`、`stream`、`partial_images`、`output_compression` 等 GIF 不適用參數。`n=1` 是一個完整動畫檔，不是影格數。

## 錯誤處理

- 缺少 key：停止，請使用者在自己的環境設定；不可將 key 貼到對話。
- HTTP 401 / 403 / 404：檢查憑證、完整模型 ID、組織驗證及 GIF preview 權限。
- HTTP 400：檢查尺寸、格式、影格參數及模型支援；不要自動降級為其他格式或合成方案。
- HTTP 429、5xx、逾時或連線中斷：可能已處理並計費；先回報，經使用者同意再重送。
- 非動畫 GIF、錯誤格式、無效 Base64 或不完整 GIF：拒絕成功回報，不寫入目標檔案。
- 輸出路徑不存在時自動建立父資料夾；既有檔案不會預設被取代。檔案系統需支援硬連結以原子方式保存而不覆寫；不支援時會回報錯誤，不會默默覆寫。

## 驗證

[離線測試](./tests/test_openai_image.py)只使用本機 HTTP 模擬伺服器，不讀取真實 key、不連 OpenAI、不計費：

```powershell
uv run --script .agents\skills\openai-image\tests\test_openai_image.py
```

測試不代表已取得模型 / GIF preview 權限或已完成付費端對端驗證。實際生成需有效 key 與使用者授權。

## 在 agent 中呼叫

- Copilot：在此專案開新對話後使用 `/openai-image`，或直接說「用 OpenAI 畫一張圖片／製作動畫 GIF」。
- Codex：在此專案中使用 `$openai-image`，或以自然語言要求使用此 skill。
- 找不到時確認 harness 支援 `.agents/skills`，並重新開啟對話或重載其技能清單；不要複製同名 skill 到多個位置造成重複發現。

## 官方參考

實作參數依據 2026-11-09 查閱的官方文件；模型存取、限制及價格可能變動。

- [圖片生成指南：GPT Image 2.6](https://developers.openai.com/api/docs/guides/image-generation#gpt-image-26)
- [Images API：原生 GIF 參數](https://developers.openai.com/api/reference/resources/images/methods/generate)
- [Sunburst 模型](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst)
- [Flare 模型](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Copilot CLI skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)
