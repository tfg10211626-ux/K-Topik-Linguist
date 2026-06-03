# K-Topik Linguist — 產品需求文件（PRD）

| 項目 | 內容 |
|------|------|
| 版本 | v1.0 |
| 狀態 | 上線前（產品尚未對外公開網站） |
| 最後更新 | 2026-06-03 |
| 主要讀者 | 產品、設計、前端、後端、內容 |

---

## 1. 產品概述

**K-Topik Linguist** 是以韓檢（TOPIK）分級詞庫為基礎的韓語自學網站。使用者選擇難度後，可透過 **劇本模式**（情境造句與口說演戲）、**學習模式**（段落詞彙分析）、**考試模式**（AI 出題練習）學習，並在 **我的單字庫** 收藏、管理從各模式存下的單字。

**產品定位：** 把韓文當韓劇學——在短時間內掌握當級重點單字，並用錄音與 AI 回饋強化口說。

**上線階段：** 目前為本機／內部驗證環境；**正式對外網站尚未上線**，本 PRD 描述上線前應達成的產品範圍與驗收基準。

---

## 2. 目標使用者

### 2.1 主要使用者（大宗）：TOPIK 自學者

- 以中文為介面語言，自主安排學習進度。
- 目標：備考 TOPIK I/II，或依「初級／中級／高級」對應自身程度練習。
- 典型場景：通勤碎片時間用劇本模式練幾個詞；讀韓文文章時用學習模式標註詞彙；考前用考試模式刷題；把難記的詞收進單字庫複習。

### 2.2 次要使用者（本期不優先）

- 補習班學員（由老師指定級別）——本期無班級／後台帳號。
- B2B 機構授權——列為上線後擴展，不在本期必達。

---

## 3. 問題與價值主張

| 痛點 | 本產品解法 |
|------|------------|
| 背單字缺乏情境，不會用 | 劇本模式依詞生成戲劇風格例句，並可錄音演戲取得評分 |
| 讀韓文不知哪些詞屬於當前程度 | 學習模式依 session 難度比對官方詞書 |
| 缺乏即時練習題 | 考試模式由 Gemini 依級別與題型出題（初級另有離線題庫） |
| 學過的詞容易散失 | 劇本／學習模式可收藏至「我的單字庫」，支援批次刪除 |

---

## 4. 產品目標與成功指標

### 4.1 業務目標（上線後 8 週內可調）

1. 自學者能在 **3 步內** 開始任一學習模式（首頁：難度 → 模式 → 進入頁）。
2. 劇本模式完成一輪核心閉環：選詞 → 生成情境 → 錄音 → 取得評分與示範音。
3. 單字庫成為跨模式複習中樞（收藏來自劇本／學習，可刪除、可再進劇本練習）。

### 4.2 建議指標

| 指標 | 目標（上線後校準） |
|------|-------------------|
| 首頁 → 進入任一模式完成率 | ≥ 55% |
| 劇本模式：提交錄音評分率（有進入錄音步驟者） | ≥ 35% |
| 7 日內再次開啟單字庫 | ≥ 20%（有收藏行為者） |
| 考試模式：完成一輪作答率 | ≥ 40% |
| 後端 AI 相關 5xx 率 | < 2% |

### 4.3 本期非目標

- 使用者註冊／登入、跨裝置雲端同步單字庫。
- 付費訂閱、廣告。
- 完整 TOPIK 全真模擬卷（聽讀寫全卷）。
- 文法專區完整課程（`grammar.html` 目前為佔位頁）。

---

## 5. 資訊架構與頁面

| 路徑 | 名稱 | 說明 |
|------|------|------|
| `index.html` | 首頁 | 選難度、選模式、同步後端 level |
| `script.html` | 劇本模式 | 情境選詞、造句、錄音演戲、評分 |
| `study.html` | 學習模式 | 貼上／選取韓文，分析當級詞彙 |
| `exam.html` | 考試模式 | 選題型與題數，作答 |
| `vocabulary.html` | 我的單字庫 | 收藏列表、選取刪除 |
| `grammar.html` | 文法（佔位） | 靜態預覽，非本期交付 |

全站須含固定 **site-header**、**site-footer**；支援側邊抽屜切換「目前難度」。

---

## 6. 功能需求

### 6.1 全站（P0）

