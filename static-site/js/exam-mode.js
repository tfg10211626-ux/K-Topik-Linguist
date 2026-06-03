(function () {

  var VOCAB_QUESTION_BANK = [
    {
      prompt: "下列何者最接近「감사하다」的意思？",
      options: ["擔心", "感謝", "等待", "比較"],
      answer: 1,
    },
    {
      prompt: "下列何者最接近「약속」的意思？",
      options: ["約定", "習慣", "地點", "聲音"],
      answer: 0,
    },
    {
      prompt: "下列何者最接近「도서관」的意思？",
      options: ["教室", "餐廳", "圖書館", "醫院"],
      answer: 2,
    },
    {
      prompt: "下列何者最接近「필요하다」的意思？",
      options: ["需要", "結束", "借用", "相信"],
      answer: 0,
    },
    {
      prompt: "下列何者最接近「빠르다」的意思？",
      options: ["昂貴", "緩慢", "快速", "乾淨"],
      answer: 2,
    },
    {
      prompt: "下列何者最接近「조용하다」的意思？",
      options: ["安靜", "熱鬧", "寒冷", "忙碌"],
      answer: 0,
    },
    {
      prompt: "下列何者最接近「지하철」的意思？",
      options: ["公車", "計程車", "地鐵", "飛機"],
      answer: 2,
    },
    {
      prompt: "下列何者最接近「준비하다」的意思？",
      options: ["休息", "準備", "離開", "回家"],
      answer: 1,
    },
    {
      prompt: "下列何者最接近「시장」的意思？",
      options: ["市場", "校長", "機場", "船長"],
      answer: 0,
    },
    {
      prompt: "下列何者最接近「연습」的意思？",
      options: ["休假", "搬家", "練習", "參觀"],
      answer: 2,
    },
  ];

  var GRAMMAR_QUESTION_BANK = [
    {
      prompt: "請選出最自然的一句：저는 친구__ 영화를 봤어요.",
      options: ["와", "를", "에서", "보다"],
      answer: 0,
    },
    {
      prompt: "請選出最自然的一句：비가 오__ 우산을 가져가세요.",
      options: ["는데", "니까", "보다", "처럼"],
      answer: 1,
    },
    {
      prompt: "請選出最自然的一句：오늘은 어제__ 덜 추워요.",
      options: ["마다", "처럼", "보다", "까지"],
      answer: 2,
    },
    {
      prompt: "請選出最自然的一句：숙제를 다 한 __ 텔레비전을 봤어요.",
      options: ["부터", "후에", "만큼", "보다"],
      answer: 1,
    },
    {
      prompt: "請選出最自然的一句：한국어를 잘하고 싶어서 매일 __.",
      options: ["연습해요", "연습이에요", "연습보다", "연습부터"],
      answer: 0,
    },
    {
      prompt: "請選出最自然的一句：시간이 없__ 택시를 탔어요.",
      options: ["고", "는데", "어서", "마다"],
      answer: 2,
    },
    {
      prompt: "請選出最自然的一句：주말에는 집에서 푹 __ 싶어요.",
      options: ["쉬고", "쉬는", "쉬다", "쉬어서"],
      answer: 0,
    },
    {
      prompt: "請選出最自然的一句：이 책은 생각보다 __ 읽어요.",
      options: ["쉽게", "쉽다", "쉬운", "쉬어서"],
      answer: 0,
    },
    {
      prompt: "請選出最自然的一句：수업이 끝나면 바로 집에 __ 거예요.",
      options: ["가요", "가고", "갈", "가서"],
      answer: 2,
    },
    {
      prompt: "請選出最自然的一句：내일 시험이 있어서 오늘은 일찍 __.",
      options: ["자요", "잘", "자는", "자서"],
      answer: 0,
    },
  ];

  function shuffleArray(list) {
    var copy = list.slice();
    var i;
    var j;
    var temp;
    for (i = copy.length - 1; i > 0; i -= 1) {
      j = Math.floor(Math.random() * (i + 1));
      temp = copy[i];
      copy[i] = copy[j];
      copy[j] = temp;
    }
    return copy;
  }

  function getQuestionBank(type) {
    if (type === "grammar") return GRAMMAR_QUESTION_BANK;
    if (type === "mixed") {
      var mixed = [];
      var maxLength = Math.max(VOCAB_QUESTION_BANK.length, GRAMMAR_QUESTION_BANK.length);
      var i;
      for (i = 0; i < maxLength; i += 1) {
        if (VOCAB_QUESTION_BANK[i]) mixed.push(VOCAB_QUESTION_BANK[i]);
        if (GRAMMAR_QUESTION_BANK[i]) mixed.push(GRAMMAR_QUESTION_BANK[i]);
      }
      return mixed;
    }
    return VOCAB_QUESTION_BANK;
  }

  function buildMockExamQuestions(selection) {
    var bank = shuffleArray(getQuestionBank(selection.type));
    var questions = [];
    var i;
    for (i = 0; i < selection.count; i += 1) {
      var template = bank[i % bank.length];
      var round = Math.floor(i / bank.length);
      questions.push({
        id: selection.type + "-" + (i + 1),
        prompt: round > 0 ? template.prompt + "（模擬題 " + (round + 1) + "）" : template.prompt,
        options: template.options.slice(),
        answer: template.answer,
      });
    }
    return questions;
  }

  async function requestExamQuestions(selection) {
    var level = selection && selection.level ? String(selection.level).trim() : "";
    if (!level || level === "初級") {
      return buildMockExamQuestions(selection);
    }

    var base =
      window.KTL && typeof window.KTL.getApiOrigin === "function" ? window.KTL.getApiOrigin() : "";
    var response;
    var payload;

    try {
      response = await fetch(base + "/api/modes/exam/questions", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          level: level,
          question_type: selection.type,
          count: selection.count,
        }),
      });
    } catch (error) {
      throw new Error("考題 API 連線失敗，請稍後再試。");
    }

    try {
      payload = await response.json();
    } catch (error2) {
      payload = {};
    }

    if (!response.ok) {
      throw new Error(payload && payload.error ? payload.error : "考題產生失敗，請稍後再試。");
    }
    if (!payload || !Array.isArray(payload.questions)) {
      throw new Error("考題格式錯誤，請稍後再試。");
    }
    return payload.questions;
  }

  function appendPromptSegment(target, text) {
    String(text || "")
      .split("\n")
      .forEach(function (part, index) {
        if (index > 0) target.appendChild(document.createElement("br"));
        if (part) target.appendChild(document.createTextNode(part));
      });
  }

  function renderQuestionPrompt(target, rawPrompt) {
    var text = String(rawPrompt || "");
    var re = /<u>([\s\S]*?)<\/u>/gi;
    var lastIndex = 0;
    var match;

    while ((match = re.exec(text))) {
      appendPromptSegment(target, text.slice(lastIndex, match.index));
      var underline = document.createElement("u");
      underline.textContent = match[1];
      target.appendChild(underline);
      lastIndex = match.index + match[0].length;
    }

    appendPromptSegment(target, text.slice(lastIndex));
  }

  function createQuestionCard(question, index, state) {
    var card = document.createElement("article");
    card.className = "exam-question-card";
    var selectedAnswer = state.answers[question.id];
    var isIncorrect = state.submitted && selectedAnswer !== question.answer;
    if (isIncorrect) {
      card.classList.add("is-incorrect");
    }

    var indexText = document.createElement("p");
    indexText.className = "exam-question-card__index";
    indexText.textContent = "Question " + String(index + 1).padStart(2, "0");

    var prompt = document.createElement("h2");
    prompt.className = "exam-question-card__prompt";
    renderQuestionPrompt(prompt, question.prompt);

    var options = document.createElement("div");
    options.className = "exam-option-list";

    question.options.forEach(function (optionText, optionIndex) {
      var label = document.createElement("label");
      label.className = "exam-option";
      if (isIncorrect && optionIndex === selectedAnswer) {
        label.classList.add("is-incorrect-choice");
      }

      var input = document.createElement("input");
      input.type = "radio";
      input.name = "exam-question-" + question.id;
      input.value = String(optionIndex);
      input.checked = selectedAnswer === optionIndex;
      input.disabled = state.submitted;

      input.addEventListener("change", function () {
        state.answers[question.id] = optionIndex;
        state.renderActions();
      });

      var marker = document.createElement("span");
      marker.className = "exam-option__marker";
      marker.textContent = String.fromCharCode(65 + optionIndex);

      var text = document.createElement("span");
      text.className = "exam-option__text";
      text.textContent = optionText;

      label.appendChild(input);
      label.appendChild(marker);
      label.appendChild(text);
      options.appendChild(label);
    });

    card.appendChild(indexText);
    card.appendChild(prompt);
    card.appendChild(options);
    if (isIncorrect) {
      var answerText = String.fromCharCode(65 + question.answer) + ". " + question.options[question.answer];
      var answerNote = document.createElement("p");
      answerNote.className = "exam-question-card__answer";
      answerNote.textContent = "正確答案：" + answerText;
      card.appendChild(answerNote);
    }

    return card;
  }

  function createButton(label, className, onClick, disabled) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.disabled = !!disabled;
    button.addEventListener("click", onClick);
    return button;
  }

  function createHomeButton() {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "exam-action-btn exam-action-btn--home";
    button.setAttribute("aria-label", "回首頁");
    button.innerHTML =
      '<span class="exam-home-icon" aria-hidden="true">' +
      '<svg viewBox="0 0 24 24" width="18" height="18" focusable="false">' +
      '<path d="M4 10.5L12 4l8 6.5V20h-5.25v-5.5h-5.5V20H4z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>' +
      "</svg>" +
      "</span>" +
      "<span>回首頁</span>";
    button.addEventListener("click", function () {
      window.location.href = "index.html";
    });
    return button;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var examTypeGroup = document.getElementById("examTypeGroup");
    var startBtn = document.getElementById("examStartBtn");
    var backBtn = document.getElementById("examBackBtn");
    var setupCard = document.getElementById("examSetupCard");
    var sessionEl = document.getElementById("examSession");
    var questionListEl = document.getElementById("examQuestionList");
    var actionsEl = document.getElementById("examActions");
    var resultCardEl = document.getElementById("examResultCard");
    var wrongCountEl = document.getElementById("examWrongCount");
    var totalScoreEl = document.getElementById("examTotalScore");

    if (
      !examTypeGroup ||
      !startBtn ||
      !setupCard ||
      !sessionEl ||
      !questionListEl ||
      !actionsEl ||
      !resultCardEl ||
      !wrongCountEl ||
      !totalScoreEl
    ) {
      return;
    }

    var state = {
      selection: {
        type: "vocabulary",
        count: 10,
        level:
          window.KTL && typeof window.KTL.getConfirmedDifficulty === "function"
            ? window.KTL.getConfirmedDifficulty()
            : "",
      },
      questions: [],
      answers: {},
      submitted: false,
      renderActions: function () {},
    };

    function getSelectedCount() {
      var checked = document.querySelector('input[name="examQuestionCount"]:checked');
      var count = checked ? parseInt(checked.value, 10) : 10;
      return isNaN(count) ? 10 : count;
    }

    function setSelectedType(nextType) {
      state.selection.type = nextType || "vocabulary";
      examTypeGroup.querySelectorAll("[data-exam-type]").forEach(function (button) {
        button.classList.toggle("is-selected", button.getAttribute("data-exam-type") === state.selection.type);
      });
    }

    function renderQuestions() {
      questionListEl.innerHTML = "";
      state.questions.forEach(function (question, index) {
        questionListEl.appendChild(createQuestionCard(question, index, state));
      });
    }

    function getAnsweredCount() {
      return Object.keys(state.answers).length;
    }

    function isReadyToSubmit() {
      return state.questions.length > 0 && getAnsweredCount() === state.questions.length;
    }

    function renderActiveActions() {
      actionsEl.innerHTML = "";
      actionsEl.appendChild(
        createButton(
          "Submit",
          "exam-action-btn exam-action-btn--primary",
          submitExam,
          !isReadyToSubmit()
        )
      );
      actionsEl.appendChild(
        createButton("返回", "exam-action-btn exam-action-btn--secondary", resetToSetup)
      );
      actionsEl.appendChild(createHomeButton());
    }

    function renderResultActions() {
      actionsEl.innerHTML = "";
      actionsEl.appendChild(
        createButton("再試一次", "exam-action-btn exam-action-btn--primary", retrySameQuestions)
      );
      actionsEl.appendChild(
        createButton("重新設定", "exam-action-btn exam-action-btn--primary", resetToSetup)
      );
      actionsEl.appendChild(createHomeButton());
    }

    state.renderActions = function () {
      if (state.submitted) renderResultActions();
      else renderActiveActions();
    };

    async function startExam(nextSelection) {
      var selection = nextSelection || {
        type: state.selection.type,
        count: getSelectedCount(),
        level:
          window.KTL && typeof window.KTL.getConfirmedDifficulty === "function"
            ? window.KTL.getConfirmedDifficulty()
            : "",
      };

      startBtn.disabled = true;
      startBtn.textContent = "載入題目中...";
      try {
        state.selection = {
          type: selection.type,
          count: selection.count,
          level: selection.level || "",
        };
        state.questions = await requestExamQuestions(state.selection);
        state.answers = {};
        state.submitted = false;

        setupCard.hidden = true;
        sessionEl.hidden = false;
        resultCardEl.hidden = true;
        wrongCountEl.textContent = "0 題";
        totalScoreEl.textContent = "0 分";

        renderQuestions();
        state.renderActions();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (error) {
        window.alert(error && error.message ? error.message : "考題載入失敗，請稍後再試。");
      } finally {
        startBtn.disabled = false;
        startBtn.textContent = "確認，開始考試";
      }
    }

    function submitExam() {
      if (!isReadyToSubmit()) return;

      var wrongCount = 0;
      state.questions.forEach(function (question) {
        if (state.answers[question.id] !== question.answer) wrongCount += 1;
      });

      state.submitted = true;
      wrongCountEl.textContent = wrongCount + " 題";
      totalScoreEl.textContent =
        Math.round(((state.questions.length - wrongCount) / state.questions.length) * 100) + " 分";
      resultCardEl.hidden = false;

      renderQuestions();
      state.renderActions();
      resultCardEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function retrySameQuestions() {
      if (!state.questions.length) return;

      state.answers = {};
      state.submitted = false;
      resultCardEl.hidden = true;
      wrongCountEl.textContent = "0 題";
      totalScoreEl.textContent = "0 分";

      renderQuestions();
      state.renderActions();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function resetToSetup() {
      state.questions = [];
      state.answers = {};
      state.submitted = false;
      questionListEl.innerHTML = "";
      resultCardEl.hidden = true;
      sessionEl.hidden = true;
      setupCard.hidden = false;
      startBtn.disabled = false;
      startBtn.textContent = "確認，開始考試";
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    examTypeGroup.addEventListener("click", function (event) {
      var button = event.target.closest("[data-exam-type]");
      if (!button) return;
      setSelectedType(button.getAttribute("data-exam-type"));
    });

    startBtn.addEventListener("click", function () {
      startExam();
    });

    if (backBtn) {
      backBtn.addEventListener("click", function () {
        if (window.KTL && typeof window.KTL.setConfirmedDifficulty === "function") {
          window.KTL.setConfirmedDifficulty("");
        }
        window.location.href = "index.html";
      });
    }

    setSelectedType(state.selection.type);
    state.renderActions();
  });
})();
