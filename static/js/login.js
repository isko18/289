// static/js/login.js

document.addEventListener("DOMContentLoaded", () => {
  // Переходы по табам и ссылкам с data-link
  document.querySelectorAll("[data-link]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = btn.getAttribute("data-link");
      if (url) {
        window.location.href = url;
      }
    });
  });

  // Показ / скрытие пароля на форме логина
  const passwordInput = document.getElementById("login-password");
  const toggleBtn = document.getElementById("loginTogglePassword");
  const toggleIcon = document.getElementById("loginTogglePasswordIcon");

  if (passwordInput && toggleBtn && toggleIcon) {
    toggleBtn.addEventListener("click", () => {
      const isHidden = passwordInput.type === "password";
      passwordInput.type = isHidden ? "text" : "password";
      toggleIcon.textContent = isHidden ? "🙈" : "👁";
      toggleBtn.setAttribute(
        "aria-label",
        isHidden ? "Скрыть пароль" : "Показать пароль"
      );
    });
  }
});