| ID | 需求 | 驗收標準 |
|----|------|----------|
| G-01 | 難度三選一：初級、中級、高級 | 寫入 `localStorage`（`ktopik:selectedLevel`）並可 `POST /api/set-level` 同步 session |
| G-02 | 模式三選一：劇本、學習、考試 | 進入對應 HTML；未連後端時提示啟動 Flask（port 5000） |
| G-03 | 中韓雙語 UI；字體：原石黑體（中文）、Rubik（英文）、韓文 Noto Sans KR / Carmen Sans 系 | 與設計規範一致 |
| G-04 | 響應式：桌機為主、手機可操作 | 核心按鈕可點、無嚴重版面破版 |
| G-05 | API 與靜態資源 | 本機以 Flask 提供站點與 `/data`；`credentials: include` 維持 session |

### 6.2 劇本模式（P0）

| ID | 需求 | 驗收標準 |
|----|------|----------|
| S-01 | 依 session 難度隨機抽 3 詞 | `GET /api/modes/script/word-picks`；詞來自當級詞書 |
| S-02 | 情境風格：浪漫愛情、嚴肅史劇、狗血八點檔 | 傳入 Gemini 風格與前端選項一致 |
| S-03 | 單詞處理與造句 | `POST /process-word` 回傳結構化 JSON；失敗有明確錯誤 |
| S-04 | 錄音演戲評分 | `POST /evaluate-acting`：Azure 發音 + Gemini 多模態；過短／無聲拒絕並提示 |
| S-05 | 示範朗讀 | `POST /sentence-demo-audio`（ElevenLabs）可播放 MP3 |
| S-06 | 收藏至單字庫 | 劇本流程內可 `KTL.addScriptFavorite`；欄位含韓文詞、中文義、戲劇台詞、時間戳 |
| S-07 | 從單字庫回填劇本輸入 | `sessionStorage` prefill，進入劇本頁可帶入該詞 |

### 6.3 學習模式（P0）

| ID | 需求 | 驗收標準 |
|----|------|----------|
| ST-01 | 使用者輸入或選取韓文段落 | 前端校驗諺文等規則 |
| ST-02 | 詞彙分析 | `POST /api/modes/study/analyze` 回傳 `matches`（當級詞書比對，單次最多 20 筆）；**須連後端**，無離線本地比對 fallback |
| ST-03 | 詳情卡收藏 | 與劇本共用 `ktopik:scriptFavorites`；已收藏顯示狀態 |
| ST-04 | 無 session level 時 | 回 401 並引導先於首頁設定難度 |
| ST-05 | 變形詞還原 | 文章內諺文片段先對詞表精確比對；未命中則依 `data/shared/study_suffixes.json` 由長到短剝除後綴，再對當級 `韓文單字` 查 `中文意思` |

### 6.4 考試模式（P0）

| ID | 需求 | 驗收標準 |
|----|------|----------|
| E-01 | 題型：單字、文法、混合 | `question_type`: `vocabulary` \| `grammar` \| `mixed` |
| E-02 | 題數 1–30 | `POST /api/modes/exam/questions` |
| E-03 | 初級離線題庫 | 難度為「初級」時使用前端內建 mock 題庫（無需 Gemini） |
| E-04 | 中級／高級 AI 出題 | 成功回傳 `questions` 陣列；429／502 顯示後端 `error` 文案 |
| E-05 | 作答與結果 | 前端呈現選項、判對錯（依現有 `exam-mode.js`） |

### 6.5 我的單字庫（P0，已實作）

| ID | 需求 | 驗收標準 |
|----|------|----------|
| V-01 | 列表展示收藏 | 讀取 `KTL.getScriptFavorites()`；空狀態有提示 |
| V-02 | 單筆／批次刪除 | 選取模式、確認對話框後自 `localStorage` 移除 |
| V-03 | 再練習 | 可將詞帶回劇本模式（prefill） |
| V-04 | 持久化範圍 | **僅瀏覽器本機**；清快取或換裝置即遺失（本期接受） |

### 6.6 文法頁（P2 / 佔位）

| ID | 需求 | 驗收標準 |
|----|------|----------|
| GR-01 | 靜態說明頁 | 現狀：`grammar.html` 佔位文案即可 |
| GR-02 | 未來：主題式文法與例句 | 另開 PRD 迭代，不阻塞首期上線 |

---

## 7. 使用者流程

```
                    ┌─────────────┐
                    │   首頁      │
                    │ 選難度+模式  │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐
    │  劇本模式   │ │  學習模式   │ │  考試模式   │
    │ 抽詞/造句   │ │ 段落分析    │ │ 出題作答    │
    │ 錄音評分    │ │ 收藏詞彙    │ │            │
    └──────┬─────┘ └──────┬─────┘ └────────────┘
           │               │
           └───────┬───────┘
                   ▼
            ┌─────────────┐
            │ 我的單字庫   │
            │ 檢視/刪除    │
            │ → 回劇本練習 │
            └─────────────┘
```

