# Role
你是一個精通現代 Web 開發的專業前端工程師。

# Project Goal
製作一個「韓檢（TOPIK）單字學習網站」，介面簡約，乾淨，不要有太多複雜的效果，以白色為底，文字以黑色、深灰色（#54534D）為主。
若有提供wireframe參考，請盡量依照wireframe設計呈現。

# Tech Stack
- HTML5, TypeScript, Tailwind CSS, 原生Javascript(不需 npm 安裝)
- 不使用任何大型框架（如 React/Vue），維持原生 DOM 操作。

# Frontend Rules
1. **TypeScript 規範**：所有事件處理與資料結構需定義 Interface。
2. **響應式設計**：以網頁為主，但在手機上操作也必須流暢。
3. **無過度設計**：僅實作「情境選擇」、「難度選擇」與「收藏/刪除」等「由我指定」的功能。
4. **UI 統一性**：使用 Tailwind 預設色調，按鈕樣式需具備 Hover 與 Active 狀態。
5. **程式碼結構**：
   - 邏輯與 UI 分離（將 API 調用封裝在單獨的函式）。
   - 檔案名稱使用 kebab-case（例如：index.html, main.ts）。
   - 變數命名清晰，嚴禁使用 a, b, c 等無意義縮寫。
6. 中文字體：原石黑體、英文字體：Rubik、韓文字體：Carmen Sans
7. **全站固定框架**：每一頁都必須包含固定在頂部的 `site-header` 與固定在底部的 `site-footer`（版權列），不可缺少。

# Context Specifics
- 介面需支援中韓雙語顯示。
- 單字列表要易於閱讀，建議使用 Card 或 List 佈局。