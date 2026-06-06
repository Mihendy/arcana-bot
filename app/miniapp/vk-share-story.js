(function () {
  var statusEl = document.getElementById("status");
  var retryEl = document.getElementById("retry");

  // VK passes the hash from the open_app button as the 'vk_hash' query param.
  // Fallback to window.location.hash for local testing.
  var search = new URLSearchParams(window.location.search);
  var rawHash = search.get("vk_hash") || window.location.hash.replace(/^#/, "");
  var hashParams = new URLSearchParams(rawHash);

  var imageUrl = hashParams.get("image_url") || "";
  var appUrl = hashParams.get("app_url") || "";

  function share() {
    if (!imageUrl) {
      statusEl.textContent = "Открой это приложение через кнопку в сообщении бота.";
      return;
    }

    var params = {
      background_type: "image",
      url: imageUrl,
      locked: false,
    };

    // attachment.url must be a vk.ru URL per VK Bridge docs
    if (appUrl) {
      params.attachment = {
        text: "open",
        type: "url",
        url: appUrl,
      };
    }

    statusEl.textContent = "Открываем редактор истории…";

    vkBridge
      .send("VKWebAppShowStoryBox", params)
      .then(function (data) {
        if (data.result) {
          statusEl.textContent = "История опубликована!";
        } else {
          statusEl.textContent = "История не была опубликована.";
          retryEl.style.display = "inline-block";
        }
      })
      .catch(function (err) {
        var code = (err && err.error_data && err.error_data.error_code) || "?";
        var reason = (err && err.error_data && err.error_data.error_reason) || "";
        if (code === 4 || reason === "User denied") {
          statusEl.textContent = "Публикация отменена.";
        } else {
          statusEl.textContent =
            "Ошибка VK Bridge: " + code + (reason ? " — " + reason : "") +
            " | URL: " + imageUrl.substring(0, 60);
        }
        retryEl.style.display = "inline-block";
      });
  }

  retryEl.addEventListener("click", share);

  // Init VK Bridge first, then run share flow.
  vkBridge.send("VKWebAppInit").then(share).catch(share);
})();