**自學者主路徑（建議）：** 首頁定級 → 劇本模式練 3 詞並收藏 → 單字庫複習 → 學習模式讀文章標詞 → 考試模式驗收。

---

## 8. 內容與難度規則

- 詞書：`data/processed/vocab_books/`  
  - 初級 `topik_vol_beginner.zh.v1.json`  
  - 中級 `topik_vol_intermediate.zh.v1.json`  
  - 高級 `topik_advanced.zh.v1.json`
- 能力指標：`data/processed/rules/topik_ability_indicators.v1.json`
- 學習模式後綴表：`data/shared/study_suffixes.json`（見 §8.1）
- **所有 AI 生成內容**須對齊使用者當前 session／請求級別，Prompt 要求嚴格 JSON；後端以詞書白名單校驗（如 `process-word` 檢查詞是否屬於當級或已知級別）。

### 8.1 學習模式詞彙比對（Study）

**資料分工**

| 檔案／來源 | 內容 | 用途 |
|------------|------|------|
| 當級詞書 JSON | `韓文單字`（字典形）、`中文意思`、`等級` | 比對白名單與釋義來源 |
| `study_suffixes.json` | 韓文助詞／語尾等**可剝除後綴**（非單字原型） | 將文章用字（如 `먹었어요`）嘗試還原為詞表中的 `먹다` |

**流程（前後端共用同一套後綴表與邏輯）**

1. 依 Flask session 中的 TOPIK 級別（`beginner`／`intermediate`／`advanced`）載入對應詞書，僅保留 `等級` 與該級中文標籤一致的列。
2. 掃描使用者貼上的韓文，以連續諺文為 token。
3. 對每個 token：若等於某筆 `韓文單字` 則直接命中；否則依 `study_suffixes.json` **由長到短**剝尾，得到 candidate 後再查是否在當級詞表。
4. 命中後回傳 `surface`／`word`（詞表原形）、`meaning_zh`（該列 `中文意思`）、`context_kr`（含該 token 的句段）。
5. 僅在**當級詞表**內查找，不跨級別回查。

**維護注意**

- 標準 JSON **不支援註解**；說明請寫在本 PRD 或同目錄 `study_suffixes.README.md`，勿在 JSON 內加 `//`。
- 調整後綴時請保持**較長後綴排在陣列前面**，與現有剝除順序一致。
- 詞書或後綴變更後需重啟 Flask，前端重新整理以載入新後綴。

---

## 9. 技術與整合

| 層級 | 選型 |
|------|------|
| 前端 | HTML、原生 JS/TS 風格、Tailwind、`static-site/` |
| 後端 | Flask（`backend/ktl_backend/flask_app.py`） |
| AI | Google Gemini（造句、考題、演戲評分） |
| 語音 | Azure Speech（TTS／發音評估）；ElevenLabs（情境示範句） |
| 狀態 | Flask session（level）；瀏覽器 localStorage（難度、收藏） |

### 9.1 主要 API

| 方法 | 路徑 | 用途 |
|------|------|------|
| POST | `/api/set-level` | 設定 TOPIK 級別 session |
| GET | `/api/modes/script/word-picks` | 劇本隨機抽詞 |
| POST | `/api/modes/study/analyze` | 學習模式詞彙比對 |
| POST | `/api/modes/exam/questions` | 考試出題（Gemini） |
| POST | `/process-word` | 單詞情境處理 |
| POST | `/sentence-demo-audio` | 示範音生成 |
| POST | `/evaluate-acting` | 演戲錄音評分 |

環境變數見 `backend/.env.example`（`GEMINI_*`、`SPEECH_*`、`ELEVENLABS_*`、`FLASK_SECRET_KEY` 等）。**金鑰不得進版控。**

### 9.2 共用模組與 DRY（2026-06-03）

為避免前後端重複維護，下列邏輯集中於單一來源：

| 職責 | 位置 | 說明 |
|------|------|------|
| 靜態資料路徑、各級詞書 URL | `static-site/js/chrome.js`（`KTL.assetDataPath`、`KTL.VOCAB_BY_LEVEL`） | `script.js` 等頁面透過 `KTL` 引用，不再各自實作 `assetDataPath` |
| Study 後綴載入 | `chrome.js`（`KTL.ensureStudySuffixes` → `KTL.STUDY_SUFFIXES`） | 自 `/data/shared/study_suffixes.json` 載入；`study-mode.js` 僅用於標記文章時剝後綴 |
| Study 比對演算法 | `backend/ktl_backend/study_match.py` | `match_study_vocab`、`slice_study_context`；`flask_app` 的 `/api/modes/study/analyze` 呼叫此模組 |
| Gemini JSON 解析 | `backend/services/gemini_json.py` | `strip_json_fence`、`parse_json_text`；造句、演戲評分、考試出題共用 |
| 全站 API 請求 | `chrome.js`（`KTL.apiFetch`） | `credentials: include`、JSON `Content-Type`；學習模式分析等改走此 helper |

