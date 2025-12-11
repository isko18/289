// static/js/register.js

document.addEventListener("DOMContentLoaded", () => {
  // Переходы по табам и ссылкам с data-link (вход/регистрация)
  document.querySelectorAll("[data-link]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = btn.getAttribute("data-link");
      if (url) {
        window.location.href = url;
      }
    });
  });

  // ==== ПУНКТ ВЫДАЧИ (кастомный select) ====

  const pickupButton = document.getElementById("pickupButton");
  const pickupDropdown = document.getElementById("pickupDropdown");
  const pickupLabel = document.getElementById("pickupLabel");
  const pickupValue = document.getElementById("pickupValue");

  if (pickupButton && pickupDropdown && pickupLabel && pickupValue) {
    // Открыть / закрыть дропдаун
    pickupButton.addEventListener("click", () => {
      pickupDropdown.classList.toggle("select-dropdown--open");
    });

    // Выбор пункта
    pickupDropdown.querySelectorAll(".select-option").forEach((option) => {
      option.addEventListener("click", () => {
        const value = option.getAttribute("data-value");
        const text = option.textContent.trim();

        pickupValue.value = value;
        pickupLabel.textContent = text;
        pickupLabel.classList.remove("select-placeholder");
        pickupDropdown.classList.remove("select-dropdown--open");
      });
    });

    // Клик вне дропдауна — закрыть
    document.addEventListener("click", (e) => {
      if (
        !pickupDropdown.contains(e.target) &&
        !pickupButton.contains(e.target)
      ) {
        pickupDropdown.classList.remove("select-dropdown--open");
      }
    });
  }

  // ==== Показ / скрытие паролей ====

  // Основной пароль
  const regPasswordInput = document.getElementById("reg-password");
  const regTogglePassword = document.getElementById("regTogglePassword");
  const regTogglePasswordIcon = document.getElementById("regTogglePasswordIcon");

  if (regPasswordInput && regTogglePassword && regTogglePasswordIcon) {
    regTogglePassword.addEventListener("click", () => {
      const isHidden = regPasswordInput.type === "password";
      regPasswordInput.type = isHidden ? "text" : "password";
      regTogglePasswordIcon.textContent = isHidden ? "🙈" : "👁";
      regTogglePassword.setAttribute(
        "aria-label",
        isHidden ? "Скрыть пароль" : "Показать пароль"
      );
    });
  }

  // Подтверждение пароля
  const regConfirmInput = document.getElementById("reg-confirmPassword");
  const regToggleConfirm = document.getElementById("regToggleConfirmPassword");
  const regToggleConfirmIcon = document.getElementById(
    "regToggleConfirmPasswordIcon"
  );

  if (regConfirmInput && regToggleConfirm && regToggleConfirmIcon) {
    regToggleConfirm.addEventListener("click", () => {
      const isHidden = regConfirmInput.type === "password";
      regConfirmInput.type = isHidden ? "text" : "password";
      regToggleConfirmIcon.textContent = isHidden ? "🙈" : "👁";
      regToggleConfirm.setAttribute(
        "aria-label",
        isHidden ? "Скрыть пароль" : "Показать пароль"
      );
    });
  }

  // Опциональная валидация перед отправкой формы (оставляю простой пример)
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", (e) => {
      // Если пункт выдачи обязателен — можно заблокировать сабмит
      if (pickupValue && !pickupValue.value) {
        // фронтовый чек, всё равно бэкенд валидирует
        alert("Выберите пункт выдачи.");
        e.preventDefault();
        return;
      }
    });
  }
});
