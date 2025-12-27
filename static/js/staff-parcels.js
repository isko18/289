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

  const normTrack = (v) => String(v || "").replace(/\s+/g, "").trim();
  const normNote = (v) => String(v || "").trim();

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
    form.addEventListener("submit", () => {
      trackInput.value = normTrack(trackInput.value);
      if (noteTextarea) noteTextarea.value = normNote(noteTextarea.value);
      // страница перезагрузится, после загрузки снова будет автофокус
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