**學習模式依賴：** 分析必須呼叫後端 API；已移除「僅開靜態頁 + 本地詞書 JSON」的離線 fallback，與 G-02「須啟動 Flask」一致。

---

## 10. 上線與營運（尚未上線）

### 10.1 上線前檢查清單

- [ ] 正式域名、HTTPS、反向代理（如 gunicorn + nginx）
- [ ] 生產環境 `.env` 與 CORS（`KTL_CORS_ORIGINS`）僅允許正式前端 origin
- [ ] `FLASK_SECRET_KEY` 強隨機值；關閉 debug
- [ ] Gemini／Azure／ElevenLabs 配額與告警
- [ ] 隱私政策：錄音上傳至第三方語音／AI 服務之說明
- [ ] 錯誤頁與 API 限流（429）使用者文案統一

### 10.2 部署參考

本機開發：`python app.py`（port 5000）。生產可參考 `.env.example` 內 gunicorn 指令。

### 10.3 上線後迭代（P1）

- 單字庫雲端同步（需帳號體系）
- 學習進度、錯題本、連續學習天數
- 文法專區內容化
- 中級／初級考試體驗統一（是否全面 AI 出題）
- 效能：靜態資源 CDN、音檔快取策略

---

## 11. 風險與依賴

| 風險 | 影響 | 緩解 |
|------|------|------|
| 第三方 AI／語音 API 故障或超額 | 劇本／考試不可用 | 限流提示、初級考試 mock、重試文案 |
| 麥克風權限（尤其 iOS Safari） | 劇本評分中斷 | 引導允許麥克風、最短錄音門檻說明 |
| AI 造句偏離級別 | 學習信任下降 | 詞書校驗 + Prompt 約束 |
| 僅 localStorage 存收藏 | 換機資料遺失 | 上線說明；P1 做帳號同步 |
| 詞書版權 | 法務 | 確認 TOPIK 官方教材使用範圍 |

---

## 12. 里程碑建議

| 階段 | 內容 | 狀態 |
|------|------|------|
| M0 | 三模式 + 單字庫 + 三級詞書 + 核心 API | 已具備 |
| M1 | 上線準備：域名、HTTPS、生產 env、隱私與錯誤文案 | 進行中 |
| M2 | 上線後 4 週：依指標優化劇本完成率與考試穩定性 | 計畫 |
| M3 | 帳號與雲端單字庫、文法專區 | 計畫 |

---

## 13. 開放問題

1. **正式網站域名與託管**（時程、是否前後端同域）。
2. **上線首日**是否開放「高級」AI 考試，或先限流邀請制。
3. **文法專區**與考試模式「文法題」的內容邊界（共用題庫或獨立課程）。
4. **商業模式**（免費／訂閱／廣告）與 API 成本上限。

---

## 附錄 A：localStorage 鍵

| 鍵 | 用途 |
|----|------|
| `ktopik:selectedLevel` | 使用者確認的難度（初級／中級／高級） |
| `ktopik:scriptFavorites` | 單字庫收藏陣列 |
| `ktopik:scriptWordPrefill` | 從單字庫進劇本時的暫存詞（sessionStorage） |
| `ktopik:favoriteWordIds` | 舊版收藏 ID（若仍引用需與 scriptFavorites 區隔） |

## 附錄 B：相關文件

- 前端規範：`.cursor/prompt/frondend.md`
- 後端規範：`.cursor/prompt/backend.md`
- 環境變數：`backend/.env.example`

## 附錄 C：`study_suffixes.json` 範例說明

檔案為**純 JSON 陣列**，元素為韓文後綴字串，例如：

```json
["에게서는", "에서", "을", "는"]
```

- **不是**單字原型列表；原型來自各級詞書的 `韓文單字`。
- 與 §8.1 流程搭配：剝除後綴僅用於對齊詞表，釋義一律取自詞書 `中文意思`。
- 實作參考：`backend/ktl_backend/study_match.py`、`static-site/js/study-mode.js`（`resolveMappedWord`）。
