(function () {
  function readParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }

  function normalizeMaybeEncoded(value) {
    if (!value) return "";
    try {
      const once = decodeURIComponent(value);
      if (/%[0-9A-Fa-f]{2}/.test(once)) {
        return decodeURIComponent(once);
      }
      return once;
    } catch (_) {
      return value;
    }
  }

  const imageUrl = readParam("image_url");
  const text = normalizeMaybeEncoded(readParam("text"));
  const widgetUrl = readParam("widget_url");
  const widgetName = readParam("widget_name") || "Узнать свою карту дня";

  const statusEl = document.getElementById("status");
  const retryEl = document.getElementById("retry");

  function share() {
    if (!window.Telegram || !window.Telegram.WebApp) {
      statusEl.textContent = "Откройте кнопку внутри Telegram.";
      retryEl.style.display = "inline-block";
      return;
    }

    if (!imageUrl) {
      statusEl.textContent = "Нет изображения для сторис.";
      retryEl.style.display = "inline-block";
      return;
    }

    try {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
      window.Telegram.WebApp.shareToStory(imageUrl, {
        text: text || "Мой расклад дня в @arcana_r_bot",
        widget_link: widgetUrl
          ? {
              url: widgetUrl,
              name: widgetName,
            }
          : undefined,
      });
      statusEl.textContent = "Окно публикации открыто.";
      setTimeout(() => {
        try {
          window.Telegram.WebApp.close();
        } catch (_) {
          // Ignore close errors in unsupported clients.
        }
      }, 3000);
    } catch (error) {
      statusEl.textContent = "Не удалось открыть сторис. Попробуйте еще раз.";
      retryEl.style.display = "inline-block";
    }
  }

  retryEl.addEventListener("click", share);
  share();
})();
