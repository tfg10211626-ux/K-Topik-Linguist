(function () {
  function assetDataPath(relativePath) {
    return window.KTL && typeof window.KTL.assetDataPath === "function"
      ? window.KTL.assetDataPath(relativePath)
      : "../data/" + relativePath;
  }

  var USER_AVATAR_SRC = assetDataPath("img/smiley.png");
  var ACTING_MODE_ENTRY_SOUND_SRC = assetDataPath(
    "sound/DSGNBass-Deep_bass_void_pull,-Elevenlabs.mp3"
  );
  var VOCAB_BY_LEVEL = window.KTL && window.KTL.VOCAB_BY_LEVEL ? window.KTL.VOCAB_BY_LEVEL : {};
  var MIN_RECORDING_BLOB_BYTES = 900;
  var MIN_RECORDING_DURATION_MS = 350;
  var MIN_RECORDING_PEAK_LEVEL = 0.02;
  var MIN_RECORDING_RMS_LEVEL = 0.008;

  /** 與 script.html #scriptScenarioSelect 的 option value 對齊；傳給後端 / Gemini「風格」 */
  var SCRIPT_SCENARIO_LABEL_BY_VALUE = {
    "romantic-love": "浪漫愛情",
    "serious-history": "嚴肅史劇",
    "soap-opera": "狗血八點檔",
  };

  function scenarioZhFromSelect(selectEl) {
    if (!selectEl || typeof selectEl.value !== "string") return "浪漫愛情";
    var v = selectEl.value.trim();
    if (!v) return "浪漫愛情";
    return SCRIPT_SCENARIO_LABEL_BY_VALUE[v] || "浪漫愛情";
  }

  function getLevel() {
    if (!window.KTL || typeof window.KTL.getConfirmedDifficulty !== "function") return "";
    return window.KTL.getConfirmedDifficulty();
  }

  function normalizeWord(raw) {
    return (raw || "").trim();
  }

  /** 僅允許諺文音節與諺文字母（不含空格、數字、英文、漢字等） */
  function isKoreanWordOnly(raw) {
    var text = normalizeWord(raw);
    if (!text) return false;
    var i;
    var c;
    for (i = 0; i < text.length; i += 1) {
      c = text.charCodeAt(i);
      var syllable = c >= 0xac00 && c <= 0xd7af;
      var jamo = c >= 0x1100 && c <= 0x11ff;
      var compatJamo = c >= 0x3131 && c <= 0x318e;
      var jamoExtA = c >= 0xa960 && c <= 0xa97f;
      var jamoExtB = c >= 0xd7b0 && c <= 0xd7ff;
      if (!syllable && !jamo && !compatJamo && !jamoExtA && !jamoExtB) return false;
    }
    return true;
  }

  function createDramaLine(word) {
    return "오늘도 " + word + " 같은 네 마음을, 끝까지 알아가고 싶어.";
  }

  var actingModeEntryAudio = null;
  var cosmicStarsEl = null;

  function mountCosmicStars() {
    if (cosmicStarsEl) return;
    cosmicStarsEl = document.createElement("div");
    cosmicStarsEl.className = "cosmic-stars";
    cosmicStarsEl.setAttribute("aria-hidden", "true");
    for (var i = 0; i < 50; i++) {
      var star = document.createElement("div");
      star.className = "cosmic-star";
      var size = Math.random() * 3;
      star.style.width = size + "px";
      star.style.height = size + "px";
      star.style.left = Math.random() * 100 + "vw";
      star.style.top = Math.random() * 100 + "vh";
      star.style.animationDuration = Math.random() * 3 + 2 + "s";
      cosmicStarsEl.appendChild(star);
    }
    document.body.appendChild(cosmicStarsEl);
  }

  function unmountCosmicStars() {
    if (!cosmicStarsEl) return;
    cosmicStarsEl.remove();
    cosmicStarsEl = null;
  }

  function isDarkTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark";
  }

  function syncActingCosmicBackdrop() {
    if (document.body.classList.contains("acting-mode") && isDarkTheme()) {
      mountCosmicStars();
      return;
    }
    unmountCosmicStars();
  }

  function setActingModeVisual(on) {
    if (on) {
      document.body.classList.add("acting-mode");
      syncActingCosmicBackdrop();
      return;
    }
    document.body.classList.remove("acting-mode");
    unmountCosmicStars();
  }

  window.addEventListener("ktl-theme-changed", syncActingCosmicBackdrop);

  function playActingModeEntrySound() {
    if (!actingModeEntryAudio) {
      actingModeEntryAudio = new Audio(ACTING_MODE_ENTRY_SOUND_SRC);
      actingModeEntryAudio.preload = "auto";
      actingModeEntryAudio.volume = 1;
    }

    try {
      actingModeEntryAudio.pause();
      actingModeEntryAudio.currentTime = 0;
    } catch (error) {}

    var pr = actingModeEntryAudio.play();
    if (pr && typeof pr.catch === "function") {
      pr.catch(function () {});
    }
  }

  async function fetchScriptWordPicks() {
    if (!window.KTL || typeof window.KTL.getApiOrigin !== "function") return null;
    var base = window.KTL.getApiOrigin();
    try {
      var response = await fetch(base + "/api/modes/script/word-picks", {
        credentials: "include",
      });
      if (!response.ok) return null;
      return await response.json();
    } catch (error) {
      return null;
    }
  }

  function renderQuickWordButtons(container, btnWrap, inputRef, picks) {
    if (!container || !btnWrap) return;
    btnWrap.innerHTML = "";
    if (!picks || !picks.length) {
      container.hidden = true;
      return;
    }
    picks.forEach(function (p) {
      if (!p || !p.word_kr) return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "script-quick-words__btn";
      btn.textContent = p.word_kr;
      btn.setAttribute("aria-label", "插入單字 " + p.word_kr);
      btn.addEventListener("click", function () {
        if (inputRef) {
          inputRef.value = p.word_kr;
          inputRef.focus();
        }
      });
      btnWrap.appendChild(btn);
    });
    container.hidden = false;
  }

  async function loadVocab(level) {
    var path = VOCAB_BY_LEVEL[level];
    if (!path) return [];
    try {
      var response = await fetch(path);
      if (!response.ok) return [];
      var payload = await response.json();
      return Array.isArray(payload.entries) ? payload.entries : [];
    } catch (error) {
      return [];
    }
  }

  async function requestProcessWord(word, scenarioZh) {
    if (!window.KTL || typeof window.KTL.getApiOrigin !== "function") {
      return { ok: false, error: "無法取得 API 位址" };
    }
    var scenario = scenarioZh && String(scenarioZh).trim() ? String(scenarioZh).trim() : "浪漫愛情";
    var base = window.KTL.getApiOrigin();
    try {
      var response = await fetch(base + "/process-word", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word: word, scenario: scenario }),
      });
      var data = {};
      try {
        data = await response.json();
      } catch (e1) {
        data = {};
      }
      if (!response.ok) {
        return {
          ok: false,
          error: (data && data.error) || "請求失敗 (" + response.status + ")",
        };
      }
      return {
        ok: true,
        dramaLineKo: typeof data.sentence === "string" ? data.sentence : "",
        translationZh: typeof data.translation === "string" ? data.translation : "",
        analysisLines: Array.isArray(data.analysis) ? data.analysis : [],
        levelWarning: typeof data.level_warning === "string" ? data.level_warning : "",
        audioUrl: typeof data.audio_url === "string" ? data.audio_url.trim() : "",
        sentenceDemoAudioUrl:
          typeof data.sentence_demo_audio_url === "string" ? data.sentence_demo_audio_url.trim() : "",
      };
    } catch (error) {
      return { ok: false, error: error && error.message ? error.message : String(error) };
    }
  }

  function createSystemAvatar() {
    var el = document.createElement("div");
    el.className = "chat-message__avatar chat-message__avatar--system";
    el.setAttribute("aria-hidden", "true");
    el.textContent = "K";
    return el;
  }

  function createUserAvatar() {
    var wrap = document.createElement("div");
    wrap.className = "chat-message__avatar chat-message__avatar--user";
    var img = document.createElement("img");
    img.className = "chat-message__user-face";
    img.src = USER_AVATAR_SRC;
    img.alt = "";
    img.width = 32;
    img.height = 32;
    img.decoding = "async";
    wrap.appendChild(img);
    return wrap;
  }

  function syncFavoriteNavList() {
    var emptyEl = document.getElementById("scriptFavoritesEmptyMsg");
    var listEl = document.getElementById("scriptFavoritesNavList");
    if (!emptyEl || !listEl || !window.KTL || typeof window.KTL.getScriptFavorites !== "function") return;
    var items = window.KTL.getScriptFavorites();
    listEl.innerHTML = "";
    if (!items.length) {
      emptyEl.hidden = false;
      listEl.hidden = true;
      return;
    }
    emptyEl.hidden = true;
    listEl.hidden = false;
    items.forEach(function (entry) {
      if (!entry || !entry.word) return;
      var li = document.createElement("li");
      li.className = "script-fav-nav-dropdown__li";
      var label = document.createElement("span");
      label.className = "script-fav-nav-dropdown__word";
      label.textContent = entry.word;
      var sub = document.createElement("span");
      sub.className = "script-fav-nav-dropdown__sub";
      sub.textContent = entry.meaningZh || "—";
      li.appendChild(label);
      li.appendChild(sub);
      listEl.appendChild(li);
    });
  }

  function initFavoritesDropdown() {
    var wrap = document.getElementById("scriptFavoritesDropdown");
    if (!wrap) return;
    var btn = document.getElementById("scriptFavoritesDropdownBtn");
    var menu = document.getElementById("scriptFavoritesDropdownMenu");
    if (!btn || !menu) return;

    function close() {
      menu.hidden = true;
      btn.setAttribute("aria-expanded", "false");
    }

    function toggle() {
      var open = menu.hidden;
      if (open) syncFavoriteNavList();
      menu.hidden = !open;
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      toggle();
    });

    document.addEventListener("click", function (e) {
      if (!wrap.contains(e.target)) close();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });

    window.addEventListener("ktl-script-favorites-changed", function () {
      syncFavoriteNavList();
    });
    syncFavoriteNavList();
  }

  function svgMicMuted() {
    return (
      '<svg class="chat-message__media-svg" viewBox="0 0 24 24" width="24" height="24" focusable="false" aria-hidden="true">' +
      '<path fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" d="M12 17v2M10 19h4M12 3a2.5 2.5 0 0 0-2.5 2.5V12A2.5 2.5 0 0 0 12 14.5 2.5 2.5 0 0 0 14.5 12V5.5A2.5 2.5 0 0 0 12 3z"/>' +
      '<path fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" d="M5 5l14 14"/>' +
      "</svg>"
    );
  }

  function svgMicLive() {
    return (
      '<svg class="chat-message__media-svg" viewBox="0 0 24 24" width="24" height="24" focusable="false" aria-hidden="true">' +
      '<path fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" d="M12 17v2M10 19h4M12 3a2.5 2.5 0 0 0-2.5 2.5V12A2.5 2.5 0 0 0 12 14.5 2.5 2.5 0 0 0 14.5 12V5.5A2.5 2.5 0 0 0 12 3z"/>' +
      '<path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" d="M17.5 9.5c1.5 1 2.5 2.7 2.5 4.5M19 7c2 1.8 3.25 4.2 3.25 7"/>' +
      "</svg>"
    );
  }

  function svgPlayIcon() {
    return (
      '<svg class="chat-message__media-svg" viewBox="0 0 24 24" width="24" height="24" focusable="false" aria-hidden="true">' +
      '<path fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" d="M10 8.5L17 12l-7 3.5V8.5z"/>' +
      "</svg>"
    );
  }

  function createWordCardMediaActions(dramaLineKo, audioUrl, playAudioUrl) {
    var mediaRow = document.createElement("div");
    mediaRow.className = "chat-message__media-actions";

    var micBtn = document.createElement("button");
    micBtn.type = "button";
    micBtn.className = "chat-message__media-btn";
    micBtn.setAttribute("data-script-mic", "true");
    micBtn.setAttribute("aria-pressed", "false");
    micBtn.setAttribute("aria-label", "錄製台詞");
    micBtn.dataset.scriptSentence = dramaLineKo || "";
    micBtn.innerHTML =
      '<span class="chat-message__media-btn-layer">' +
      svgMicMuted() +
      "</span>" +
      '<span class="chat-message__media-btn-layer chat-message__media-btn-layer--alt" hidden>' +
      svgMicLive() +
      "</span>";

    var submitRecBtn = document.createElement("button");
    submitRecBtn.type = "button";
    submitRecBtn.className = "chat-message__submit-rec";
    submitRecBtn.textContent = "送出";
    submitRecBtn.setAttribute("aria-label", "送出錄音以評分");
    submitRecBtn.hidden = true;

    var playBtn = document.createElement("button");
    playBtn.type = "button";
    playBtn.className = "chat-message__media-btn";
    playBtn.setAttribute("aria-label", "播放韓文造句");
    playBtn.innerHTML = svgPlayIcon();
    playBtn.addEventListener("click", function () {
      if (audioUrl && typeof playAudioUrl === "function" && playAudioUrl(audioUrl)) return;
      var text = dramaLineKo || "";
      if (!text) return;
      if (!("speechSynthesis" in window)) return;
      var utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "ko-KR";
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    });

    mediaRow.appendChild(micBtn);
    mediaRow.appendChild(submitRecBtn);
    mediaRow.appendChild(playBtn);
    return mediaRow;
  }

  document.addEventListener("DOMContentLoaded", async function () {
    var level = getLevel();
    var levelTextEl = document.getElementById("currentLevelText");
    var formEl = document.getElementById("scriptForm");
    var sendBtn = formEl ? formEl.querySelector(".input-icon-btn--send") : null;
    var inputEl = document.getElementById("scriptWordInput");
    var chatBoardEl = document.getElementById("chatBoard");
    var quickWordsEl = document.getElementById("scriptQuickWords");
    var quickWordsBtns = document.getElementById("scriptQuickWordsBtns");
    var scenarioSelectEl = document.getElementById("scriptScenarioSelect");
    var scoreToggleEl = document.getElementById("scoreToggle");
    var scoreEnableDialogEl = document.getElementById("scoreEnableDialog");
    var scoreEnableConfirmEl = document.getElementById("scoreEnableConfirm");
    var scoreEnableDismissEl = document.getElementById("scoreEnableDismiss");
    var scoreDemoBtn = document.getElementById("scoreDemoBtn");
    var scoreRetryBtn = document.getElementById("scoreRetryBtn");
    var scoreWaveEl = document.getElementById("scoreWaveformPlaceholder");

    if (!levelTextEl || !formEl || !inputEl || !chatBoardEl) {
      return;
    }

    var prefillWord =
      window.KTL && typeof window.KTL.consumeScriptInputPrefill === "function"
        ? String(window.KTL.consumeScriptInputPrefill() || "").trim()
        : "";
    if (prefillWord) {
      inputEl.value = prefillWord;
      inputEl.focus();
    }

    var pageApiOrigin =
      window.KTL && typeof window.KTL.getApiOrigin === "function"
        ? String(window.KTL.getApiOrigin()).replace(/\/$/, "")
        : "";

    var pendingScoreDialog = { source: "toggle", mic: null };
    var recState = {
      mediaRecorder: null,
      chunks: [],
      stream: null,
      button: null,
      mime: "",
      abortUpload: false,
      activeSentence: "",
      submitRequested: false,
      phase: "idle",
      audioContext: null,
      analyser: null,
      analyserSource: null,
      analyserData: null,
      analyserRaf: 0,
      monitorSupported: false,
      detectedSignal: false,
      maxInputLevel: 0,
      recordingStartedAt: 0,
    };
    var lastEvaluatedSentence = "";
    var lastEvaluatedDemoAudioUrl = "";
    var lastEvalAverageTotal = null;
    var sentenceDemoAudio = null;
    var sentenceDemoFetchSeq = 0;
    var sentenceDemoAudioUrlBySentence = {};
    var isWordRequestPending = false;
    var isScoreRequestPending = false;

    function hasPendingScriptRequest() {
      return isWordRequestPending || isScoreRequestPending;
    }

    function syncScriptRequestLocks() {
      var locked = hasPendingScriptRequest();
      if (inputEl) inputEl.disabled = locked;
      if (sendBtn) sendBtn.disabled = locked;
      if (scenarioSelectEl) scenarioSelectEl.disabled = locked;
      if (scoreToggleEl) scoreToggleEl.disabled = locked;
      if (scoreDemoBtn) scoreDemoBtn.disabled = locked;
      if (scoreRetryBtn) scoreRetryBtn.disabled = locked;
      if (quickWordsBtns) {
        quickWordsBtns.querySelectorAll(".script-quick-words__btn").forEach(function (btn) {
          btn.disabled = locked;
        });
      }
      chatBoardEl.querySelectorAll("[data-script-mic]").forEach(function (btn) {
        btn.disabled = locked;
      });
      chatBoardEl.querySelectorAll(".chat-message__submit-rec").forEach(function (btn) {
        btn.disabled = locked;
      });
    }

    function setScriptRequestPending(kind, pending) {
      if (kind === "word") {
        isWordRequestPending = !!pending;
      } else if (kind === "score") {
        isScoreRequestPending = !!pending;
      }
      syncScriptRequestLocks();
    }

    syncScriptRequestLocks();

    function uiSafePanelErr(s) {
      var t = String(s || "").trim();
      if (!t) return "";
      if (/請重新錄音/.test(t)) return "請重新錄音";
      if (/網路|伺服器/.test(t)) return "網路或伺服器錯誤";
      if (
        t.length > 160 ||
        /headers:|status_code:|'detail'|traceback|file "|apierror|\[object object\]|models\/|generatecontent|api version|grpc|debug_error_string|gemini|google|azure|ffmpeg|exception|not found/i.test(
          t
        )
      ) {
        return "系統忙線中，請稍後再試";
      }
      return t;
    }

    function stopSentenceDemoAudio() {
      if (!sentenceDemoAudio) return;
      try {
        sentenceDemoAudio.pause();
        sentenceDemoAudio.removeAttribute("src");
        sentenceDemoAudio.load();
      } catch (e) {
        /* ignore */
      }
      sentenceDemoAudio = null;
    }

    function finishDemoWaveUi() {
      if (!scoreWaveEl) return;
      var rk = rankFromAverage(lastEvalAverageTotal);
      if (rk !== "尚未評分") {
        scoreWaveEl.textContent = "等級評定 " + rk;
      } else {
        setWaveformActingFirstHint();
      }
    }

    /** 「看我示範」取得網址後播放；失敗只顯示「請再試一次就好」（402 付費提示除外）。 */
    function playSentenceDemoFromUrl(absUrl, seq) {
      if (scoreWaveEl) scoreWaveEl.classList.remove("waveform-placeholder--loading");
      function fail() {
        if (scoreWaveEl && seq === sentenceDemoFetchSeq) {
          scoreWaveEl.textContent = "請再試一次就好";
        }
        try {
          if (sentenceDemoAudio) {
            sentenceDemoAudio.pause();
            sentenceDemoAudio.removeAttribute("src");
          }
        } catch (e2) {
          /* ignore */
        }
        sentenceDemoAudio = null;
      }
      var a = new Audio(absUrl);
      sentenceDemoAudio = a;
      a.addEventListener(
        "ended",
        function () {
          if (sentenceDemoAudio === a) sentenceDemoAudio = null;
        },
        { once: true }
      );
      a.addEventListener(
        "error",
        function () {
          if (sentenceDemoAudio === a) sentenceDemoAudio = null;
          fail();
        },
        { once: true }
      );
      var pr = a.play();
      if (pr && typeof pr.then === "function") {
        pr.then(function () {
          if (seq !== sentenceDemoFetchSeq) return;
          finishDemoWaveUi();
        }).catch(fail);
      } else {
        finishDemoWaveUi();
      }
    }

    function absoluteApiMediaUrl(path) {
      if (!path || typeof path !== "string") return "";
      var p = path.trim();
      if (!p) return "";
      if (p.indexOf("http://") === 0 || p.indexOf("https://") === 0) return p;
      if (!pageApiOrigin) return "";
      return pageApiOrigin + (p.charAt(0) === "/" ? p : "/" + p);
    }

    function playPreparedAudioUrl(path) {
      var absUrl = absoluteApiMediaUrl(path);
      if (!absUrl) return false;
      stopSentenceDemoAudio();
      var a = new Audio(absUrl);
      sentenceDemoAudio = a;
      a.addEventListener(
        "ended",
        function () {
          if (sentenceDemoAudio === a) sentenceDemoAudio = null;
        },
        { once: true }
      );
      a.addEventListener(
        "error",
        function () {
          if (sentenceDemoAudio === a) sentenceDemoAudio = null;
        },
        { once: true }
      );
      var pr = a.play();
      if (pr && typeof pr.catch === "function") {
        pr.catch(function () {
          if (sentenceDemoAudio === a) sentenceDemoAudio = null;
        });
      }
      return true;
    }

    function uiSafeDemoMessage(raw, status) {
      if (status === 402) return "示範語音需 ElevenLabs 付費方案，請至官網升級後再試。";
      if (status === 401) return "示範語音未授權，請檢查後端 API 金鑰。";
      if (status === 429) return "示範語音請求過於頻繁，請稍後再試。";
      if (status === 503) return "示範語音服務未設定。";
      if (typeof raw !== "string") return "示範語音載入失敗。";
      var s = raw.trim();
      if (!s) return "示範語音載入失敗。";
      if (
        s.length > 120 ||
        /[\]\[{}]|headers:|status_code:|'detail'|traceback|\bFile "|apierror|request_id/i.test(s)
      ) {
        return "示範語音暫時無法使用，請稍後再試。";
      }
      return s;
    }

    async function fetchSentenceDemoPlaybackUrl(sentence) {
      if (!pageApiOrigin) {
        return { ok: false, status: 0, error: "無法取得 API 位址" };
      }
      var base = pageApiOrigin;
      var response = await fetch(base + "/sentence-demo-audio", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sentence: sentence,
          scenario: scenarioZhFromSelect(scenarioSelectEl),
        }),
      });
      var data = {};
      try {
        data = await response.json();
      } catch (e1) {
        data = {};
      }
      if (!response.ok) {
        return {
          ok: false,
          status: response.status,
          error: uiSafeDemoMessage((data && data.error) || "", response.status),
        };
      }
      var rel = typeof data.sentence_demo_audio_url === "string" ? data.sentence_demo_audio_url.trim() : "";
      if (!rel) {
        return { ok: false, status: response.status, error: "後端未回傳示範音檔" };
      }
      var abs = absoluteApiMediaUrl(rel);
      return abs ? { ok: true, url: abs } : { ok: false, status: response.status, error: "無法組合音檔網址" };
    }

    var SCORE_RANGE_TO_NUM = {
      scoreRangeAccuracy: "scoreNumAccuracy",
      scoreRangeProsody: "scoreNumProsody",
      scoreRangeActing: "scoreNumActing",
    };

    function pickAudioMime() {
      if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) return "audio/webm;codecs=opus";
      if (MediaRecorder.isTypeSupported("audio/webm")) return "audio/webm";
      return "";
    }

    function resetRecordingSignalState() {
      recState.detectedSignal = false;
      recState.maxInputLevel = 0;
      recState.recordingStartedAt = 0;
    }

    function stopMicSignalMonitor() {
      if (recState.analyserRaf) {
        cancelAnimationFrame(recState.analyserRaf);
        recState.analyserRaf = 0;
      }
      if (recState.analyserSource) {
        try {
          recState.analyserSource.disconnect();
        } catch (error) {}
      }
      if (recState.analyser) {
        try {
          recState.analyser.disconnect();
        } catch (error2) {}
      }
      if (recState.audioContext && typeof recState.audioContext.close === "function") {
        try {
          recState.audioContext.close();
        } catch (error3) {}
      }
      recState.audioContext = null;
      recState.analyser = null;
      recState.analyserSource = null;
      recState.analyserData = null;
      recState.monitorSupported = false;
      resetRecordingSignalState();
    }

    function startMicSignalMonitor(stream) {
      stopMicSignalMonitor();
      var AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx || !stream) return;
      try {
        var audioContext = new AudioCtx();
        var source = audioContext.createMediaStreamSource(stream);
        var analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);
        recState.audioContext = audioContext;
        recState.analyserSource = source;
        recState.analyser = analyser;
        recState.analyserData = new Float32Array(analyser.fftSize);
        recState.monitorSupported = true;
      } catch (error4) {
        stopMicSignalMonitor();
        return;
      }

      function sample() {
        if (!recState.analyser || !recState.analyserData) return;
        if (recState.phase === "recording") {
          recState.analyser.getFloatTimeDomainData(recState.analyserData);
          var peak = 0;
          var sumSquares = 0;
          var i;
          for (i = 0; i < recState.analyserData.length; i += 1) {
            var value = recState.analyserData[i];
            var abs = Math.abs(value);
            if (abs > peak) peak = abs;
            sumSquares += value * value;
          }
          var rms = Math.sqrt(sumSquares / recState.analyserData.length);
          if (peak > recState.maxInputLevel) recState.maxInputLevel = peak;
          if (peak >= MIN_RECORDING_PEAK_LEVEL || rms >= MIN_RECORDING_RMS_LEVEL) {
            recState.detectedSignal = true;
          }
        }
        recState.analyserRaf = requestAnimationFrame(sample);
      }

      recState.analyserRaf = requestAnimationFrame(sample);
    }

    function stopRecStream() {
      stopMicSignalMonitor();
      if (recState.stream) {
        recState.stream.getTracks().forEach(function (t) {
          t.stop();
        });
        recState.stream = null;
      }
    }

    function showInvalidRecordingMessage() {
      var fbEl = document.getElementById("scoreActingFeedback");
      if (fbEl) fbEl.textContent = "請重新錄音";
      setWaveformActingFirstHint();
    }

    function hideAllSubmitRec() {
      chatBoardEl.querySelectorAll(".chat-message__submit-rec").forEach(function (b) {
        b.hidden = true;
      });
    }

    function showSubmitRecFor(micBtn) {
      hideAllSubmitRec();
      if (!micBtn) return;
      var row = micBtn.parentElement;
      if (!row) return;
      var sub = row.querySelector(".chat-message__submit-rec");
      if (sub) {
        sub.hidden = false;
        sub.disabled = hasPendingScriptRequest();
      }
    }

    function setMicIdleUi(btn) {
      if (!btn) return;
      btn.setAttribute("aria-pressed", "false");
      var acting = document.body.classList.contains("acting-mode");
      btn.setAttribute("aria-label", acting ? "開啟麥克風" : "錄製台詞");
      var layers = btn.querySelectorAll(".chat-message__media-btn-layer");
      if (layers.length >= 2) {
        layers[0].hidden = false;
        layers[1].hidden = true;
      }
    }

    function setMicArmedUi(btn) {
      if (!btn) return;
      btn.setAttribute("aria-pressed", "false");
      btn.setAttribute("aria-label", "開始錄音");
      var layers = btn.querySelectorAll(".chat-message__media-btn-layer");
      if (layers.length >= 2) {
        layers[0].hidden = false;
        layers[1].hidden = true;
      }
    }

    function setMicRecordingUi(btn, on) {
      if (!btn) return;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.setAttribute("aria-label", on ? "錄製中" : "開始錄音");
      var layers = btn.querySelectorAll(".chat-message__media-btn-layer");
      if (layers.length >= 2) {
        layers[0].hidden = !!on;
        layers[1].hidden = !on;
      }
    }

    function setWaveformActingFirstHint() {
      if (!scoreWaveEl) return;
      scoreWaveEl.classList.remove("waveform-placeholder--loading");
      scoreWaveEl.textContent = document.body.classList.contains("acting-mode")
        ? "點選對話中的麥克風以開啟"
        : "點選麥克風開始錄音";
    }

    function setWaveformArmHint() {
      if (!scoreWaveEl) return;
      scoreWaveEl.textContent = "請點擊麥克風開始你的表演";
      scoreWaveEl.classList.remove("waveform-placeholder--loading");
    }

    function setWaveformIdleHint() {
      setWaveformActingFirstHint();
    }

    function setWaveformRecording() {
      if (!scoreWaveEl) return;
      scoreWaveEl.textContent = "錄製中...";
      scoreWaveEl.classList.remove("waveform-placeholder--loading");
    }

    function setWaveformJudging() {
      if (!scoreWaveEl) return;
      scoreWaveEl.textContent = "評審正在絞盡腦汁";
      scoreWaveEl.classList.add("waveform-placeholder--loading");
    }

    function clearWaveformPulse() {
      if (!scoreWaveEl) return;
      scoreWaveEl.classList.remove("waveform-placeholder--loading");
    }

    function releaseActingMicResources() {
      hideAllSubmitRec();
      if (recState.mediaRecorder && recState.mediaRecorder.state === "recording") {
        recState.abortUpload = true;
        recState.submitRequested = false;
        try {
          recState.mediaRecorder.stop();
        } catch (e1) {
          /* ignore */
        }
        return;
      }
      stopRecStream();
      recState.mediaRecorder = null;
      recState.chunks = [];
      if (recState.button) setMicIdleUi(recState.button);
      recState.button = null;
      recState.phase = "idle";
      recState.activeSentence = "";
      recState.submitRequested = false;
      recState.abortUpload = false;
    }

    var scoreRangeAnimateSeq = 0;

    function setRangeScore(id, val, immediate) {
      var el = document.getElementById(id);
      if (!el) return;
      var nid = SCORE_RANGE_TO_NUM[id];
      var numEl = nid ? document.getElementById(nid) : null;
      var showDash = val == null || val === "" || (typeof val === "number" && isNaN(val));
      if (showDash) {
        scoreRangeAnimateSeq += 1;
        el.value = "0";
        if (numEl) numEl.textContent = "—";
        return;
      }
      var target = Math.max(0, Math.min(100, Math.round(Number(val))));
      if (isNaN(target)) {
        scoreRangeAnimateSeq += 1;
        el.value = "0";
        if (numEl) numEl.textContent = "—";
        return;
      }
      if (immediate === true) {
        scoreRangeAnimateSeq += 1;
        el.value = String(target);
        if (numEl) numEl.textContent = String(target);
        return;
      }
      var start = parseInt(String(el.value), 10);
      if (isNaN(start)) start = 0;
      start = Math.max(0, Math.min(100, start));
      var mySeq = ++scoreRangeAnimateSeq;
      var dur = 620;
      var t0 = null;
      function easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
      }
      function tick(ts) {
        if (mySeq !== scoreRangeAnimateSeq) return;
        if (t0 === null) t0 = ts;
        var p = Math.min(1, (ts - t0) / dur);
        var cur = Math.round(start + (target - start) * easeOutCubic(p));
        el.value = String(cur);
        if (numEl) numEl.textContent = String(cur);
        if (p < 1) {
          requestAnimationFrame(tick);
        } else {
          el.value = String(target);
          if (numEl) numEl.textContent = String(target);
        }
      }
      requestAnimationFrame(tick);
    }

    function rankFromAverage(avg) {
      if (avg == null || avg === "" || (typeof avg === "number" && isNaN(avg))) return "尚未評分";
      var v = Number(avg);
      if (isNaN(v)) return "尚未評分";
      if (v >= 88) return "LEVEL 5：鏡頭前的主角";
      if (v >= 75) return "LEVEL 4：有戲的配角";
      if (v >= 60) return "LEVEL 3：能吃鏡的臨演";
      if (v >= 45) return "LEVEL 2：漢江旁的背景板";
      return "LEVEL 1：被剪光的龍套";
    }

    function applyEvalToPanel(data, sentence) {
      lastEvaluatedSentence = sentence || "";
      lastEvaluatedDemoAudioUrl = lastEvaluatedSentence
        ? sentenceDemoAudioUrlBySentence[lastEvaluatedSentence] || ""
        : "";
      lastEvalAverageTotal =
        data.average_total != null && data.average_total !== "" && !isNaN(Number(data.average_total))
          ? Number(data.average_total)
          : null;
      setRangeScore("scoreRangeAccuracy", data.accuracy_score, true);
      setRangeScore("scoreRangeProsody", data.prosody_score, true);
      setRangeScore("scoreRangeActing", data.score_acting, true);
      var rankEl = document.getElementById("scoreTotalRank");
      var avgLine = document.getElementById("scoreAverageLine");
      var scored =
        data.average_total != null && data.average_total !== "" && !isNaN(Number(data.average_total));
      if (avgLine) {
        avgLine.textContent = scored ? "總分 " + String(data.average_total) + " 分" : "總分 —";
      }
      if (rankEl) rankEl.textContent = rankFromAverage(data.average_total);
      var fbEl = document.getElementById("scoreActingFeedback");
      var fb = typeof data.feedback_acting === "string" ? data.feedback_acting.trim() : "";
      if (data.azure_error) fb += (fb ? "\n" : "") + "[發音] " + uiSafePanelErr(data.azure_error);
      if (data.gemini_error) fb += (fb ? "\n" : "") + "[演技] " + uiSafePanelErr(data.gemini_error);
      if (fbEl) fbEl.textContent = fb;
      if (scoreWaveEl) {
        var rk = rankFromAverage(data.average_total);
        scoreWaveEl.classList.remove("waveform-placeholder--loading");
        if (rk !== "尚未評分") {
          scoreWaveEl.textContent = "等級評定 " + rk;
        } else {
          setWaveformActingFirstHint();
        }
      }
    }

    function resetScorePanel() {
      lastEvaluatedSentence = "";
      lastEvaluatedDemoAudioUrl = "";
      lastEvalAverageTotal = null;
      stopSentenceDemoAudio();
      if (recState.mediaRecorder && recState.mediaRecorder.state === "recording") {
        recState.abortUpload = true;
        recState.submitRequested = false;
        try {
          recState.mediaRecorder.stop();
        } catch (er) {
          /* ignore */
        }
      }
      releaseActingMicResources();
      setRangeScore("scoreRangeAccuracy", null, true);
      setRangeScore("scoreRangeProsody", null, true);
      setRangeScore("scoreRangeActing", null, true);
      var rankEl = document.getElementById("scoreTotalRank");
      var avgLine = document.getElementById("scoreAverageLine");
      var fbEl = document.getElementById("scoreActingFeedback");
      if (avgLine) avgLine.textContent = "總分 —";
      if (rankEl) rankEl.textContent = "尚未評分";
      if (fbEl) fbEl.textContent = "";
      hideAllSubmitRec();
      setWaveformActingFirstHint();
      chatBoardEl.querySelectorAll("[data-script-mic]").forEach(function (m) {
        setMicIdleUi(m);
      });
    }

    async function postEvaluateActing(blob, mimeHint, sentence) {
      if (hasPendingScriptRequest()) return;
      if (!pageApiOrigin) {
        clearWaveformPulse();
        setWaveformIdleHint();
        return;
      }
      setScriptRequestPending("score", true);
      var base = pageApiOrigin;
      var ext = ".webm";
      var mt = mimeHint || "audio/webm";
      if (mt.indexOf("wav") !== -1) {
        ext = ".wav";
      }
      var fd = new FormData();
      fd.append("audio", blob, "take" + ext);
      fd.append("sentence", sentence);
      fd.append("scenario", scenarioZhFromSelect(scenarioSelectEl));
      try {
        var response = await fetch(base + "/evaluate-acting", {
          method: "POST",
          credentials: "include",
          body: fd,
        });
        var data = {};
        try {
          data = await response.json();
        } catch (e2) {
          data = {};
        }
        if (!response.ok) {
          var errTop =
            data && data.error ? String(data.error) : "請求失敗 (" + response.status + ")";
          errTop = uiSafePanelErr(errTop) || "評分請求失敗";
          var azureMsg = data.azure_error ? uiSafePanelErr(data.azure_error) : "";
          var geminiMsg = data.gemini_error ? uiSafePanelErr(data.gemini_error) : "";
          if (!azureMsg && !geminiMsg && errTop) {
            geminiMsg = errTop;
          }
          applyEvalToPanel(
            {
              accuracy_score: data.accuracy_score,
              prosody_score: data.prosody_score,
              score_acting: data.score_acting,
              feedback_acting: typeof data.feedback_acting === "string" ? data.feedback_acting : "",
              average_total: data.average_total,
              azure_error: azureMsg,
              gemini_error: geminiMsg,
            },
            sentence
          );
          return;
        }
        applyEvalToPanel(data, sentence);
      } catch (err) {
        var em = err && err.message ? String(err.message) : String(err);
        applyEvalToPanel(
          {
            accuracy_score: null,
            prosody_score: null,
            score_acting: null,
            feedback_acting: "",
            average_total: null,
            azure_error: uiSafePanelErr(em) || "網路或伺服器錯誤",
            gemini_error: "",
          },
          sentence
        );
      } finally {
        setScriptRequestPending("score", false);
        clearWaveformPulse();
      }
    }

    function getLastMicFromChat() {
      var nodes = chatBoardEl.querySelectorAll("[data-script-mic]");
      if (!nodes.length) return { sentence: "", mic: null };
      var last = nodes[nodes.length - 1];
      return { sentence: (last.dataset.scriptSentence || "").trim(), mic: last };
    }

    function beginActualRecording() {
      if (!recState.mediaRecorder || recState.phase !== "armed") return;
      if (recState.mediaRecorder.state !== "inactive") return;
      recState.submitRequested = false;
      recState.abortUpload = false;
      resetRecordingSignalState();
      recState.recordingStartedAt = Date.now();
      if (recState.audioContext && typeof recState.audioContext.resume === "function") {
        recState.audioContext.resume().catch(function () {});
      }
      try {
        recState.mediaRecorder.start();
      } catch (e0) {
        releaseActingMicResources();
        setWaveformActingFirstHint();
        return;
      }
      recState.phase = "recording";
      setMicRecordingUi(recState.button, true);
      setWaveformRecording();
      showSubmitRecFor(recState.button);
    }

    function armActingMic(micBtn, sentence) {
      var s = (sentence || "").trim();
      if (!s || !micBtn) return;
      if (hasPendingScriptRequest()) return;
      if (recState.phase === "recording") return;
      if (recState.phase === "armed" && recState.button === micBtn) return;
      if (recState.phase !== "idle" || recState.mediaRecorder || recState.stream) {
        releaseActingMicResources();
      }
      hideAllSubmitRec();
      recState.activeSentence = s;
      recState.submitRequested = false;
      recState.abortUpload = false;
      var mime = pickAudioMime();
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return;
      }
      navigator.mediaDevices
        .getUserMedia({ audio: true })
        .then(function (stream) {
          if (recState.stream && recState.stream !== stream) {
            stopRecStream();
          }
          recState.stream = stream;
          recState.chunks = [];
          recState.button = micBtn;
          recState.mime = mime;
          resetRecordingSignalState();
          startMicSignalMonitor(stream);
          var opts = mime ? { mimeType: mime } : undefined;
          var mr = new MediaRecorder(stream, opts || {});
          recState.mediaRecorder = mr;
          mr.ondataavailable = function (ev) {
            if (ev.data && ev.data.size > 0) recState.chunks.push(ev.data);
          };
          mr.onstop = function () {
            var usedMime = mr.mimeType || recState.mime || "audio/webm";
            var skipUpload = recState.abortUpload;
            var doSubmit = recState.submitRequested;
            var recordingStartedAt = recState.recordingStartedAt;
            var detectedSignal = recState.detectedSignal;
            var monitorSupported = recState.monitorSupported;
            recState.abortUpload = false;
            recState.submitRequested = false;
            stopRecStream();
            var btnRef = recState.button;
            setMicIdleUi(btnRef);
            hideAllSubmitRec();
            var chunks = recState.chunks.slice();
            var blobSentence = recState.activeSentence;
            recState.mediaRecorder = null;
            recState.chunks = [];
            recState.button = null;
            recState.activeSentence = "";
            recState.phase = "idle";
            if (skipUpload || !doSubmit) {
              setWaveformActingFirstHint();
              return;
            }
            var blob = new Blob(chunks, { type: usedMime });
            var recordedMs = recordingStartedAt ? Date.now() - recordingStartedAt : 0;
            if (blob.size < MIN_RECORDING_BLOB_BYTES || recordedMs < MIN_RECORDING_DURATION_MS) {
              showInvalidRecordingMessage();
              return;
            }
            if (monitorSupported && !detectedSignal) {
              showInvalidRecordingMessage();
              return;
            }
            setWaveformJudging();
            postEvaluateActing(blob, usedMime, blobSentence);
          };
          chatBoardEl.querySelectorAll("[data-script-mic]").forEach(function (m) {
            setMicIdleUi(m);
          });
          recState.phase = "armed";
          setMicArmedUi(micBtn);
          setWaveformArmHint();
        })
        .catch(function () {
          stopRecStream();
          setMicIdleUi(micBtn);
          recState.mediaRecorder = null;
          recState.button = null;
          recState.phase = "idle";
          recState.activeSentence = "";
          recState.chunks = [];
          setWaveformActingFirstHint();
        });
    }

    function openScoreEnableDialog(source, micEl) {
      if (hasPendingScriptRequest()) return;
      pendingScoreDialog.source = source === "mic" ? "mic" : "toggle";
      pendingScoreDialog.mic = micEl || null;
      if (!scoreEnableDialogEl || typeof scoreEnableDialogEl.showModal !== "function") return;
      scoreEnableDialogEl.showModal();
    }

    function handleMicInActingMode(btn) {
      var sentence = (btn.dataset.scriptSentence || "").trim();
      if (!sentence) return;
      if (recState.phase === "recording") return;
      if (recState.phase === "armed" && recState.button === btn) {
        beginActualRecording();
        return;
      }
      armActingMic(btn, sentence);
    }

    chatBoardEl.addEventListener(
      "click",
      function (e) {
        var sub = e.target.closest(".chat-message__submit-rec");
        if (sub && chatBoardEl.contains(sub) && !sub.hidden) {
          e.preventDefault();
          e.stopImmediatePropagation();
          if (hasPendingScriptRequest()) return;
          if (!document.body.classList.contains("acting-mode")) return;
          var row = sub.closest(".chat-message__media-actions");
          if (!row) return;
          var mic = row.querySelector("[data-script-mic]");
          if (!mic || mic !== recState.button) return;
          if (!recState.mediaRecorder || recState.mediaRecorder.state !== "recording") return;
          recState.submitRequested = true;
          recState.mediaRecorder.stop();
          return;
        }

        var btn = e.target.closest("[data-script-mic]");
        if (!btn || !chatBoardEl.contains(btn)) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        if (hasPendingScriptRequest()) return;
        if (!document.body.classList.contains("acting-mode")) {
          openScoreEnableDialog("mic", btn);
          return;
        }
        handleMicInActingMode(btn);
      },
      true
    );

    if (scoreToggleEl) {
      scoreToggleEl.addEventListener("change", function () {
        if (hasPendingScriptRequest()) return;
        if (scoreToggleEl.checked) {
          scoreToggleEl.checked = false;
          openScoreEnableDialog("toggle", null);
        } else {
          setActingModeVisual(false);
          releaseActingMicResources();
          setWaveformActingFirstHint();
        }
      });
    }

    if (scoreEnableConfirmEl && scoreEnableDialogEl) {
      scoreEnableConfirmEl.addEventListener("click", function () {
        if (hasPendingScriptRequest()) return;
        setActingModeVisual(true);
        playActingModeEntrySound();
        if (scoreToggleEl) scoreToggleEl.checked = true;
        if (typeof scoreEnableDialogEl.close === "function") scoreEnableDialogEl.close();
        var src = pendingScoreDialog.source;
        var micFromDialog = pendingScoreDialog.mic;
        pendingScoreDialog.source = "toggle";
        pendingScoreDialog.mic = null;
        var sentence = "";
        var targetMic = null;
        if (src === "mic" && micFromDialog) {
          sentence = (micFromDialog.dataset.scriptSentence || "").trim();
          targetMic = micFromDialog;
        } else {
          var last = getLastMicFromChat();
          sentence = last.sentence;
          targetMic = last.mic;
        }
        if (!sentence || !targetMic) {
          if (scoreWaveEl) {
            scoreWaveEl.textContent = "請先送出單字產生台詞";
            scoreWaveEl.classList.remove("waveform-placeholder--loading");
          }
          return;
        }
        armActingMic(targetMic, sentence);
      });
    }

    if (scoreEnableDismissEl && scoreEnableDialogEl) {
      scoreEnableDismissEl.addEventListener("click", function () {
        if (typeof scoreEnableDialogEl.close === "function") scoreEnableDialogEl.close();
      });
    }

    if (scoreDemoBtn) {
      scoreDemoBtn.addEventListener("click", function () {
        if (hasPendingScriptRequest()) return;
        var text = (lastEvaluatedSentence || "").trim();
        if (!text) return;
        if (!pageApiOrigin) return;
        var seq = ++sentenceDemoFetchSeq;
        stopSentenceDemoAudio();
        var preparedUrl = absoluteApiMediaUrl(lastEvaluatedDemoAudioUrl);
        if (preparedUrl) {
          playSentenceDemoFromUrl(preparedUrl, seq);
          return;
        }
        if (scoreWaveEl) {
          scoreWaveEl.classList.add("waveform-placeholder--loading");
          scoreWaveEl.textContent = "載入示範音檔…";
        }
        fetchSentenceDemoPlaybackUrl(text)
          .then(function (res) {
            if (seq !== sentenceDemoFetchSeq) return;
            if (scoreWaveEl) {
              scoreWaveEl.classList.remove("waveform-placeholder--loading");
            }
            if (!res.ok) {
              if (scoreWaveEl) {
                scoreWaveEl.textContent =
                  res.status === 402 ? res.error : "請再試一次就好";
              }
              return;
            }
            lastEvaluatedDemoAudioUrl = res.url;
            sentenceDemoAudioUrlBySentence[text] = res.url;
            playSentenceDemoFromUrl(res.url, seq);
          })
          .catch(function () {
            if (seq !== sentenceDemoFetchSeq) return;
            if (scoreWaveEl) {
              scoreWaveEl.classList.remove("waveform-placeholder--loading");
              scoreWaveEl.textContent = "請再試一次就好";
            }
          });
      });
    }

    if (scoreRetryBtn) {
      scoreRetryBtn.addEventListener("click", function () {
        if (hasPendingScriptRequest()) return;
        resetScorePanel();
      });
    }

    levelTextEl.textContent = level || "未選擇";
    var picksPayload = await fetchScriptWordPicks();
    if (quickWordsEl && quickWordsBtns && picksPayload && Array.isArray(picksPayload.picks)) {
      renderQuickWordButtons(quickWordsEl, quickWordsBtns, inputEl, picksPayload.picks);
      syncScriptRequestLocks();
    }

    var vocabEntries = await loadVocab(level);
    var meaningByWord = {};
    vocabEntries.forEach(function (entry) {
      if (!entry || !entry["韓文單字"] || !entry["中文意思"]) return;
      meaningByWord[entry["韓文單字"]] = entry["中文意思"];
    });

    function appendAssistantPlain(text) {
      var item = document.createElement("article");
      item.className = "chat-message chat-message--assistant";
      var inner = document.createElement("div");
      inner.className = "chat-message__inner";
      inner.appendChild(createSystemAvatar());
      var content = document.createElement("div");
      content.className = "chat-message__content";
      var wrap = document.createElement("div");
      wrap.className = "chat-message__bubble-wrap";
      var bubble = document.createElement("p");
      bubble.className = "chat-message__bubble";
      bubble.textContent = text;
      wrap.appendChild(bubble);
      content.appendChild(wrap);
      inner.appendChild(content);
      item.appendChild(inner);
      chatBoardEl.appendChild(item);
      chatBoardEl.scrollTop = chatBoardEl.scrollHeight;
    }

    /** @returns {HTMLElement} 完成請求後請移除此節點 */
    function appendAssistantThinking() {
      var item = document.createElement("article");
      item.className = "chat-message chat-message--assistant";
      item.setAttribute("data-script-thinking", "true");
      var inner = document.createElement("div");
      inner.className = "chat-message__inner";
      inner.appendChild(createSystemAvatar());
      var content = document.createElement("div");
      content.className = "chat-message__content";
      var wrap = document.createElement("div");
      wrap.className = "chat-message__bubble-wrap";
      var bubble = document.createElement("p");
      bubble.className = "chat-message__bubble";
      bubble.textContent = "容我好好想想...";
      wrap.appendChild(bubble);
      content.appendChild(wrap);
      inner.appendChild(content);
      item.appendChild(inner);
      chatBoardEl.appendChild(item);
      chatBoardEl.scrollTop = chatBoardEl.scrollHeight;
      return item;
    }

    function appendUserMessage(word) {
      var item = document.createElement("article");
      item.className = "chat-message chat-message--user";
      var inner = document.createElement("div");
      inner.className = "chat-message__inner";
      var content = document.createElement("div");
      content.className = "chat-message__content";
      var wrap = document.createElement("div");
      wrap.className = "chat-message__bubble-wrap";
      var bubble = document.createElement("p");
      bubble.className = "chat-message__bubble";
      bubble.textContent = word;
      wrap.appendChild(bubble);
      content.appendChild(wrap);
      inner.appendChild(content);
      inner.appendChild(createUserAvatar());
      item.appendChild(inner);
      chatBoardEl.appendChild(item);
      chatBoardEl.scrollTop = chatBoardEl.scrollHeight;
    }

    function setFavoriteButtonState(btn, filled) {
      btn.setAttribute("aria-pressed", filled ? "true" : "false");
      btn.setAttribute("aria-label", filled ? "取消收藏" : "收藏單字");
    }

    function appendAssistantWordCard(word, meaningZh, dramaLineKo, extras) {
      extras = extras || {};
      var audioUrl = typeof extras.audioUrl === "string" ? extras.audioUrl.trim() : "";
      var demoAudioUrl =
        typeof extras.sentenceDemoAudioUrl === "string" ? extras.sentenceDemoAudioUrl.trim() : "";
      if (demoAudioUrl && dramaLineKo) {
        sentenceDemoAudioUrlBySentence[dramaLineKo] = demoAudioUrl;
      }
      var lines = [];
      if (extras.levelWarning) lines.push(extras.levelWarning);
      lines.push("・「" + word + "」：" + meaningZh);
      lines.push("・" + dramaLineKo);
      if (extras.translationZh) lines.push(extras.translationZh);
      if (extras.analysisLines && extras.analysisLines.length) {
        lines.push("・其他重點：");
        extras.analysisLines.forEach(function (row) {
          if (row) lines.push(String(row));
        });
      }
      var displayText = lines.join("\n");

      var item = document.createElement("article");
      item.className = "chat-message chat-message--assistant";
      var inner = document.createElement("div");
      inner.className = "chat-message__inner";
      inner.appendChild(createSystemAvatar());

      var content = document.createElement("div");
      content.className = "chat-message__content";
      var row = document.createElement("div");
      row.className = "chat-message__bubble-row";

      var wrap = document.createElement("div");
      wrap.className = "chat-message__bubble-wrap chat-message__bubble-wrap--with-media";

      var bubble = document.createElement("p");
      bubble.className = "chat-message__bubble";
      bubble.textContent = displayText;

      var favBtn = document.createElement("button");
      favBtn.type = "button";
      favBtn.className = "chat-favorite-btn";
      favBtn.setAttribute("aria-pressed", "false");
      favBtn.setAttribute("aria-label", "收藏單字");
      favBtn.innerHTML =
        '<svg class="chat-favorite-icon chat-favorite-icon--outline" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
        '<path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>' +
        "</svg>" +
        '<svg class="chat-favorite-icon chat-favorite-icon--fill" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
        '<path fill="currentColor" d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>' +
        "</svg>";

      favBtn.addEventListener("click", function () {
        if (!window.KTL) return;
        var pressed = favBtn.getAttribute("aria-pressed") === "true";
        if (pressed) {
          if (typeof window.KTL.removeScriptFavorite === "function") {
            window.KTL.removeScriptFavorite(word);
          }
          setFavoriteButtonState(favBtn, false);
        } else {
          var added =
            typeof window.KTL.addScriptFavorite === "function" &&
            window.KTL.addScriptFavorite({
              word: word,
              meaningZh: meaningZh,
              dramaLineKo: dramaLineKo,
              sentenceStyle: scenarioZhFromSelect(scenarioSelectEl),
            });
          if (added || (window.KTL.isScriptFavoriteWord && window.KTL.isScriptFavoriteWord(word))) {
            setFavoriteButtonState(favBtn, true);
          }
        }
      });

      wrap.appendChild(bubble);
      wrap.appendChild(createWordCardMediaActions(dramaLineKo, audioUrl, playPreparedAudioUrl));
      row.appendChild(wrap);
      row.appendChild(favBtn);
      content.appendChild(row);
      inner.appendChild(content);
      item.appendChild(inner);
      chatBoardEl.appendChild(item);
      chatBoardEl.scrollTop = chatBoardEl.scrollHeight;
      syncScriptRequestLocks();
    }

    initFavoritesDropdown();

    appendAssistantPlain("請輸入你想練習的韓文單字。");

    formEl.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (hasPendingScriptRequest()) return;
      var word = normalizeWord(inputEl.value);
      if (!word) return;
      if (!isKoreanWordOnly(word)) {
        appendAssistantPlain("輸入非韓文，請重新輸入");
        return;
      }
      appendUserMessage(word);
      inputEl.value = "";

      var thinkingEl = appendAssistantThinking();
      var scenarioZh = scenarioZhFromSelect(scenarioSelectEl);
      var apiResult;
      setScriptRequestPending("word", true);
      try {
        apiResult = await requestProcessWord(word, scenarioZh);
      } finally {
        setScriptRequestPending("word", false);
        thinkingEl.remove();
      }

      var meaning = meaningByWord[word] || "尚未收錄此單字";
      var line = createDramaLine(word);

      if (!apiResult.ok) {
        appendAssistantPlain(
          apiResult.error === "目前測試人數過多，請稍後再試"
            ? apiResult.error
            : "系統忙線中，請稍後再試"
        );
        return;
      }

      line = apiResult.dramaLineKo || line;

      appendAssistantWordCard(word, meaning, line, {
        levelWarning: apiResult.levelWarning,
        translationZh: apiResult.translationZh,
        analysisLines: apiResult.analysisLines,
        audioUrl: apiResult.audioUrl,
        sentenceDemoAudioUrl: apiResult.sentenceDemoAudioUrl,
      });
    });
  });
})();
