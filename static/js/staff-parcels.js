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

  // чистим пробелы перед отправкой
  if (form && trackInput) {
    form.addEventListener("submit", () => {
      trackInput.value = trackInput.value.trim().replace(/\s+/g, "");
      if (noteTextarea) {
        noteTextarea.value = noteTextarea.value.trim();
      }
      // после submit браузер перезагрузит страницу,
      // на новой странице поле опять автофокусится.
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
      const track = item.dataset.track || "";
      if (track) {
        trackInput.value = track;
        trackInput.focus();
        trackInput.select();
      }
    });
  }
});
