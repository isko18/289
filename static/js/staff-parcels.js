// static/js/staff-parcels.js
document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  const form = document.getElementById("staffParcelForm");
  const trackInput = document.getElementById("staffTrackInput");
  const noteTextarea = document.getElementById("staffNote");
  const clearBtn = document.getElementById("staffClearBtn");

  const alertError = document.getElementById("staffAlertError");
  const alertSuccess = document.getElementById("staffAlertSuccess");

  const recentList = document.getElementById("staffRecentList");

  const TRACK_MIN_LEN = 6;
  const TRACK_MAX_LEN = 18;
  
  const normTrack = (v) => String(v || "").replace(/\s+/g, "").trim().toUpperCase();
  const normNote = (v) => String(v || "").trim();
  
  function showError(message) {
    // если есть существующий элемент ошибки - используем его
    let errorDiv = alertError;
    
    if (!errorDiv) {
      // создаем новый элемент ошибки если его нет
      errorDiv = document.createElement("div");
      errorDiv.id = "staffAlertError";
      errorDiv.className = "alert alert--error";
      
      // вставляем перед формой
      if (form && form.parentNode) {
        form.parentNode.insertBefore(errorDiv, form);
      }
    }
    
    errorDiv.textContent = message;
    errorDiv.style.display = "block";
    errorDiv.classList.remove("alert--fade-out");
    
    // скрываем сообщение об успехе если есть
    if (alertSuccess) {
      alertSuccess.style.display = "none";
    }
    
    // автоскрытие через 5 секунд
    setTimeout(() => {
      if (errorDiv && errorDiv.parentNode) {
        errorDiv.classList.add("alert--fade-out");
        setTimeout(() => {
          if (errorDiv && errorDiv.parentNode) {
            errorDiv.style.display = "none";
          }
        }, 400);
      }
    }, 5000);
    
    // прокручиваем к ошибке
    errorDiv.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // автофокус на поле сканера
  if (trackInput) {
    trackInput.focus();
    trackInput.select();
  }

  function autoHideAlert(el) {
    if (!el) return;
    setTimeout(() => {
      el.classList.add("alert--fade-out");
      setTimeout(() => {
        if (el && el.parentNode) {
          el.parentNode.removeChild(el);
        }
      }, 400);
    }, 3500);
  }

  autoHideAlert(alertError);
  autoHideAlert(alertSuccess);

  // чистим трек на лету (сканеры часто вставляют перевод строки/пробелы)
  if (trackInput) {
    const onClean = () => {
      const cleaned = normTrack(trackInput.value);
      if (trackInput.value !== cleaned) {
        const pos = trackInput.selectionStart || cleaned.length;
        trackInput.value = cleaned;
        try {
          trackInput.setSelectionRange(pos, pos);
        } catch (_) {}
      }
    };

    trackInput.addEventListener("input", onClean);
    trackInput.addEventListener("paste", () => {
      // после paste значение появится чуть позже
      setTimeout(onClean, 0);
    });

    // если сканер/юзер жмёт Enter — отправляем форму
    trackInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (form) form.requestSubmit();
      }
    });
  }

  // чистим пробелы перед отправкой (финальный контроль)
  if (form && trackInput) {
    form.addEventListener("submit", (e) => {
      const rawValue = (trackInput.value || "").trim().replace(/\s+/g, "").toUpperCase();
      
      // проверка длины трек-номера до обрезки
      if (rawValue.length > 0) {
        if (rawValue.length < TRACK_MIN_LEN) {
          e.preventDefault();
          showError(`Трек-номер слишком короткий (минимум ${TRACK_MIN_LEN} символов). Введено: ${rawValue.length}.`);
          trackInput.value = rawValue;
          trackInput.focus();
          trackInput.select();
          return false;
        }
        if (rawValue.length > TRACK_MAX_LEN) {
          e.preventDefault();
          showError(`Трек-номер слишком длинный (максимум ${TRACK_MAX_LEN} символов). Введено: ${rawValue.length}.`);
          trackInput.value = rawValue.slice(0, TRACK_MAX_LEN);
          trackInput.focus();
          trackInput.select();
          return false;
        }
      }
      
      const cleaned = normTrack(trackInput.value);
      trackInput.value = cleaned;
      if (noteTextarea) noteTextarea.value = normNote(noteTextarea.value);
      // страница перезагрузится, после загрузки снова будет автофокус
    });
  }
  
  // показываем предупреждение при вводе слишком длинного трека
  if (trackInput) {
    trackInput.addEventListener("input", () => {
      const rawValue = (trackInput.value || "").trim().replace(/\s+/g, "").toUpperCase();
      
      // добавляем/убираем класс для стилизации
      if (rawValue.length > TRACK_MAX_LEN) {
        trackInput.style.borderColor = "#dc3545";
        trackInput.title = `Трек-номер слишком длинный (максимум ${TRACK_MAX_LEN} символов). Введено: ${rawValue.length}.`;
      } else if (rawValue.length > 0 && rawValue.length < TRACK_MIN_LEN) {
        trackInput.style.borderColor = "#ffc107";
        trackInput.title = `Трек-номер слишком короткий (минимум ${TRACK_MIN_LEN} символов). Введено: ${rawValue.length}.`;
      } else {
        trackInput.style.borderColor = "";
        trackInput.title = "";
      }
    });
  }

  if (clearBtn && trackInput) {
    clearBtn.addEventListener("click", (e) => {
      e.preventDefault();
      trackInput.value = "";
      if (noteTextarea) noteTextarea.value = "";
      trackInput.focus();
    });
  }

  // клик по последней посылке — подставляем трек
  if (recentList && trackInput) {
    recentList.addEventListener("click", (e) => {
      const item = e.target.closest(".staff-list-item");
      if (!item) return;
      const track = normTrack(item.dataset.track || "");
      if (track) {
        trackInput.value = track;
        trackInput.focus();
        trackInput.select();
      }
    });
  }
});
