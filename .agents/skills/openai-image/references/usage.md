# 設定與 CLI 使用指南

## 前置條件

- 安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/)，並以 `uv --version` 確認。
- 需要 Python 3.11+。腳本使用 PEP 723 宣告環境，第三方依賴為零；uv 首次缺少合適的 Python 時可能下載執行環境。
- 真實生成需要 OpenAI API 金鑰與所選模型權限。ChatGPT、Copilot 或 Codex 訂閱不等於 API 額度；原生 GIF 另需 GIF preview 存取權限。
- dry-run 與測試不呼叫 OpenAI，也不需要 API 金鑰。

## 路徑與初次設定（PowerShell）

`$skillDir` 必須指向實際安裝的 `openai-image` 資料夾。以下示範從本儲存庫根目錄執行；個人安裝時改用 `Join-Path $HOME '.agents\skills\openai-image'`，其他 harness 則使用其實際安裝位置。

```powershell
$skillDir = (Resolve-Path '.agents\skills\openai-image').Path
$script = Join-Path $skillDir 'scripts\openai_image.py'
```

之後可切換至要存放圖片的工作專案；腳本使用絕對路徑，輸出則相對於目前工作目錄。請在**使用者工作專案**設定金鑰，不要將憑證存入共用或個人的 skill 安裝目錄。

若選用 dotenv，在工作專案建立設定檔：

```powershell
$envFile = Join-Path (Get-Location).Path '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath (Join-Path $skillDir 'assets\.env.example') -Destination $envFile
}
```

在自己的編輯器填入 `OPENAI_API_KEY`。範本中的 key 是空白，`OPENAI_IMAGE_MODEL` 預設為 `gpt-image-2.6-sunburst`。不要覆蓋既有設定；確認目的專案的 `.gitignore` 排除 `.env`、`.env.*` 與輸出資料夾，且只允許不含金鑰的 `.env.example` 被提交。

不要列印設定檔、把金鑰貼到對話或寫入原始碼。腳本本身不解析 dotenv；使用 `uv run --env-file "$envFile"` 載入，無須安裝 `python-dotenv` 或重新啟動 IDE。已存在的程序環境變數優先於檔案中的同名設定。

也可由使用者在自己的終端機隱藏輸入：

```powershell
$secret = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
Remove-Variable secret
```

這只影響該 PowerShell 與其子程序，不會修改已執行的 IDE／agent 環境。使用程序環境變數時，將下列 `--env-file "$envFile"` 換成 `--no-env-file`，並在同一終端機執行。

## 靜態圖片

先執行不計費的參數檢查：

```powershell
uv run --no-env-file --script "$script" --prompt '原創水彩風格的台灣山林與晨霧，沒有文字' --output outputs\mountains.png --dry-run
```

**僅在使用者授權繪圖後**才執行真實 API 請求：

```powershell
uv run --env-file "$envFile" --script "$script" --prompt '原創水彩風格的台灣山林與晨霧，沒有文字' --output outputs\mountains.png
```

## 原生動畫 GIF

```powershell
uv run --no-env-file --script "$script" --prompt '原創像素風小貓輕輕揮手，固定鏡位，背景與角色一致，流暢循環，首尾自然銜接' --output outputs\cat-wave.gif --frames 9 --frame-duration-ms 200 --dry-run
```

確認參數並取得付費請求授權後：

```powershell
uv run --env-file "$envFile" --script "$script" --prompt '原創像素風小貓輕輕揮手，固定鏡位，背景與角色一致，流暢循環，首尾自然銜接' --output outputs\cat-wave.gif --frames 9 --frame-duration-ms 200
```

GIF 由模型單次直接輸出，不逐格生成、不使用 FFmpeg 或 Pillow。支援 2–16 格，預設 9 格、每格 200 ms。每格允許 20–655350 ms，API 會四捨五入至 10 ms。實際影格數與總時長以輸出 JSON 為準。

預設不指定尺寸。自訂 `--size WIDTHxHEIGHT` 須為 16 的倍數、長寬比介於 1:3 與 3:1；GIF 另有模型尺寸限制，不要假設靜態圖片的 1024×1024 一定適用。

## 參數速查

| 參數 | 說明 |
| --- | --- |
| `--prompt` / `--prompt-file` | 二擇一；檔案須為 UTF-8，提示詞 1–32000 字元。 |
| `--output` | 必填；PNG、JPG／JPEG、WebP、GIF 副檔名決定格式。 |
| `--model` | 優先於 `OPENAI_IMAGE_MODEL`；預設 `gpt-image-2.6-sunburst`，快速迭代可用 `gpt-image-2.6-flare`。 |
| `--format` | `png`、`jpeg`、`webp`、`gif`；明確指定時必須與副檔名一致。 |
| `--size` | `auto` 或 `WIDTHxHEIGHT`；省略時由 API 決定。 |
| `--quality` | `low`、`medium`、`high`、`auto`。 |
| `--complexity` | `low`、`medium`、`high`；獨立於 quality。 |
| `--background` | `auto`、`opaque`、`transparent`；透明背景僅用於 PNG／WebP。 |
| `--frames` | 僅 GIF，2–16，預設 9。 |
| `--frame-duration-ms` | 僅 GIF，20–655350，預設 200。 |
| `--timeout` | 正數且有限，預設 300 秒；不自動重試。 |
| `--overwrite` | 只有使用者明確同意時才使用；預設拒絕覆寫。 |
| `--dry-run` | 不呼叫 API、不寫檔、不需要 key；會顯示提示詞，勿包含機密資料。 |

不傳送 `response_format`、`stream`、`partial_images`、`output_compression`。`n=1` 是一個完整動畫檔，不是影格數。

## 結果與故障處理

- 成功時 stdout 輸出 JSON，包含輸出路徑、格式等資訊；GIF 另有實際尺寸、影格數及總時長。
- 失敗時 stderr 顯示訊息、結束碼為非零；不要把錯誤訊息當作成功產出。
- 401／403／404：檢查金鑰、完整模型 ID、組織驗證及 GIF preview 權限。
- 400：檢查格式、尺寸與模型支援；不要未經同意切換其他模型、格式或服務。
- 429、5xx、逾時或斷線：請求可能已處理並計費，先回報並取得重送同意。
- 程式只連線至 `https://api.openai.com`，不讀取 `OPENAI_BASE_URL`，也不跟隨 API 重新導向。
- 檔案驗證是容器／格式檢查，不是完整像素解碼或視覺品質驗收。未預覽時不要宣稱視覺效果已驗證。
- 保存檔案預設使用硬連結達成原子寫入且不覆寫，目的檔案系統需支援硬連結；不支援時回報錯誤，不會偷偷改為覆寫。
