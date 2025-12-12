// static/js/cabinet-home.js
document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  // ====== DOM ======
  const trackAddForm = document.getElementById("trackAddForm");
  const trackAddInputsContainer = document.getElementById("trackAddInputs");
  const trackResetBtn = document.getElementById("trackResetBtn");

  const statusCards = document.querySelectorAll(".status-card");
  const trackListWrapper = document.getElementById("trackListWrapper");

  const statusModal = document.getElementById("statusModal");
  const statusModalTitle = document.getElementById("statusModalTitle");
  const statusModalBody = document.getElementById("statusModalBody");

  const historyModal = document.getElementById("historyModal");
  const historyModalTitle = document.getElementById("historyModalTitle");
  const historyTimeline = document.getElementById("historyTimeline");

  const trackSearchForm = document.getElementById("trackSearchForm");
  const trackSearchInput = document.getElementById("trackSearchInput");
  const trackSearchError = document.getElementById("trackSearchError"); // (если есть в HTML)

  // ====== UTILS ======
  function openModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add("hidden");
    document.body.style.overflow = "";
  }

  function setSearchMsg(text) {
    if (!trackSearchError) return;
    if (!text) {
      trackSearchError.style.display = "none";
      trackSearchError.textContent = "";
      return;
    }
    trackSearchError.style.display = "block";
    trackSearchError.textContent = text;
  }

  function cleanTrack(v) {
    return (v || "").trim().replace(/\s+/g, "").slice(0, 20);
  }

  function statusLabel(status) {
    switch (Number(status)) {
      case 0:
        return "Ожидает поступления на склад в Китае";
      case 1:
        return "Принят на склад в Китае";
      case 2:
        return "Отправлен из Китая";
      case 3:
        return "Прибыл в пункт выдачи";
      case 4:
        return "Получен";
      default:
        return "Неизвестный статус";
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // ====== ДИНАМИЧЕСКИЕ ПОЛЯ ДЛЯ ТРЕКОВ (до 5 штук) ======
  function attachDynamicInputs() {
    if (!trackAddInputsContainer) return;

    const MAX_INPUTS = 5;

    function updateResetVisibility() {
      if (!trackResetBtn) return;
      const inputs = Array.from(
        trackAddInputsContainer.querySelectorAll("input[name='tracks']")
      );
      const hasValue = inputs.some((inp) => inp.value.trim().length > 0);
      trackResetBtn.style.display = hasValue ? "inline-block" : "none";
    }

    function onInputChange() {
      const inputs = Array.from(
        trackAddInputsContainer.querySelectorAll("input[name='tracks']")
      );
      if (!inputs.length) return;

      updateResetVisibility();

      if (inputs.length >= MAX_INPUTS) return;

      const last = inputs[inputs.length - 1];

      // создаём следующее поле только когда в последнем хотя бы 3 символа
      if (last && last.value.trim().length >= 3) {
        const hasEmptyAtEnd =
          inputs.length > 1 &&
          inputs[inputs.length - 1].value.trim() === "" &&
          inputs[inputs.length - 2].value.trim() === "";

        if (hasEmptyAtEnd) return;

        const input = document.createElement("input");
        input.name = "tracks";
        input.type = "text";
        input.className = "input";
        input.placeholder = "Трек-номер";
        input.maxLength = 20;
        input.addEventListener("input", onInputChange);
        trackAddInputsContainer.appendChild(input);
      }
    }

    // навешиваем слушатель на существующее первое поле
    const firstInput = trackAddInputsContainer.querySelector(
      "input[name='tracks']"
    );
    if (firstInput) firstInput.addEventListener("input", onInputChange);

    // обработчик кнопки сброса
    if (trackResetBtn) {
      trackResetBtn.addEventListener("click", (e) => {
        e.preventDefault();

        // очищаем контейнер и создаём одно пустое поле
        trackAddInputsContainer.innerHTML = "";

        const input = document.createElement("input");
        input.name = "tracks";
        input.type = "text";
        input.className = "input";
        input.placeholder = "Трек-номер";
        input.maxLength = 20;
        input.addEventListener("input", onInputChange);
        trackAddInputsContainer.appendChild(input);

        trackResetBtn.style.display = "none";
      });

      trackResetBtn.style.display = "none";
    }
  }

  attachDynamicInputs();

  // перед отправкой формы чистим пробелы
  if (trackAddForm && trackAddInputsContainer) {
    trackAddForm.addEventListener("submit", () => {
      const inputs = Array.from(
        trackAddInputsContainer.querySelectorAll("input[name='tracks']")
      );
      inputs.forEach((inp) => {
        inp.value = inp.value.trim().replace(/\s+/g, "");
      });
    });
  }

  // ====== МОДАЛКА СО СПИСКОМ ПО СТАТУСУ ======
  function openStatusModal(status) {
    if (!trackListWrapper || !statusModalBody || !statusModalTitle) return;

    const allParcels = Array.from(
      trackListWrapper.querySelectorAll(".track-item")
    );

    const filtered = allParcels.filter(
      (item) => String(item.dataset.status) === String(status)
    );

    statusModalBody.innerHTML = "";

    if (!filtered.length) {
      statusModalBody.innerHTML = `
        <div class="empty-state">
          <div class="empty-state__icon">📭</div>
          <p>Посылок с таким статусом пока нет.</p>
        </div>
      `;
    } else {
      const list = document.createElement("div");
      list.className = "track-list";

      filtered.forEach((item) => {
        const trackNumber =
          item.querySelector(".track-item__number")?.textContent?.trim() || "";
        const statusText =
          item.querySelector(".track-item__status")?.textContent?.trim() || "";
        const historyUrl = item.dataset.historyUrl || "";
        const parcelId = item.dataset.parcelId || "";

        const row = document.createElement("div");
        row.className = "track-item";
        row.dataset.historyUrl = historyUrl;
        row.dataset.parcelId = parcelId;

        row.innerHTML = `
          <div class="track-item__main">
            <p class="track-item__number">${escapeHtml(trackNumber)}</p>
            <p class="track-item__status">${escapeHtml(statusText)}</p>
          </div>
        `;

        list.appendChild(row);
      });

      statusModalBody.appendChild(list);
    }

    statusModalTitle.textContent = statusLabel(status);
    openModal(statusModal);
  }

  statusCards.forEach((card) => {
    card.addEventListener("click", (e) => {
      e.preventDefault();
      const status = card.dataset.status;
      openStatusModal(status);
    });
  });

  // ====== ИСТОРИЯ КОНКРЕТНОЙ ПОСЫЛКИ ======
  function loadParcelHistory(historyUrl, trackNumber) {
    if (!historyModal || !historyTimeline || !historyModalTitle) return;
    if (!historyUrl) return;

    historyTimeline.innerHTML = `
      <div class="empty-state">
        <p>Загрузка истории...</p>
      </div>
    `;

    fetch(historyUrl, {
      method: "GET",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json",
      },
      credentials: "same-origin",
    })
      .then((res) => {
        if (!res.ok) throw new Error("Ошибка загрузки");
        return res.json();
      })
      .then((data) => {
        const events = data.events || [];
        const tn = data.track_number || trackNumber || "";

        historyModalTitle.textContent =
          "История отслеживания" + (tn ? ` — ${escapeHtml(tn)}` : "");

        if (!events.length) {
          historyTimeline.innerHTML = `
            <div class="empty-state">
              <div class="empty-state__icon">⏳</div>
              <p>История статусов пока отсутствует.</p>
            </div>
          `;
          openModal(historyModal);
          return;
        }

        historyTimeline.innerHTML = events
          .map((e) => {
            const dotClass = e.is_latest
              ? "timeline-item__dot timeline-item__dot--active"
              : "timeline-item__dot";
            const statusClass = e.is_latest
              ? "timeline-item__status timeline-item__status--active"
              : "timeline-item__status";

            return `
              <div class="timeline-item">
                <div class="${dotClass}"></div>
                <div class="timeline-item__content">
                  <p class="${statusClass}">${escapeHtml(
                    e.status_display || ""
                  )}</p>
                  ${
                    e.message
                      ? `<p class="timeline-item__message">${escapeHtml(
                          e.message
                        )}</p>`
                      : ""
                  }
                  <p class="timeline-item__date">${escapeHtml(
                    e.datetime || ""
                  )}</p>
                </div>
              </div>
            `;
          })
          .join("");

        openModal(historyModal);
      })
      .catch((err) => {
        console.error(err);
        historyTimeline.innerHTML = `
          <div class="empty-state">
            <div class="empty-state__icon">⚠️</div>
            <p>Не удалось загрузить историю. Попробуйте позже.</p>
          </div>
        `;
        openModal(historyModal);
      });
  }

  // ====== Делегирование кликов (закрытие модалок + клик по трекам) ======
  document.addEventListener("click", (e) => {
    // закрытие модалок по кнопке
    const closeBtn = e.target.closest("[data-modal-close]");
    if (closeBtn) {
      const id = closeBtn.getAttribute("data-modal-close");
      const modal = document.getElementById(id);
      if (modal) closeModal(modal);
      return;
    }

    // клик по backdrop
    if (e.target.classList.contains("modal__backdrop")) {
      const modal = e.target.closest(".modal");
      if (modal) closeModal(modal);
      return;
    }

    // клик по карточке посылки
    const trackItem = e.target.closest(".track-item");
    if (trackItem && trackItem.dataset.historyUrl) {
      const url = trackItem.dataset.historyUrl;
      const trackNumber =
        trackItem.querySelector(".track-item__number")?.textContent?.trim() ||
        "";
      loadParcelHistory(url, trackNumber);
    }
  });

  // ====== ПОИСК "ОТСЛЕДИТЬ ТОВАР" (любой трек, даже чужой) ======
  if (trackSearchForm && trackSearchInput) {
    trackSearchInput.addEventListener("input", () => setSearchMsg(""));

    trackSearchForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const track = cleanTrack(trackSearchInput.value);
      trackSearchInput.value = track;

      if (!track) return;

      try {
        // публичный lookup по треку
        const res = await fetch(
          `/cabinet/api/track/public/?track=${encodeURIComponent(track)}`,
          {
            method: "GET",
            headers: {
              "X-Requested-With": "XMLHttpRequest",
              Accept: "application/json",
            },
            credentials: "same-origin",
          }
        );

        if (!res.ok) {
          setSearchMsg("Трек не найден.");
          return;
        }

        const lookup = await res.json();

        if (!lookup || !lookup.ok || !lookup.history_url) {
          setSearchMsg("Трек не найден.");
          return;
        }

        setSearchMsg("");
        loadParcelHistory(lookup.history_url, lookup.track_number || track);
      } catch (err) {
        console.error(err);
        setSearchMsg("Трек не найден.");
      }
    });
  }

  // ====== ПОКАЗАТЬ ЕЩЁ ДЛЯ "МОИ ПОСЫЛКИ" ======
  const showMoreBtn = document.getElementById("trackShowMoreBtn");
  if (showMoreBtn && trackListWrapper) {
    const step = Number(showMoreBtn.dataset.step || 5);

    showMoreBtn.addEventListener("click", () => {
      const hiddenItems = Array.from(
        trackListWrapper.querySelectorAll(".track-item--hidden")
      );

      if (!hiddenItems.length) {
        showMoreBtn.style.display = "none";
        return;
      }

      hiddenItems.slice(0, step).forEach((el) => {
        el.classList.remove("track-item--hidden");
      });

      const stillHidden = trackListWrapper.querySelector(".track-item--hidden");
      if (!stillHidden) showMoreBtn.style.display = "none";
    });
  }
});
