# AI Assistant Instructions

## Language
- Always respond in Traditional Chinese (Taiwan, zh-TW).
- 所有回答、說明、分析、錯誤解釋皆使用繁體中文。
- 即使使用者提供英文內容或圖片，也必須使用繁體中文回答。
- 程式碼、變數名稱、API 名稱與技術術語可保留英文。
- 除非使用者明確要求英文，否則不要使用英文回答。

## Coding
- 程式碼說明使用繁體中文。
- 優先提供清楚、可執行的程式碼。
- 解釋錯誤時，使用繁體中文說明原因及修正方法。

## Skill 維護
- 以 [openai-image](./.agents/skills/openai-image) 為唯一可發布的 skill 來源；保持整個資料夾可獨立複製，所有 skill 資源連結都必須在套件內。
- 不假設 skill 的安裝位置或使用者的工作目錄；腳本從 skill 根目錄解析，憑證與輸出使用使用者工作專案的路徑。
- 透過 uv 執行 Python，維持 PEP 723 宣告與零第三方 Python 依賴。
- 修改後執行 `uv run --no-env-file --script .agents\skills\openai-image\tests\test_openai_image.py`；此測試不呼叫 OpenAI、不使用真實 key。
- 不讀取或輸出 `.env` 內容，不提交憑證或生成圖片，不因整理、安裝或測試 skill 而執行付費生成。
- 安裝方式或 CLI 行為異動時，同步更新 [README](./README.md)、[SKILL.md](./.agents/skills/openai-image/SKILL.md) 與[使用指南](./.agents/skills/openai-image/references/usage.md)。
