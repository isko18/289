document.addEventListener("DOMContentLoaded", () => {
  // =========================
  // НАВИГАЦИЯ
  // =========================

  const pages = {
    home: document.getElementById("page-home"),
    profile: document.getElementById("page-profile"),
    editProfile: document.getElementById("page-editProfile"),
  };

  const bottomNavItems = document.querySelectorAll(".bottom-nav__item");

  function showPage(name) {
    Object.entries(pages).forEach(([key, el]) => {
      if (!el) return;
      if (key === name) el.classList.remove("page--hidden");
      else el.classList.add("page--hidden");
    });

    bottomNavItems.forEach((btn) => {
      const target = btn.getAttribute("data-page-target");
      if (target === name) btn.classList.add("bottom-nav__item--active");
      else btn.classList.remove("bottom-nav__item--active");
    });
  }

  document.querySelectorAll("[data-page-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-page-target");
      if (target && pages[target]) showPage(target);
    });
  });

  // стартовая
  showPage("home");

  // =========================
  // ДАННЫЕ ПОСЫЛОК
  // =========================

  let trackItems = [];

  const statusNames = {
    1: "Принят на склад в Китае",
    2: "Отправлен из Китая",
    3: "Прибыл в пункт выдачи",
    4: "Получен",
  };

  const trackListWrapper = document.getElementById("trackListWrapper");
  const trackListCard = document.getElementById("trackListCard");

  const statusCounts = {
    1: document.getElementById("status-count-1"),
    2: document.getElementById("status-count-2"),
    3: document.getElementById("status-count-3"),
    4: document.getElementById("status-count-4"),
  };

  // =========================
  // HELPERS
  // =========================

  function randomId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
  }

  function createMockHistory(statusCode) {
    const history = [];

    if (statusCode >= 1) {
      history.push({
        date: "2025-08-19",
        status: "Товар поступил на склад в Китае",
        isActive: statusCode === 1,
      });
    }
    if (statusCode >= 2) {
      history.push({
        date: "2025-08-21",
        status: "Товар отправлен со склада и уже в пути.",
        isActive: statusCode === 2,
      });
      history.push({
        date: "2025-08-25",
        status: "По пути в Кашгар.",
        isActive: false,
      });
    }
    if (statusCode >= 3) {
      history.push({
        date: "2025-08-26",
        status: "Товар прибыл в [Бишкек].",
        isActive: statusCode === 3,
      });
      history.push({
        date: "2025-08-26",
        status: "Классификация и обработка.",
        isActive: false,
      });
    }
    if (statusCode >= 4) {
      history.push({
        date: "2025-08-28",
        status:
          "Товар прибыл в пункт выдачи, трек-номер: 45847548365495, адрес: г. Бишкек, ул. Павлова, 13/4",
        isActive: true,
      });
    }

    // последние события сверху
    return history.reverse();
  }

  function updateStatusCounters() {
    [1, 2, 3, 4].forEach((code) => {
      const count = trackItems.filter((t) => t.statusCode === code).length;
      if (statusCounts[code]) statusCounts[code].textContent = String(count);
    });
  }

  function renderHomeTrackList() {
    if (!trackListWrapper || !trackListCard) return;

    if (trackItems.length === 0) {
      trackListWrapper.innerHTML =
        '<p class="helper-text">У вас пока нет добавленных трек-номеров.</p>';
      return;
    }

    trackListWrapper.innerHTML = "";

    trackItems.forEach((track) => {
      const item = document.createElement("div");
      item.className = "track-item";

      const main = document.createElement("div");
      main.className = "track-item__main";

      const numberEl = document.createElement("p");
      numberEl.className = "track-item__number";
      numberEl.textContent = track.number;

      const statusEl = document.createElement("p");
      statusEl.className = "track-item__status";
      statusEl.textContent = track.status;

      main.appendChild(numberEl);
      main.appendChild(statusEl);

      const historyBtn = document.createElement("button");
      historyBtn.type = "button";
      historyBtn.className = "icon-button";
      historyBtn.textContent = "🔍";
      historyBtn.title = "Показать историю";
      historyBtn.addEventListener("click", () => openHistoryModal(track));

      item.appendChild(main);
      item.appendChild(historyBtn);
      trackListWrapper.appendChild(item);
    });
  }

  // =========================
  // МОДАЛКИ
  // =========================

  function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove("hidden");
  }

  function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add("hidden");
  }

  document.querySelectorAll("[data-modal-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-modal-close");
      if (id) closeModal(id);
    });
  });

  document.querySelectorAll(".modal").forEach((modal) => {
    const backdrop = modal.querySelector(".modal__backdrop");
    if (backdrop) {
      backdrop.addEventListener("click", () => modal.classList.add("hidden"));
    }
  });

  const statusModalTitle = document.getElementById("statusModalTitle");
  const statusModalBody = document.getElementById("statusModalBody");
  const historyTimeline = document.getElementById("historyTimeline");

  function openStatusModal(statusCode) {
    if (!statusModalTitle || !statusModalBody) return;

    const items = trackItems.filter((t) => t.statusCode === statusCode);
    statusModalTitle.textContent = statusNames[statusCode] || "Статус";

    statusModalBody.innerHTML = "";

    if (items.length === 0) {
      statusModalBody.innerHTML =
        '<p class="helper-text">Нет посылок с этим статусом.</p>';
    } else {
      items.forEach((track) => {
        const wrap = document.createElement("div");
        wrap.style.padding = "0.75rem 0";
        wrap.style.borderBottom = "1px solid #f3f4f6";

        const line1 = document.createElement("div");
        line1.style.display = "flex";
        line1.style.gap = "0.25rem";
        line1.innerHTML =
          '<span style="color:#6b7280;font-size:0.8rem;">Трек:</span>' +
          `<span style="font-size:0.9rem;">${track.number}</span>`;

        const activeHistory =
          track.history.find((h) => h.isActive) || track.history[0];

        const line2 = document.createElement("div");
        line2.style.display = "flex";
        line2.style.gap = "0.25rem";
        line2.innerHTML =
          '<span style="color:#6b7280;font-size:0.8rem;">Статус:</span>' +
          `<span style="font-size:0.9rem;color:#2563eb;">${
            activeHistory ? activeHistory.status : track.status
          }</span>`;

        const btnHistory = document.createElement("button");
        btnHistory.type = "button";
        btnHistory.className = "auth-link auth-link--accent";
        btnHistory.textContent = "Показать историю";
        btnHistory.addEventListener("click", () => {
          closeModal("statusModal");
          openHistoryModal(track);
        });

        wrap.appendChild(line1);
        wrap.appendChild(line2);
        wrap.appendChild(btnHistory);
        statusModalBody.appendChild(wrap);
      });
    }

    openModal("statusModal");
  }

  function openHistoryModal(track) {
    if (!historyTimeline) return;
    historyTimeline.innerHTML = "";

    track.history.forEach((item) => {
      const wrap = document.createElement("div");
      wrap.className = "timeline-item";

      const dot = document.createElement("div");
      dot.className = "timeline-item__dot";
      if (item.isActive) dot.classList.add("timeline-item__dot--active");

      const status = document.createElement("p");
      status.className = "timeline-item__status";
      if (item.isActive) status.classList.add("timeline-item__status--active");
      status.textContent = item.status;

      const date = document.createElement("p");
      date.className = "timeline-item__date";
      date.textContent = item.date;

      wrap.appendChild(dot);
      wrap.appendChild(status);
      wrap.appendChild(date);
      historyTimeline.appendChild(wrap);
    });

    openModal("historyModal");
  }

  // клики по карточкам статусов
  document.querySelectorAll(".status-card").forEach((card) => {
    card.addEventListener("click", () => {
      const code = Number(card.getAttribute("data-status") || "0");
      if (code >= 1 && code <= 4) openStatusModal(code);
    });
  });

  // =========================
  // ДОБАВЛЕНИЕ ТРЕКА
  // =========================

  const trackAddForm = document.getElementById("trackAddForm");
  const trackAddInput = document.getElementById("trackAddInput");

  if (trackAddForm && trackAddInput) {
    trackAddForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const value = trackAddInput.value.trim();
      if (!value) return;

      if (value.length < 1 || value.length > 32) {
        alert("Длина трек-номера должна быть от 1 до 32 символов.");
        return;
      }

      const randomStatus = Math.floor(Math.random() * 4) + 1;

      const newTrack = {
        id: randomId(),
        number: value,
        status: statusNames[randomStatus],
        statusCode: randomStatus,
        history: createMockHistory(randomStatus),
      };

      trackItems.push(newTrack);
      trackAddInput.value = "";

      updateStatusCounters();
      renderHomeTrackList();
    });
  }

  // =========================
  // ПОИСК ТРЕКА
  // =========================

  const trackSearchForm = document.getElementById("trackSearchForm");
  const trackSearchInput = document.getElementById("trackSearchInput");

  if (trackSearchForm && trackSearchInput) {
    trackSearchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const query = trackSearchInput.value.trim();
      if (!query) return;

      const found = trackItems.find((t) => t.number === query);
      if (found) {
        openHistoryModal(found);
      } else {
        alert("Посылка с таким трек-номером не найдена.");
      }
    });
  }

  // =========================
  // ПУНКТ ВЫДАЧИ В EDIT PROFILE
  // =========================

  const pickupPoints = [
    "Бишкек - Центр",
    "Бишкек - Восток",
    "Бишкек - Запад",
    "Ош",
    "Джалал-Абад",
  ];

  const editPickupButton = document.getElementById("editPickupButton");
  const editPickupLabel = document.getElementById("editPickupLabel");
  const editPickupDropdown = document.getElementById("editPickupDropdown");
  const editPickupValue = document.getElementById("editPickupValue");

  if (
    editPickupButton &&
    editPickupLabel &&
    editPickupDropdown &&
    editPickupValue
  ) {
    editPickupDropdown.innerHTML = "";
    pickupPoints.forEach((point) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "select-option";
      option.textContent = point;
      option.addEventListener("click", () => {
        editPickupLabel.textContent = point;
        editPickupLabel.classList.remove("select-placeholder");
        editPickupValue.value = point;

        const profilePickup = document.getElementById("profile-pickup");
        if (profilePickup) profilePickup.textContent = point;

        editPickupDropdown.classList.remove("select-dropdown--open");
      });
      editPickupDropdown.appendChild(option);
    });

    editPickupButton.addEventListener("click", () => {
      editPickupDropdown.classList.toggle("select-dropdown--open");
    });

    document.addEventListener("click", (e) => {
      if (
        !editPickupButton.contains(e.target) &&
        !editPickupDropdown.contains(e.target)
      ) {
        editPickupDropdown.classList.remove("select-dropdown--open");
      }
    });
  }

  // =========================
  // СИНХРОН ПРОФИЛЯ
  // =========================

  const editProfileForm = document.getElementById("editProfileForm");
  const editFullName = document.getElementById("edit-fullname");
  const editPhone = document.getElementById("edit-phone");
  const profileFullname = document.getElementById("profile-fullname");
  const profilePhone = document.getElementById("profile-phone");

  if (editProfileForm) {
    editProfileForm.addEventListener("submit", (e) => {
      // если нужен только фронт — можно держать preventDefault
      // e.preventDefault();

      if (editFullName && profileFullname) {
        profileFullname.textContent = editFullName.value || "Не указано";
      }
      if (editPhone && profilePhone) {
        const phoneVal = editPhone.value.trim();
        profilePhone.textContent = phoneVal ? `+996 ${phoneVal}` : "Не указано";
      }

      showPage("profile");
    });
  }

  // первичная отрисовка
  updateStatusCounters();
  renderHomeTrackList();
});
