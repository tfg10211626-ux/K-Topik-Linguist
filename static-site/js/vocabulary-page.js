(function () {
  var state = {
    selectMode: false,
    selectedWords: {},
    pendingDeleteWords: [],
  };

  var openMenuRef = null;

  function getFavorites() {
    if (!window.KTL || typeof window.KTL.getScriptFavorites !== "function") return [];
    return window.KTL.getScriptFavorites().filter(function (entry) {
      return entry && entry.word;
    });
  }

  function setFavorites(entries) {
    if (!window.KTL || typeof window.KTL.setScriptFavorites !== "function") return;
    window.KTL.setScriptFavorites(entries);
  }

  function closeOpenMenu() {
    if (!openMenuRef) return;
    openMenuRef.menu.hidden = true;
    openMenuRef.button.setAttribute("aria-expanded", "false");
    openMenuRef = null;
  }

  function openMenu(menuEl, buttonEl) {
    if (!menuEl || !buttonEl) return;
    if (openMenuRef && openMenuRef.menu === menuEl) {
      closeOpenMenu();
      return;
    }
    closeOpenMenu();
    menuEl.hidden = false;
    buttonEl.setAttribute("aria-expanded", "true");
    openMenuRef = { menu: menuEl, button: buttonEl };
  }

  function uniqueWords(words) {
    var seen = {};
    return (words || []).filter(function (word) {
      var value = String(word || "").trim();
      if (!value || seen[value]) return false;
      seen[value] = true;
      return true;
    });
  }

  function getSelectedWords() {
    return Object.keys(state.selectedWords).filter(function (word) {
      return !!state.selectedWords[word];
    });
  }

  function syncSelectedWords(items) {
    var allowed = {};
    items.forEach(function (entry) {
      allowed[entry.word] = true;
    });
    Object.keys(state.selectedWords).forEach(function (word) {
      if (!allowed[word]) delete state.selectedWords[word];
    });
  }

  function updateToolbar(items) {
    var selectBtn = document.getElementById("vocabSelectModeBtn");
    var selectionActions = document.getElementById("vocabSelectionActions");
    var selectAllBtn = document.getElementById("vocabSelectAllBtn");
    var bulkDeleteBtn = document.getElementById("vocabBulkDeleteBtn");
    var hasItems = !!(items && items.length);
    var selectedCount = getSelectedWords().length;
    var hasSelected = selectedCount > 0;
    var allSelected = hasItems && selectedCount === items.length;

    if (selectBtn) {
      selectBtn.disabled = !hasItems;
      selectBtn.hidden = state.selectMode;
    }
    if (selectionActions) {
      selectionActions.hidden = !state.selectMode;
    }
    if (selectAllBtn) {
      selectAllBtn.disabled = !hasItems || allSelected;
    }
    if (bulkDeleteBtn) {
      bulkDeleteBtn.disabled = !hasSelected;
    }
  }

  function exitSelectionMode() {
    state.selectMode = false;
    state.selectedWords = {};
    closeOpenMenu();
    renderScriptFavorites();
  }

  function enterSelectionMode() {
    state.selectMode = true;
    closeOpenMenu();
    renderScriptFavorites();
  }

  function selectAllWords(items) {
    (items || []).forEach(function (entry) {
      state.selectedWords[entry.word] = true;
    });
    renderScriptFavorites();
  }

  function goToScriptMode(word) {
    var value = String(word || "").trim();
    if (!value) return;
    if (window.KTL && typeof window.KTL.setScriptInputPrefill === "function") {
      window.KTL.setScriptInputPrefill(value);
    }
    window.location.href = "script.html";
  }

  function deleteWords(words) {
    var removeTargets = uniqueWords(words);
    if (!removeTargets.length) return;
    var removeMap = {};
    removeTargets.forEach(function (word) {
      removeMap[word] = true;
      delete state.selectedWords[word];
    });
    var next = getFavorites().filter(function (entry) {
      return !removeMap[entry.word];
    });
    if (!next.length) {
      state.selectMode = false;
    }
    setFavorites(next);
    closeOpenMenu();
    renderScriptFavorites();
  }

  function confirmDeletePending() {
    var dialogEl = document.getElementById("vocabDeleteDialog");
    var words = state.pendingDeleteWords.slice();
    state.pendingDeleteWords = [];
    if (dialogEl && dialogEl.open && typeof dialogEl.close === "function") {
      dialogEl.close();
    }
    deleteWords(words);
  }

  function openDeleteDialog(words) {
    var dialogEl = document.getElementById("vocabDeleteDialog");
    var textEl = document.getElementById("vocabDeleteDialogText");
    var targets = uniqueWords(words);
    if (!targets.length) return;
    state.pendingDeleteWords = targets;
    if (textEl) {
      textEl.textContent =
        targets.length > 1
          ? "刪除後將會從單字庫移除這 " + targets.length + " 個單字。"
          : "刪除後將會從單字庫移除這個單字。";
    }
    if (dialogEl && typeof dialogEl.showModal === "function") {
      dialogEl.showModal();
      return;
    }
    if (window.confirm(textEl ? textEl.textContent : "是否確認刪除")) {
      confirmDeletePending();
    } else {
      state.pendingDeleteWords = [];
    }
  }

  function createHeartButton(word) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "chat-favorite-btn vocab-library-card__icon-btn";
    button.setAttribute("aria-pressed", "true");
    button.setAttribute("aria-label", "從單字庫移除");
    button.innerHTML =
      '<svg class="chat-favorite-icon chat-favorite-icon--outline" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
      '<path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>' +
      "</svg>" +
      '<svg class="chat-favorite-icon chat-favorite-icon--fill" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>' +
      "</svg>";
    button.addEventListener("click", function () {
      deleteWords([word]);
    });
    return button;
  }

  function createMoreMenu(word) {
    var wrap = document.createElement("div");
    wrap.className = "vocab-card-menu";

    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "vocab-card-menu__trigger vocab-library-card__icon-btn";
    trigger.setAttribute("aria-label", "更多選單");
    trigger.setAttribute("aria-haspopup", "menu");
    trigger.setAttribute("aria-expanded", "false");
    trigger.innerHTML =
      '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">' +
      '<circle cx="5" cy="12" r="1.7" fill="currentColor"></circle>' +
      '<circle cx="12" cy="12" r="1.7" fill="currentColor"></circle>' +
      '<circle cx="19" cy="12" r="1.7" fill="currentColor"></circle>' +
      "</svg>";

    var menu = document.createElement("div");
    menu.className = "vocab-card-menu__menu";
    menu.setAttribute("role", "menu");
    menu.hidden = true;

    var deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "vocab-card-menu__item";
    deleteBtn.textContent = "刪除";
    deleteBtn.addEventListener("click", function () {
      closeOpenMenu();
      openDeleteDialog([word]);
    });

    var scriptBtn = document.createElement("button");
    scriptBtn.type = "button";
    scriptBtn.className = "vocab-card-menu__item";
    scriptBtn.textContent = "劇本模式";
    scriptBtn.addEventListener("click", function () {
      closeOpenMenu();
      goToScriptMode(word);
    });

    trigger.addEventListener("click", function (event) {
      event.stopPropagation();
      openMenu(menu, trigger);
    });

    menu.appendChild(deleteBtn);
    menu.appendChild(scriptBtn);
    wrap.appendChild(trigger);
    wrap.appendChild(menu);
    return wrap;
  }

  function createVocabCard(entry) {
    var item = document.createElement("li");
    item.className = "vocab-library-card";
    item.dataset.word = entry.word;

    var selection = document.createElement("label");
    selection.className = "vocab-library-card__selection";
    selection.hidden = !state.selectMode;

    var checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "vocab-library-card__checkbox";
    checkbox.checked = !!state.selectedWords[entry.word];
    checkbox.setAttribute("aria-label", "選取 " + entry.word);
    checkbox.addEventListener("change", function () {
      state.selectedWords[entry.word] = checkbox.checked;
      item.classList.toggle("is-selected", checkbox.checked);
      updateToolbar(getFavorites());
    });

    selection.appendChild(checkbox);

    var main = document.createElement("div");
    main.className = "vocab-library-card__main";

    var titleRowEl = document.createElement("div");
    titleRowEl.className = "vocab-library-card__title-row";

    var wordEl = document.createElement("strong");
    wordEl.className = "vocab-library-card__word";
    wordEl.textContent = entry.word;

    var meaningEl = document.createElement("p");
    meaningEl.className = "vocab-library-card__meaning";
    meaningEl.textContent = entry.meaningZh || "—";

    var sentenceEl = document.createElement("p");
    sentenceEl.className = "vocab-library-card__sentence";
    sentenceEl.textContent = entry.dramaLineKo || "";

    titleRowEl.appendChild(wordEl);
    titleRowEl.appendChild(meaningEl);
    main.appendChild(titleRowEl);
    main.appendChild(sentenceEl);

    var actions = document.createElement("div");
    actions.className = "vocab-library-card__actions";
    actions.appendChild(createHeartButton(entry.word));
    actions.appendChild(createMoreMenu(entry.word));

    item.appendChild(selection);
    item.appendChild(main);
    item.appendChild(actions);
    item.classList.toggle("is-selected", checkbox.checked);
    return item;
  }

  function renderScriptFavorites() {
    var mount = document.getElementById("vocabScriptFavoritesMount");
    if (!mount) return;
    closeOpenMenu();

    var items = getFavorites();
    if (!items.length) {
      state.selectMode = false;
      state.selectedWords = {};
    }
    syncSelectedWords(items);
    mount.innerHTML = "";
    updateToolbar(items);

    if (!items.length) {
      var empty = document.createElement("p");
      empty.className = "vocab-library-empty";
      empty.textContent = "尚無收藏單字。";
      mount.appendChild(empty);
      return;
    }

    var list = document.createElement("ul");
    list.className = "vocab-library-list";
    items.forEach(function (entry) {
      list.appendChild(createVocabCard(entry));
    });
    mount.appendChild(list);
  }

  function initDifficultySidebar() {
    var toggleBtn = document.getElementById("vocabDifficultyToggle");
    var listEl = document.getElementById("vocabDifficultyList");

    if (toggleBtn && listEl) {
      toggleBtn.addEventListener("click", function () {
        var expanded = toggleBtn.getAttribute("aria-expanded") === "true";
        toggleBtn.setAttribute("aria-expanded", expanded ? "false" : "true");
        listEl.hidden = expanded;
      });
    }

    if (listEl) {
      listEl.addEventListener("click", function (event) {
        var item = event.target.closest(".difficulty-list__item");
        if (!item) return;
        var value = String(item.getAttribute("data-d") || "").trim();
        if (!value || !window.KTL) return;
        if (typeof window.KTL.setConfirmedDifficulty === "function") {
          window.KTL.setConfirmedDifficulty(value);
        }
        if (typeof window.KTL.syncLevelToBackend === "function") {
          window.KTL.syncLevelToBackend(value);
        }
      });
    }

    if (window.KTL && typeof window.KTL.syncDrawerDifficultyChecks === "function") {
      window.KTL.syncDrawerDifficultyChecks();
    }
  }

  function initToolbar() {
    var selectBtn = document.getElementById("vocabSelectModeBtn");
    var selectAllBtn = document.getElementById("vocabSelectAllBtn");
    var cancelBtn = document.getElementById("vocabCancelSelectionBtn");
    var bulkDeleteBtn = document.getElementById("vocabBulkDeleteBtn");

    if (selectBtn) {
      selectBtn.addEventListener("click", function () {
        if (state.selectMode) return;
        enterSelectionMode();
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        exitSelectionMode();
      });
    }

    if (selectAllBtn) {
      selectAllBtn.addEventListener("click", function () {
        selectAllWords(getFavorites());
      });
    }

    if (bulkDeleteBtn) {
      bulkDeleteBtn.addEventListener("click", function () {
        openDeleteDialog(getSelectedWords());
      });
    }
  }

  function initDeleteDialog() {
    var dialogEl = document.getElementById("vocabDeleteDialog");
    var confirmBtn = document.getElementById("vocabDeleteConfirmBtn");
    var cancelBtn = document.getElementById("vocabDeleteCancelBtn");

    if (confirmBtn) {
      confirmBtn.addEventListener("click", function () {
        confirmDeletePending();
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        state.pendingDeleteWords = [];
        if (dialogEl && dialogEl.open && typeof dialogEl.close === "function") dialogEl.close();
      });
    }

    if (dialogEl) {
      dialogEl.addEventListener("cancel", function () {
        state.pendingDeleteWords = [];
      });
      dialogEl.addEventListener("click", function (event) {
        if (event.target === dialogEl && typeof dialogEl.close === "function") {
          state.pendingDeleteWords = [];
          dialogEl.close();
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initDifficultySidebar();
    initToolbar();
    initDeleteDialog();
    renderScriptFavorites();

    document.addEventListener("click", function (event) {
      if (!event.target.closest(".vocab-card-menu")) {
        closeOpenMenu();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeOpenMenu();
    });

    window.addEventListener("ktl-script-favorites-changed", renderScriptFavorites);
  });
})();
