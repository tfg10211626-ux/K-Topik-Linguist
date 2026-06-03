(function () {
  var STORAGE_THEME_KEY = "ktopik:theme";

  function getStoredTheme() {
    try {
      var value = localStorage.getItem(STORAGE_THEME_KEY);
      return value === "dark" ? "dark" : "light";
    } catch (e) {
      return "light";
    }
  }

  function applyTheme(theme) {
    var next = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(STORAGE_THEME_KEY, next);
    } catch (e2) {
      /* ignore */
    }
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      var isDark = next === "dark";
      btn.setAttribute("aria-pressed", isDark ? "true" : "false");
      btn.setAttribute("aria-label", isDark ? "切換為淺色模式" : "切換為深色模式");
      btn.title = isDark ? "淺色模式" : "深色模式";
    });
    try {
      window.dispatchEvent(
        new CustomEvent("ktl-theme-changed", { detail: { theme: next } })
      );
    } catch (e3) {
      /* ignore */
    }
  }

  applyTheme(getStoredTheme());

  window.KTL = window.KTL || {};
  window.KTL.getTheme = getStoredTheme;
  window.KTL.setTheme = applyTheme;
  window.KTL.toggleTheme = function () {
    applyTheme(getStoredTheme() === "dark" ? "light" : "dark");
  };
})();
