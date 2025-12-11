// static/js/cabinet-theme.js
(function () {
  const body = document.body;
  if (!body) return;

  const toggleBtn = document.getElementById("themeToggleBtn");
  const STORAGE_KEY = "lc_theme";

  function applyTheme(theme) {
    if (theme === "dark") {
      body.classList.remove("theme-light");
      body.classList.add("theme-dark");
      if (toggleBtn) toggleBtn.textContent = "☀️";
    } else {
      body.classList.remove("theme-dark");
      body.classList.add("theme-light");
      if (toggleBtn) toggleBtn.textContent = "🌙";
    }
  }

  // default из data-атрибута body
  const defaultTheme = body.dataset.defaultTheme === "dark" ? "dark" : "light";
  const saved = localStorage.getItem(STORAGE_KEY);
  const initialTheme = saved || defaultTheme;

  applyTheme(initialTheme);

  if (!toggleBtn) return;

  toggleBtn.addEventListener("click", function () {
    const nextTheme = body.classList.contains("theme-dark") ? "light" : "dark";
    applyTheme(nextTheme);
    localStorage.setItem(STORAGE_KEY, nextTheme);
  });
})();
