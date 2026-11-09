# OpenAI Image Skill

適用於 **GitHub Copilot 與 OpenAI Codex** 的 [Agent Skills](https://agentskills.io/specification) 套件：透過 OpenAI Images API 產生靜態圖片與原生動畫 GIF，以 **uv + Python 3.11+** 執行，無第三方 Python 套件依賴。

這是獨立的工作流程封裝，不是 OpenAI 官方產品；API 費用、模型存取權限與限制由 OpenAI 決定。

## 功能

- PNG、JPEG、WebP，以及模型直接輸出的動畫 GIF。
- 預設 `gpt-image-2.6-sunburst`，可選 `gpt-image-2.6-flare` 或使用 `--model` 指定。
- 原生 GIF 預設 9 格、每格 200 ms，不逐格合成；需要帳號具備 GIF preview 權限。
- `--dry-run` 檢查參數，不呼叫 API、不產生圖片、不需要金鑰。
- 預設不覆寫檔案、不自動重試付費請求、不將金鑰傳送到自訂端點。
- 隨附離線測試、設定範本與 Codex 介面中繼資料。

## 套件結構

唯一的 skill 來源是 [openai-image](./.agents/skills/openai-image)。安裝時請複製**完整資料夾**，不是只有 [SKILL.md](./.agents/skills/openai-image/SKILL.md)。

```text
.agents/skills/openai-image/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── .env.example
├── references/
│   └── usage.md
├── scripts/
│   └── openai_image.py
└── tests/
    └── test_openai_image.py
```

[SKILL.md](./.agents/skills/openai-image/SKILL.md) 使用標準 `name`、`description`、`compatibility` frontmatter；資料夾名稱與 skill 名稱均為 `openai-image`。[agents/openai.yaml](./.agents/skills/openai-image/agents/openai.yaml) 提供 Codex 介面資訊，Copilot 不需要依賴此檔案。

## 安裝

先下載儲存庫；若儲存庫為 Private，須以有存取權限的 GitHub 帳號認證：

```powershell
git clone https://github.com/weber87na/openai-image-skill.git
Set-Location openai-image-skill
```

### 專案使用

Copilot CLI、Codex 與支援此位置的 VS Code harness 可直接讀取本儲存庫的 [.agents/skills](./.agents/skills)。要用於另一個專案，將完整的 [openai-image](./.agents/skills/openai-image) 資料夾複製到該專案對應位置。

| 用戶端 | 專案位置 | 個人位置 |
| --- | --- | --- |
| Copilot CLI | `.agents/skills/openai-image` 或 `.github/skills/openai-image` | `~/.agents/skills/openai-image` 或 `~/.copilot/skills/openai-image` |
| Codex | `.agents/skills/openai-image` | `~/.agents/skills/openai-image` |
| VS Code Copilot | 優先使用目前 harness 支援的位置；官方主要位置為 `.github/skills/openai-image` | `~/.copilot/skills/openai-image` |

VS Code 的 Local harness 也支援 `.agents/skills`。其他 harness 的支援位置請以其 Agent Customizations 介面與[官方文件](https://code.visualstudio.com/docs/agent-customization/agent-skills#_skill-locations)為準。不要為了相容性在同一個搜尋範圍留下多份同名 skill；需要時移動完整資料夾。

### Copilot CLI／Codex 個人共用安裝

在下載的儲存庫根目錄執行；已安裝時會停止，不覆寫既有檔案：

```powershell
$skillsDir = Join-Path $HOME '.agents\skills'
$destination = Join-Path $skillsDir 'openai-image'
if (Test-Path -LiteralPath $destination) {
    throw 'openai-image 已存在，請先檢查原有安裝，不要直接覆寫。'
}
New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
Copy-Item -LiteralPath '.agents\skills\openai-image' -Destination $destination -Recurse
```

個人安裝適用於其他工作專案；避免同時在個人與專案位置安裝同名 skill。這是複製安裝，不會自動更新；更新前請先檢查本機修改。

重新開啟對話或重新載入技能清單後：

- Copilot：輸入 `/openai-image`，或要求「用 OpenAI 畫一張圖片」。
- Codex：輸入 `$openai-image`，或以自然語言指定使用此 skill。

## 不計費的快速驗證

先安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/)，再於儲存庫根目錄執行：

```powershell
uv --version
uv run --no-env-file --script .agents\skills\openai-image\scripts\openai_image.py --prompt '原創水彩風格的台灣山林與晨霧' --output outputs\mountains.png --dry-run
uv run --no-env-file --script .agents\skills\openai-image\tests\test_openai_image.py
```

測試只使用本機 HTTP 模擬伺服器與假金鑰；不連 OpenAI、不計費。uv 首次缺少合適的 Python 時仍可能下載執行環境。

GitHub Actions 會在 Windows／Linux、Python 3.11／3.13 執行同一份離線測試。這些測試不代表已驗證帳號的模型權限、真實 API 回應或圖片視覺品質。

## 設定金鑰與實際生成

請閱讀[設定與 CLI 使用指南](./.agents/skills/openai-image/references/usage.md)，將[空白設定範本](./.agents/skills/openai-image/assets/.env.example)複製到**使用者工作專案**的 `.env`，只在本機填入金鑰。已有設定時不得覆寫。

- 不要把 `.env`、真實金鑰或生成圖片提交到 Git。
- 不要把金鑰貼到聊天、放進提示詞或寫入 skill 安裝目錄。
- 目的專案也必須排除 `.env`、`.env.*` 與輸出資料夾；本儲存庫的 [.gitignore](./.gitignore) 不會自動套用到其他專案。
- 實際生成會使用 OpenAI API 額度；只在使用者授權後執行。
- ChatGPT、Copilot 或 Codex 訂閱不等於 OpenAI API 額度或 GIF preview 權限。

## 授權

目前未指定開源授權；不應將可存取本儲存庫視為取得再散布或其他開源授權。

## 規格與官方文件

- [Agent Skills 規格](https://agentskills.io/specification)
- [GitHub Copilot CLI skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)
- [VS Code Agent Skills](https://code.visualstudio.com/docs/agent-customization/agent-skills)
- [Codex skills](https://developers.openai.com/codex/skills)
- [OpenAI 圖片生成指南](https://developers.openai.com/api/docs/guides/image-generation#gpt-image-26)
