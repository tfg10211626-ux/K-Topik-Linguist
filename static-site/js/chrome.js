(function () {
  var STORAGE_DIFFICULTY_KEY = "ktopik:selectedLevel";
  var STORAGE_FAVORITES_KEY = "ktopik:favoriteWordIds";
  var STORAGE_SCRIPT_FAVORITES_KEY = "ktopik:scriptFavorites";
  var STORAGE_SCRIPT_INPUT_PREFILL_KEY = "ktopik:scriptWordPrefill";

  function getConfirmedDifficulty() {
    try {
      return localStorage.getItem(STORAGE_DIFFICULTY_KEY) || "";
    } catch (e) {
      return "";
    }
  }

  function getFavoriteWordIds() {
    try {
      var raw = localStorage.getItem(STORAGE_FAVORITES_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  var authUser = null;
  var cloudSyncEnabled = false;
  var cloudFavorites = null;
  var cloudSyncPromise = null;
  var cloudPushTimer = null;
  var cloudPushJob = null;

  function getLocalScriptFavorites() {
    try {
      var raw = localStorage.getItem(STORAGE_SCRIPT_FAVORITES_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function getScriptFavorites() {
    return getLocalScriptFavorites();
  }

  function notifyFavoritesChanged() {
    try {
      window.dispatchEvent(new CustomEvent("ktl-script-favorites-changed"));
    } catch (e) {
      /* ignore */
    }
  }

  function commitFavorites(entries) {
    var list = Array.isArray(entries) ? entries : [];
    setLocalScriptFavorites(list);
    if (authUser && cloudSyncEnabled) {
      cloudFavorites = list.slice();
    }
  }

  function setLocalScriptFavorites(entries) {
    try {
      if (!Array.isArray(entries) || entries.length === 0) {
        localStorage.removeItem(STORAGE_SCRIPT_FAVORITES_KEY);
      } else {
        localStorage.setItem(STORAGE_SCRIPT_FAVORITES_KEY, JSON.stringify(entries));
      }
    } catch (e) {
      /* ignore */
    }
    notifyFavoritesChanged();
  }

  function clearVocabularyForLogout() {
    if (cloudPushTimer) {
      clearTimeout(cloudPushTimer);
      cloudPushTimer = null;
    }
    cloudPushJob = null;
    setLocalScriptFavorites([]);
    try {
      localStorage.removeItem(STORAGE_FAVORITES_KEY);
    } catch (e) {
      /* ignore */
    }
  }

  function pushFavoritesToCloudNow(list, replace) {
    if (!authUser || !cloudSyncEnabled) return Promise.resolve();
    var sentList = Array.isArray(list) ? list.slice() : [];
    return apiFetch("/api/vocabulary/favorites/sync", {
      method: "POST",
      body: JSON.stringify({ items: sentList, replace: !!replace }),
    })
      .then(async function (res) {
        if (res.ok) return res.json();
        var err = null;
        try {
          err = await res.json();
        } catch (e) {
          /* ignore */
        }
        console.warn("雲端同步失敗（本機已保留）", err || res.status);
        return null;
      })
      .then(function (data) {
        if (!data || !Array.isArray(data.items)) return;
        if (typeof data.count === "number" && data.count < sentList.length) {
          console.warn(
            "雲端只寫入 " + data.count + " / " + sentList.length + " 筆，請在 Supabase 執行 docs/supabase_fix_constraints.sql"
          );
        }
        commitFavorites(data.items);
      })
      .catch(function () {
        /* 雲端失敗時保留本機列表 */
      });
  }

  function pushFavoritesToCloud(list, replace) {
    if (!authUser || !cloudSyncEnabled) return;
    if (replace) {
      if (cloudPushTimer) {
        clearTimeout(cloudPushTimer);
        cloudPushTimer = null;
      }
      cloudPushJob = null;
      pushFavoritesToCloudNow(list, true);
      return;
    }
    cloudPushJob = {
      list: Array.isArray(list) ? list.slice() : [],
      replace: false,
    };
    if (cloudPushTimer) clearTimeout(cloudPushTimer);
    cloudPushTimer = setTimeout(function () {
      var job = cloudPushJob;
      cloudPushTimer = null;
      cloudPushJob = null;
      if (!job) return;
      pushFavoritesToCloudNow(job.list, job.replace);
    }, 400);
  }

  function setScriptFavorites(entries) {
    var list = Array.isArray(entries) ? entries : [];
    var prev = getLocalScriptFavorites();
    commitFavorites(list);
    if (!authUser || !cloudSyncEnabled) return;
    var nextMap = {};
    list.forEach(function (entry) {
      if (entry && entry.word) nextMap[entry.word] = true;
    });
    var removed = prev
      .map(function (entry) {
        return entry && entry.word;
      })
      .filter(function (word) {
        return word && !nextMap[word];
      });
    if (!removed.length) {
      pushFavoritesToCloud(list, false);
      return;
    }
    Promise.all(
      removed.map(function (word) {
        return apiFetch(
          "/api/vocabulary/favorites?word=" + encodeURIComponent(word),
          { method: "DELETE" }
        );
      })
    )
      .then(function () {
        return pullCloudFavorites();
      })
      .catch(function () {
        pushFavoritesToCloudNow(list, true);
      });
  }

  function mergeFavoriteEntries(cloudItems, localItems) {
    var map = {};
    function put(entry) {
      if (!entry || !entry.word) return;
      var prev = map[entry.word];
      if (!prev) {
        map[entry.word] = entry;
        return;
      }
      var prevAt = Date.parse(prev.savedAt || "") || 0;
      var nextAt = Date.parse(entry.savedAt || "") || 0;
      if (nextAt >= prevAt) map[entry.word] = entry;
    }
    (cloudItems || []).forEach(put);
    (localItems || []).forEach(put);
    return Object.keys(map).map(function (word) {
      return map[word];
    });
  }

  async function pullCloudFavorites() {
    var res = await apiFetch("/api/vocabulary/favorites", { method: "GET" });
    if (!res.ok) return;
    var data = await res.json();
    var cloudItems = data && Array.isArray(data.items) ? data.items : [];
    commitFavorites(cloudItems);
  }

  async function bootstrapLocalFavoritesToCloud() {
    var localItems = getLocalScriptFavorites();
    if (!localItems.length) return;
    var res = await apiFetch("/api/vocabulary/favorites", { method: "GET" });
    var cloudItems = [];
    if (res.ok) {
      var data = await res.json();
      cloudItems = data && Array.isArray(data.items) ? data.items : [];
    }
    var merged = mergeFavoriteEntries(cloudItems, localItems);
    await pushFavoritesToCloudNow(merged, true);
  }

  function syncCloudFavorites(justLoggedIn) {
    if (!authUser || !cloudSyncEnabled) {
      cloudFavorites = null;
      return Promise.resolve();
    }
    if (cloudSyncPromise) return cloudSyncPromise;
    cloudSyncPromise = (async function () {
      try {
        if (justLoggedIn) {
          await bootstrapLocalFavoritesToCloud();
        }
        await pullCloudFavorites();
      } catch (e) {
        /* 保留本機 */
      }
    })().finally(function () {
      cloudSyncPromise = null;
    });
    return cloudSyncPromise;
  }

  function assetDataPath(relativePath) {
    var loc = window.location;
    if (
      loc.protocol !== "file:" &&
      loc.port === "5000" &&
      (loc.hostname === "localhost" || loc.hostname === "127.0.0.1")
    ) {
      return "/data/" + relativePath;
    }
    return "../data/" + relativePath;
  }

  var VOCAB_BY_LEVEL = {
    "初級": assetDataPath("processed/vocab_books/topik_vol_beginner.zh.v1.json"),
    "中級": assetDataPath("processed/vocab_books/topik_vol_intermediate.zh.v1.json"),
    "高級": assetDataPath("processed/vocab_books/topik_advanced.zh.v1.json"),
  };

  var studySuffixesPromise = null;

  function ensureStudySuffixes() {
    if (window.KTL && Array.isArray(window.KTL.STUDY_SUFFIXES)) {
      return Promise.resolve(window.KTL.STUDY_SUFFIXES);
    }
    if (!studySuffixesPromise) {
      studySuffixesPromise = fetch(assetDataPath("shared/study_suffixes.json"))
        .then(function (res) {
          return res.ok ? res.json() : [];
        })
        .then(function (arr) {
          window.KTL.STUDY_SUFFIXES = Array.isArray(arr) ? arr : [];
          return window.KTL.STUDY_SUFFIXES;
        })
        .catch(function () {
          window.KTL.STUDY_SUFFIXES = [];
          return window.KTL.STUDY_SUFFIXES;
        });
    }
    return studySuffixesPromise;
  }

  async function apiFetch(path, options) {
    var base = getApiOrigin();
    var opts = options || {};
    opts.credentials = "include";
    if (!opts.headers) opts.headers = {};
    if (opts.body && !opts.headers["Content-Type"]) {
      opts.headers["Content-Type"] = "application/json";
    }
    return fetch(base + path, opts);
  }

  function isScriptFavoriteWord(word) {
    if (!word) return false;
    return getScriptFavorites().some(function (entry) {
      return entry && entry.word === word;
    });
  }

  function addScriptFavorite(entry) {
    if (!entry || !entry.word) return false;
    var list = getScriptFavorites();
    if (list.some(function (x) { return x.word === entry.word; })) return false;
    var item = {
      word: entry.word,
      meaningZh: entry.meaningZh || "",
      dramaLineKo: entry.dramaLineKo || "",
      sentenceStyle: entry.sentenceStyle || "",
      savedAt: new Date().toISOString(),
    };
    list.push(item);
    commitFavorites(list);
    if (authUser && cloudSyncEnabled) {
      pushFavoritesToCloud(getLocalScriptFavorites(), true);
    }
    return true;
  }

  function removeScriptFavorite(word) {
    if (!word) return;
    var value = String(word).trim();
    if (!value) return;
    var next = getLocalScriptFavorites().filter(function (x) {
      return !x || x.word !== value;
    });
    commitFavorites(next);
    if (!authUser || !cloudSyncEnabled) return;
    apiFetch("/api/vocabulary/favorites?word=" + encodeURIComponent(value), {
      method: "DELETE",
    })
      .then(function (res) {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then(function (data) {
        if (data && Array.isArray(data.items)) commitFavorites(data.items);
      })
      .catch(function () {
        pushFavoritesToCloud(next, true);
      });
  }

  function renderAuthWidget() {
    var slot = document.getElementById("ktlAuthSlot");
    if (!slot) return;
    slot.innerHTML = "";

    var wrap = document.createElement("div");
    wrap.className = "auth-widget";
    wrap.id = "ktlAuthWidget";

    if (!authUser) {
      var loginBtn = document.createElement("button");
      loginBtn.type = "button";
      loginBtn.className = "auth-widget__login";
      loginBtn.id = "ktlGoogleLoginBtn";
      loginBtn.textContent = "Google 登入";
      loginBtn.addEventListener("click", function () {
        window.location.href = getApiOrigin() + "/api/auth/google";
      });
      wrap.appendChild(loginBtn);
      slot.appendChild(wrap);
      return;
    }

    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "auth-widget__trigger";
    trigger.id = "ktlAuthMenuBtn";
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-haspopup", "menu");
    trigger.setAttribute("aria-label", "帳號選單");

    if (authUser.avatarUrl) {
      var img = document.createElement("img");
      img.className = "auth-widget__avatar";
      img.src = authUser.avatarUrl;
      img.alt = "";
      trigger.appendChild(img);
    } else {
      var fallback = document.createElement("span");
      fallback.className = "auth-widget__avatar-fallback";
      var label = (authUser.displayName || authUser.email || "U").trim();
      fallback.textContent = label ? label.charAt(0).toUpperCase() : "U";
      trigger.appendChild(fallback);
    }

    var menu = document.createElement("div");
    menu.className = "auth-widget__menu";
    menu.id = "ktlAuthMenu";
    menu.setAttribute("role", "menu");
    menu.hidden = true;

    var logoutBtn = document.createElement("button");
    logoutBtn.type = "button";
    logoutBtn.className = "auth-widget__menu-item";
    logoutBtn.textContent = "登出";
    logoutBtn.addEventListener("click", async function () {
      try {
        await apiFetch("/api/auth/logout", { method: "POST" });
      } catch (e) {
        /* ignore */
      }
      authUser = null;
      cloudSyncEnabled = false;
      cloudFavorites = null;
      clearVocabularyForLogout();
      renderAuthWidget();
    });

    menu.appendChild(logoutBtn);
    wrap.appendChild(trigger);
    wrap.appendChild(menu);
    slot.appendChild(wrap);

    function closeMenu() {
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }

    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = menu.hidden;
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
    });

    document.addEventListener("click", function (e) {
      if (!wrap.contains(e.target)) closeMenu();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeMenu();
    });
  }

  function ensureHeaderRight() {
    var inner = document.querySelector(".site-header__inner");
    if (!inner) return;

    var slot = document.getElementById("ktlHeaderRight");
    if (!slot) {
      slot = document.createElement("div");
      slot.className = "site-header__right";
      slot.id = "ktlHeaderRight";
      inner.appendChild(slot);
    }

    if (!document.getElementById("ktlThemeToggle")) {
      var themeBtn = document.createElement("button");
      themeBtn.type = "button";
      themeBtn.className = "theme-toggle";
      themeBtn.id = "ktlThemeToggle";
      themeBtn.setAttribute("data-theme-toggle", "");
      themeBtn.addEventListener("click", function () {
        if (window.KTL && typeof window.KTL.toggleTheme === "function") {
          window.KTL.toggleTheme();
        }
      });
      slot.appendChild(themeBtn);
      if (window.KTL && typeof window.KTL.getTheme === "function") {
        var isDark = window.KTL.getTheme() === "dark";
        themeBtn.setAttribute("aria-pressed", isDark ? "true" : "false");
        themeBtn.setAttribute("aria-label", isDark ? "切換為淺色模式" : "切換為深色模式");
        themeBtn.title = isDark ? "淺色模式" : "深色模式";
      }
    }

    if (!document.getElementById("ktlAuthSlot")) {
      var authSlot = document.createElement("div");
      authSlot.className = "site-header__auth";
      authSlot.id = "ktlAuthSlot";
      slot.appendChild(authSlot);
    }
  }

  async function initAuth() {
    ensureHeaderRight();
    authUser = null;
    cloudSyncEnabled = false;
    cloudFavorites = null;
    try {
      var res = await apiFetch("/api/auth/me", { method: "GET" });
      if (res.ok) {
        var data = await res.json();
        if (data && data.loggedIn && data.user) {
          authUser = data.user;
          cloudSyncEnabled = !!data.cloudSync;
        }
      }
    } catch (e) {
      /* ignore */
    }
    var justLoggedIn = false;
    try {
      justLoggedIn = new URLSearchParams(window.location.search).get("auth") === "1";
    } catch (e0) {
      /* ignore */
    }
    if (authUser && cloudSyncEnabled) {
      await syncCloudFavorites(justLoggedIn);
    }
    renderAuthWidget();

    var localLevel = getConfirmedDifficulty();
    if (authUser && localLevel) {
      await syncLevelToBackend(localLevel);
    }

    try {
      var params = new URLSearchParams(window.location.search);
      if (params.get("auth") === "1") {
        params.delete("auth");
        var qs = params.toString();
        var nextUrl = window.location.pathname + (qs ? "?" + qs : "") + window.location.hash;
        window.history.replaceState({}, "", nextUrl);
      }
    } catch (e2) {
      /* ignore */
    }
  }

  function setScriptInputPrefill(word) {
    try {
      var value = String(word || "").trim();
      if (value) sessionStorage.setItem(STORAGE_SCRIPT_INPUT_PREFILL_KEY, value);
      else sessionStorage.removeItem(STORAGE_SCRIPT_INPUT_PREFILL_KEY);
    } catch (e) {
      /* ignore */
    }
  }

  function consumeScriptInputPrefill() {
    try {
      var value = sessionStorage.getItem(STORAGE_SCRIPT_INPUT_PREFILL_KEY) || "";
      sessionStorage.removeItem(STORAGE_SCRIPT_INPUT_PREFILL_KEY);
      return value;
    } catch (e) {
      return "";
    }
  }

  function syncDrawerDifficultyChecks() {
    var confirmed = getConfirmedDifficulty();
    var items = document.querySelectorAll(".difficulty-list__item");
    items.forEach(function (li) {
      var d = li.getAttribute("data-d");
      li.classList.toggle("is-confirmed", Boolean(confirmed && d === confirmed));
    });
  }

  function initScriptModeDropdown() {
    var wrap = document.getElementById("scriptModeDropdown");
    if (!wrap) return;
    var btn = document.getElementById("scriptModeDropdownBtn");
    var menu = document.getElementById("scriptModeDropdownMenu");
    if (!btn || !menu) return;

    function close() {
      menu.hidden = true;
      btn.setAttribute("aria-expanded", "false");
    }

    function toggle() {
      var open = menu.hidden;
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
  }

  function initDropdown() {
    var wrap = document.getElementById("libraryDropdown");
    if (!wrap) return;
    var btn = document.getElementById("libraryDropdownBtn");
    var menu = document.getElementById("libraryDropdownMenu");
    if (!btn || !menu) return;

    function close() {
      menu.hidden = true;
      btn.setAttribute("aria-expanded", "false");
    }

    function toggle() {
      var open = menu.hidden;
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
  }

  function resolveConfiguredApiOrigin(raw, currentHost, isLoopback) {
    if (!raw) return "";
    try {
      var u = new URL(String(raw));
      if (isLoopback && (u.hostname === "localhost" || u.hostname === "127.0.0.1")) {
        u.hostname = currentHost;
      }
      return u.origin;
    } catch (e) {
      return String(raw).replace(/\/$/, "");
    }
  }

  function getApiOrigin() {
    var loc = window.location;
    var meta = document.querySelector('meta[name="ktl-api-origin"]');
    var configured =
      resolveConfiguredApiOrigin(
        (meta && meta.getAttribute("content")) || window.KTL_DEFAULT_API_ORIGIN || "",
        loc.hostname,
        loc.hostname === "localhost" || loc.hostname === "127.0.0.1"
      ) || "";
    if (loc.protocol === "file:") {
      return configured || "http://127.0.0.1:5000";
    }
    var h = loc.hostname;
    var isLoopback = h === "localhost" || h === "127.0.0.1";
    /** Flask 同機同埠提供靜態站 + API 時同源，無需跨域 */
    if (isLoopback && loc.port === "5000") {
      return loc.origin;
    }
    if (isLoopback) {
      if (configured) return configured;
      return loc.protocol + "//" + h + ":5000";
    }
    return configured || loc.origin;
  }

  async function syncLevelToBackend(levelZh) {
    if (!levelZh) return false;
    var base = getApiOrigin();
    try {
      var res = await fetch(base + "/api/set-level", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: levelZh, include_entries: false }),
      });
      return res.ok;
    } catch (e) {
      return false;
    }
  }

  function initDrawer() {
    var menuToggle = document.getElementById("menuToggleBtn");
    var fab = document.getElementById("fabMoreBtn");
    var drawer = document.getElementById("drawer");
    var backdrop = document.getElementById("drawerBackdrop");
    var trigger = menuToggle || fab;
    if (!trigger || !drawer || !backdrop) return;

    function openDrawer() {
      drawer.classList.add("is-open");
      drawer.setAttribute("aria-hidden", "false");
      backdrop.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
    }

    function closeDrawer() {
      drawer.classList.remove("is-open");
      drawer.setAttribute("aria-hidden", "true");
      backdrop.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }

    trigger.addEventListener("click", function () {
      if (drawer.classList.contains("is-open")) closeDrawer();
      else openDrawer();
    });

    backdrop.addEventListener("click", closeDrawer);

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !backdrop.hidden) closeDrawer();
    });

    var diffToggle = document.getElementById("difficultyDrawerToggle");
    var diffList = document.getElementById("drawerDifficultyList");
    if (diffToggle && diffList) {
      diffToggle.addEventListener("click", function () {
        var expanded = diffToggle.getAttribute("aria-expanded") === "true";
        diffToggle.setAttribute("aria-expanded", expanded ? "false" : "true");
        diffList.hidden = expanded;
      });
    }
  }

  window.KTL = window.KTL || {};
  window.KTL.STORAGE_DIFFICULTY_KEY = STORAGE_DIFFICULTY_KEY;
  window.KTL.STORAGE_FAVORITES_KEY = STORAGE_FAVORITES_KEY;
  window.KTL.STORAGE_SCRIPT_FAVORITES_KEY = STORAGE_SCRIPT_FAVORITES_KEY;
  window.KTL.getConfirmedDifficulty = getConfirmedDifficulty;
  window.KTL.getFavoriteWordIds = getFavoriteWordIds;
  window.KTL.getScriptFavorites = getScriptFavorites;
  window.KTL.setScriptFavorites = setScriptFavorites;
  window.KTL.addScriptFavorite = addScriptFavorite;
  window.KTL.removeScriptFavorite = removeScriptFavorite;
  window.KTL.isScriptFavoriteWord = isScriptFavoriteWord;
  window.KTL.setScriptInputPrefill = setScriptInputPrefill;
  window.KTL.consumeScriptInputPrefill = consumeScriptInputPrefill;
  window.KTL.setConfirmedDifficulty = function (value) {
    try {
      if (value) localStorage.setItem(STORAGE_DIFFICULTY_KEY, value);
      else localStorage.removeItem(STORAGE_DIFFICULTY_KEY);
    } catch (e) {
      /* ignore */
    }
    syncDrawerDifficultyChecks();
  };
  window.KTL.setFavoriteWordIds = function (ids) {
    try {
      if (!Array.isArray(ids) || ids.length === 0) {
        localStorage.removeItem(STORAGE_FAVORITES_KEY);
        return;
      }
      localStorage.setItem(STORAGE_FAVORITES_KEY, JSON.stringify(ids));
    } catch (e) {
      /* ignore */
    }
  };
  window.KTL.syncDrawerDifficultyChecks = syncDrawerDifficultyChecks;
  window.KTL.assetDataPath = assetDataPath;
  window.KTL.VOCAB_BY_LEVEL = VOCAB_BY_LEVEL;
  window.KTL.getApiOrigin = getApiOrigin;
  window.KTL.apiFetch = apiFetch;
  window.KTL.ensureStudySuffixes = ensureStudySuffixes;
  window.KTL.syncLevelToBackend = syncLevelToBackend;
  window.KTL.isLoggedIn = function () {
    return !!authUser;
  };
  window.KTL.hasCloudSync = function () {
    return !!authUser && cloudSyncEnabled;
  };
  window.KTL.getAuthUser = function () {
    return authUser;
  };
  window.KTL.refreshAuth = initAuth;

  document.addEventListener("DOMContentLoaded", function () {
    initDropdown();
    initScriptModeDropdown();
    initDrawer();
    syncDrawerDifficultyChecks();
    initAuth();
    ensureStudySuffixes();
  });
})();
