(function () {
  var state = {
    articleText: "",
    matches: [],
    matchMap: {},
    openedKeys: [],
    activeKey: "",
    toastTimer: 0,
  };

  function studySuffixes() {
    return window.KTL && Array.isArray(window.KTL.STUDY_SUFFIXES) ? window.KTL.STUDY_SUFFIXES : [];
  }

  function getLevel() {
    if (!window.KTL || typeof window.KTL.getConfirmedDifficulty !== "function") return "";
    return window.KTL.getConfirmedDifficulty();
  }

  function createFavoriteIconMarkup() {
    return (
      '<svg class="chat-favorite-icon chat-favorite-icon--outline" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
      '<path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>' +
      "</svg>" +
      '<svg class="chat-favorite-icon chat-favorite-icon--fill" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>' +
      "</svg>"
    );
  }

  function setFavoriteButtonState(button, isSaved) {
    button.setAttribute("aria-pressed", isSaved ? "true" : "false");
    button.setAttribute("aria-label", isSaved ? "已收藏" : "加入我的學習庫");
  }

  function isFavoriteWord(word) {
    if (!word || !window.KTL || typeof window.KTL.isScriptFavoriteWord !== "function") return false;
    return window.KTL.isScriptFavoriteWord(word);
  }

  function autoResizeTextarea(textarea) {
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 144) + "px";
  }

  function resetStudyState() {
    state.matches = [];
    state.matchMap = {};
    state.openedKeys = [];
    state.activeKey = "";
  }

  function normalizeMatch(raw) {
    if (!raw || typeof raw !== "object") return null;
    var surface = String(raw.surface || raw.word || "").trim();
    var word = String(raw.word || raw.surface || "").trim();
    var meaningZh = String(raw.meaning_zh || raw.meaningZh || raw.meaning || "").trim();
    if (!surface || !word || !meaningZh) return null;
    return {
      key: surface,
      surface: surface,
      word: word,
      meaningZh: meaningZh,
      contextKr: String(raw.context_kr || raw.contextKr || "").trim(),
    };
  }

  function resolveMappedWord(token, lookup) {
    var clean = String(token || "").trim();
    if (!clean) return null;
    if (lookup[clean]) return clean;

    var i;
    var suffixes = studySuffixes();
    for (i = 0; i < suffixes.length; i += 1) {
      var suffix = suffixes[i];
      if (!suffix || clean.length <= suffix.length) continue;
      if (clean.slice(-suffix.length) !== suffix) continue;
      var stem = clean.slice(0, clean.length - suffix.length);
      if (stem && lookup[stem]) {
        return stem;
      }
    }
    return null;
  }

  function indexMatches(matches) {
    var map = {};
    var list = [];
    var i;
    for (i = 0; i < matches.length; i += 1) {
      var match = normalizeMatch(matches[i]);
      if (!match || map[match.key]) continue;
      map[match.key] = match;
      list.push(match);
    }
    state.matches = list;
    state.matchMap = map;
  }

  function renderPlaceholder(articleEl, text) {
    articleEl.innerHTML = "";
    var line = document.createElement("p");
    line.className = "study-mode-placeholder";
    line.textContent = text;
    articleEl.appendChild(line);
  }

  function showEditor(editorEl, articleEl) {
    if (editorEl) editorEl.hidden = false;
    if (articleEl) articleEl.hidden = true;
  }

  function showArticle(editorEl, articleEl) {
    if (editorEl) editorEl.hidden = true;
    if (articleEl) articleEl.hidden = false;
  }

  function renderArticle(articleEl) {
    articleEl.innerHTML = "";
    if (!state.articleText) {
      renderPlaceholder(articleEl, "請貼上韓文文章，系統會依照目前 TOPIK 等級標出生字。");
      return;
    }

    var paragraphs = state.articleText.split(/\n+/);
    var hadParagraph = false;
    var tokenPattern = /([가-힣]+)/g;
    var markedKeys = {};
    var i;

    for (i = 0; i < paragraphs.length; i += 1) {
      var paragraphText = paragraphs[i];
      if (!paragraphText || !paragraphText.trim()) continue;
      hadParagraph = true;

      var p = document.createElement("p");
      var lastIndex = 0;
      tokenPattern.lastIndex = 0;

      var tokenMatch;
      while ((tokenMatch = tokenPattern.exec(paragraphText))) {
        var token = tokenMatch[0];
        var start = tokenMatch.index;
        if (start > lastIndex) {
          p.appendChild(document.createTextNode(paragraphText.slice(lastIndex, start)));
        }

        var vocabKey = resolveMappedWord(token, state.matchMap);
        var vocab = vocabKey ? state.matchMap[vocabKey] : null;
        if (vocab && !markedKeys[vocab.key]) {
          markedKeys[vocab.key] = true;
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "study-mode-token";
          if (state.activeKey === vocab.key) {
            btn.classList.add("is-active");
          }
          btn.textContent = vocab.surface;
          btn.setAttribute("data-study-key", vocab.key);
          btn.addEventListener("click", function (event) {
            var key = event.currentTarget.getAttribute("data-study-key");
            openDetail(key);
          });
          p.appendChild(btn);
          if (token.length > vocab.surface.length) {
            p.appendChild(document.createTextNode(token.slice(vocab.surface.length)));
          }
        } else {
          p.appendChild(document.createTextNode(token));
        }

        lastIndex = start + token.length;
      }

      if (lastIndex < paragraphText.length) {
        p.appendChild(document.createTextNode(paragraphText.slice(lastIndex)));
      }

      articleEl.appendChild(p);
    }

    if (!hadParagraph) {
      renderPlaceholder(articleEl, "請貼上韓文文章，系統會依照目前 TOPIK 等級標出生字。");
    }
  }

  function renderDetailPanel(frameEl, panelEl, listEl) {
    listEl.innerHTML = "";
    if (!state.openedKeys.length) {
      panelEl.hidden = true;
      frameEl.classList.remove("is-detail-open");
      return;
    }

    frameEl.classList.add("is-detail-open");
    panelEl.hidden = false;

    var i;
    for (i = 0; i < state.openedKeys.length; i += 1) {
      var key = state.openedKeys[i];
      var match = state.matchMap[key];
      if (!match) continue;

      var card = document.createElement("article");
      card.className = "study-mode-detail-card";
      if (key === state.activeKey) {
        card.classList.add("is-active");
      }

      var main = document.createElement("div");
      main.className = "study-mode-detail-card__main";

      var row = document.createElement("div");
      row.className = "study-mode-detail-card__row";

      var wordEl = document.createElement("strong");
      wordEl.className = "study-mode-detail-card__word";
      wordEl.textContent = match.surface;
      row.appendChild(wordEl);

      var meaningEl = document.createElement("span");
      meaningEl.className = "study-mode-detail-card__meaning";
      meaningEl.textContent = match.meaningZh;
      row.appendChild(meaningEl);

      main.appendChild(row);

      var favBtn = document.createElement("button");
      favBtn.type = "button";
      favBtn.className = "chat-favorite-btn";
      favBtn.innerHTML = createFavoriteIconMarkup();
      favBtn.setAttribute("data-study-word", match.word);
      setFavoriteButtonState(favBtn, isFavoriteWord(match.word));
      favBtn.addEventListener("click", function (event) {
        handleFavoriteClick(event.currentTarget);
      });

      card.appendChild(main);
      card.appendChild(favBtn);
      listEl.appendChild(card);
    }
  }

  function showToast(toastEl) {
    if (state.toastTimer) {
      window.clearTimeout(state.toastTimer);
      state.toastTimer = 0;
    }

    toastEl.hidden = false;
    toastEl.classList.add("is-visible");

    state.toastTimer = window.setTimeout(function () {
      toastEl.classList.remove("is-visible");
      state.toastTimer = window.setTimeout(function () {
        toastEl.hidden = true;
      }, 220);
    }, 2000);
  }

  function handleFavoriteClick(button) {
    var word = button.getAttribute("data-study-word");
    if (!word) return;
    if (isFavoriteWord(word)) {
      setFavoriteButtonState(button, true);
      return;
    }
    if (!window.KTL || typeof window.KTL.addScriptFavorite !== "function") return;

    var i;
    var match = null;
    for (i = 0; i < state.matches.length; i += 1) {
      if (state.matches[i].word === word) {
        match = state.matches[i];
        break;
      }
    }
    if (!match) return;

    var added = window.KTL.addScriptFavorite({
      word: match.word,
      meaningZh: match.meaningZh,
      dramaLineKo: match.contextKr || state.articleText || "",
    });

    if (added || isFavoriteWord(word)) {
      setFavoriteButtonState(button, true);
      var toastEl = document.getElementById("studyModeToast");
      if (toastEl) showToast(toastEl);
    }
  }

  function openDetail(key) {
    if (!key || !state.matchMap[key]) return;
    if (state.openedKeys.indexOf(key) === -1) {
      state.openedKeys.push(key);
    }
    state.activeKey = key;

    var frameEl = document.getElementById("studyModeFrame");
    var articleEl = document.getElementById("studyModeArticle");
    var panelEl = document.getElementById("studyModeDetailPanel");
    var listEl = document.getElementById("studyModeDetailList");
    if (!frameEl || !articleEl || !panelEl || !listEl) return;

    renderArticle(articleEl);
    renderDetailPanel(frameEl, panelEl, listEl);
  }

  async function fetchStudyAnalysis(text, level) {
    if (window.KTL && typeof window.KTL.syncLevelToBackend === "function" && level) {
      await window.KTL.syncLevelToBackend(level);
    }
    if (!window.KTL || typeof window.KTL.apiFetch !== "function") {
      return { summary_level: level || "", matches: [] };
    }
    try {
      var response = await window.KTL.apiFetch("/api/modes/study/analyze", {
        method: "POST",
        body: JSON.stringify({ text: text }),
      });
      if (
        response.status === 401 &&
        window.KTL &&
        typeof window.KTL.syncLevelToBackend === "function" &&
        level
      ) {
        await window.KTL.syncLevelToBackend(level);
        response = await window.KTL.apiFetch("/api/modes/study/analyze", {
          method: "POST",
          body: JSON.stringify({ text: text }),
        });
      }
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      /* ignore */
    }
    return { summary_level: level || "", matches: [] };
  }

  document.addEventListener("DOMContentLoaded", function () {
    var frameEl = document.getElementById("studyModeFrame");
    var articleEl = document.getElementById("studyModeArticle");
    var editorEl = document.getElementById("studyModeEditor");
    var panelEl = document.getElementById("studyModeDetailPanel");
    var listEl = document.getElementById("studyModeDetailList");
    var formEl = document.getElementById("studyModeForm");
    var clearBtn = document.getElementById("studyModeClearBtn");
    var sendBtn = formEl ? formEl.querySelector(".study-mode-action-btn--primary") : null;

    if (!frameEl || !articleEl || !editorEl || !panelEl || !listEl || !formEl || !clearBtn || !sendBtn) return;

    showEditor(editorEl, articleEl);
    if (window.KTL && typeof window.KTL.ensureStudySuffixes === "function") {
      window.KTL.ensureStudySuffixes();
    }

    formEl.addEventListener("submit", async function (event) {
      event.preventDefault();
      var text = String(editorEl.value || "").trim();
      if (!text) return;

      state.articleText = text;
      resetStudyState();
      sendBtn.disabled = true;
      renderPlaceholder(articleEl, "系統分析中...");
      showArticle(editorEl, articleEl);
      renderDetailPanel(frameEl, panelEl, listEl);

      var level = getLevel();
      var payload = await fetchStudyAnalysis(text, level);
      var matches = payload && Array.isArray(payload.matches) ? payload.matches : [];
      indexMatches(matches);

      renderArticle(articleEl);
      renderDetailPanel(frameEl, panelEl, listEl);

      sendBtn.disabled = false;
    });

    clearBtn.addEventListener("click", function () {
      state.articleText = "";
      editorEl.value = "";
      articleEl.innerHTML = "";
      resetStudyState();
      renderDetailPanel(frameEl, panelEl, listEl);
      showEditor(editorEl, articleEl);
      editorEl.focus();
    });
  });
})();
