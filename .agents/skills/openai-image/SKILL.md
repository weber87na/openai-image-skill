---
name: openai-image
description: '使用 OpenAI 官方 Images API 產生靜態圖片與原生動畫 GIF。當使用者要求繪圖、畫圖、生圖、圖片生成、動畫貼圖、GIF、animated GIF、text-to-image、GPT Image 2.6、Sunburst、Flare，或要在 Codex / GitHub Copilot 呼叫 OpenAI 繪圖模型時使用。以 uv 執行隨附的零第三方依賴 Python CLI；GIF 直接由模型輸出，不逐格合成。'
compatibility: '適用於 GitHub Copilot 與 OpenAI Codex；需要 uv、Python 3.11+。實際生成需要 OPENAI_API_KEY 與 api.openai.com HTTPS 存取權限；離線測試與 dry-run 不需要 API 金鑰。'
---

# OpenAI 繪圖與原生 GIF

此 skill 是可獨立複製的 Agent Skills 套件，支援專案與個人安裝。以本檔所在資料夾為 **skill 根目錄**，不要假設固定安裝位置或目前工作目錄。所有 Python 命令必須透過 **uv** 執行，不使用裸 `python`、`pip` 或自行建立 venv。

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
5. 確認 `OPENAI_API_KEY` 是否存在即可；絕不列印 `.env` 或 key 的內容、不要求貼到對話、不寫入原始碼或版本庫。有既有程序環境變數時直接使用；需要 dotenv 時，確認使用者工作專案或明確指定的 `.env` 絕對路徑，以 `uv run --env-file <路徑>` 載入。不要到 skill 安裝目錄尋找別的專案憑證。此工具只連線到 `https://api.openai.com`，不讀取 `OPENAI_BASE_URL`。
6. 從 skill 根目錄解析 [CLI](./scripts/openai_image.py) 的絕對路徑，先 dry-run 檢查參數，再執行一次真實請求。輸出路徑以使用者工作專案為準，不寫入 skill 安裝目錄。初次設定使用隨附的[空白設定範本](./assets/.env.example)與[使用指南](./references/usage.md)，不得覆蓋既有設定。
7. 檢查結束碼與結果 JSON。工具驗證回傳格式，對 GIF 解析區塊、確認至少兩格，回報實際尺寸、影格數及總時長，再寫入檔案。這是容器與格式檢查，不是完整像素解碼或視覺品質驗收；具備圖片預覽能力時再檢查畫面。
8. 提供產出檔案連結；GIF 若未預覽不可宣稱視覺效果已驗證。影格數不符時呈現 warning，不隱瞞。

## 執行方式

先依載入位置設定 `$skillDir` 為 skill 根目錄的絕對路徑，再從使用者工作專案執行。完整設定、靜態圖片／GIF 範例及參數見[使用指南](./references/usage.md)。

```powershell
$script = Join-Path $skillDir 'scripts\openai_image.py'
uv run --no-env-file --script "$script" --prompt '原創水彩風格的台灣山林與晨霧，沒有文字' --output outputs\mountains.png --dry-run
```

- `--dry-run` 不需要 API key、不呼叫 API、不寫檔；會顯示提示詞，不可使用機密內容。uv 首次缺少 Python 時仍可能下載執行環境。
- 只有取得繪圖授權後才移除 `--dry-run`。需要 dotenv 時將 `--no-env-file` 換成 `--env-file <使用者指定的 .env 絕對路徑>`。
- GIF 使用 `.gif` 副檔名，可指定 `--frames 9 --frame-duration-ms 200`；`n=1` 代表完整動畫，不是影格數。
- 不傳送 `response_format`、`stream`、`partial_images`、`output_compression` 等 GIF 不適用參數。
- 預設不指定尺寸；自訂尺寸須為 16 的倍數、長寬比介於 1:3 與 3:1。GIF 另有模型尺寸限制，不要假設靜態尺寸一定適用。
- 不提供 `--overwrite`，除非使用者明確同意取代既有檔案。

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
$tests = Join-Path $skillDir 'tests\test_openai_image.py'
uv run --no-env-file --script "$tests"
```

測試不代表已取得模型 / GIF preview 權限或已完成付費端對端驗證。實際生成需有效 key 與使用者授權。

## 在 agent 中呼叫

- Copilot：使用 `/openai-image`，或直接說「用 OpenAI 畫一張圖片／製作動畫 GIF」。
- Codex：使用 `$openai-image`，或以自然語言要求使用此 skill；[Codex 介面設定](./agents/openai.yaml)不影響共用指令。
- 找不到時確認目前 harness 支援安裝位置，並重新開啟對話或重載技能清單。Copilot CLI 與 Codex 可共用 `.agents/skills`；部分 Copilot harness 使用 `.github/skills`。請移動完整資料夾，不要複製同名 skill 到多個會同時掃描的位置。

## 官方參考

實作參數依據 2026-11-09 查閱的官方文件；模型存取、限制及價格可能變動。

- [圖片生成指南：GPT Image 2.6](https://developers.openai.com/api/docs/guides/image-generation#gpt-image-26)
- [Images API：原生 GIF 參數](https://developers.openai.com/api/reference/resources/images/methods/generate)
- [Sunburst 模型](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst)
- [Flare 模型](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Copilot CLI skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)
