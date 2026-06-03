(function () {
  var MODE_HREF = {
    script: "script.html",
    study: "study.html",
    exam: "exam.html",
  };

  document.addEventListener("DOMContentLoaded", function () {
    var stepDiff = document.getElementById("stepDifficulty");
    var stepMode = document.getElementById("stepMode");
    var confirmDiffBtn = document.getElementById("confirmDifficultyBtn");
    var backBtn = document.getElementById("backToDifficultyBtn");
    var startBtn = document.getElementById("startLearningBtn");
    if (!stepDiff || !stepMode || !confirmDiffBtn || !startBtn) return;

    var selectedDifficulty = "";
    var selectedMode = "";

    var diffButtons = stepDiff.querySelectorAll("[data-difficulty]");
    var modeButtons = stepMode.querySelectorAll("[data-mode]");

    function setGroupSelection(buttons, attr, value) {
      buttons.forEach(function (btn) {
        btn.classList.toggle("is-selected", btn.getAttribute(attr) === value);
      });
    }

    diffButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectedDifficulty = btn.getAttribute("data-difficulty") || "";
        setGroupSelection(diffButtons, "data-difficulty", selectedDifficulty);
        confirmDiffBtn.disabled = !selectedDifficulty;
      });
    });

    modeButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectedMode = btn.getAttribute("data-mode") || "";
        setGroupSelection(modeButtons, "data-mode", selectedMode);
        startBtn.disabled = !selectedMode;
      });
    });

    confirmDiffBtn.addEventListener("click", async function () {
      if (!selectedDifficulty) return;
      if (window.KTL && typeof window.KTL.setConfirmedDifficulty === "function") {
        window.KTL.setConfirmedDifficulty(selectedDifficulty);
      }
      if (window.KTL && typeof window.KTL.syncLevelToBackend === "function") {
        await window.KTL.syncLevelToBackend(selectedDifficulty);
      }
      stepDiff.hidden = true;
      stepMode.hidden = false;
    });

    if (backBtn) {
      backBtn.addEventListener("click", function () {
        stepMode.hidden = true;
        stepDiff.hidden = false;
        selectedMode = "";
        setGroupSelection(modeButtons, "data-mode", "");
        startBtn.disabled = true;
      });
    }

    startBtn.addEventListener("click", async function () {
      if (!selectedMode || !selectedDifficulty) return;
      var href = MODE_HREF[selectedMode];
      if (!href) return;
      if (window.KTL && typeof window.KTL.syncLevelToBackend === "function") {
        var ok = await window.KTL.syncLevelToBackend(selectedDifficulty);
        if (!ok) {
          window.alert(
            "無法連線後端。請先在 backend 目錄啟動 Flask（port 5000），再從 Flask 網址或對應代理網址開站，不要只開 Live Server。"
          );
          return;
        }
      }
      window.location.href = href;
    });
  });
})();
