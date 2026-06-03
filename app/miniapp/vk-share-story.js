(function () {
  var statusEl = document.getElementById("status");
  var retryEl = document.getElementById("retry");

  // VK passes the hash from the open_app button as the 'vk_hash' query param.
  // Fallback to window.location.hash for local testing.
  var search = new URLSearchParams(window.location.search);
  var rawHash = search.get("vk_hash") || window.location.hash.replace(/^#/, "");
  var hashParams = new URLSearchParams(rawHash);

  var imageUrl = hashParams.get("image_url") || "";
  var groupUrl = hashParams.get("group_url") || "";

  function share() {
    if (!imageUrl) {
      statusEl.textContent = "Открой это приложение через кнопку в сообщении бота.";
      return;
    }

    // VKWebAppShowStoryBox is only available in the VK mobile app.
    vkBridge
      .send("VKWebAppGetClientVersion")
      .then(function (info) {
        if (info.platform === "web" || info.platform === "desktop_web") {
          statusEl.textContent = "Публикация историй доступна только в мобильном приложении ВКонтакте.";
          return;
        }

        var params = {
          background_type: "image",
          url: imageUrl,
          locked: false,
        };

        if (groupUrl) {
          params.attachment = {
            text: "open",
            type: "url",
            url: groupUrl,
          };
        }

        statusEl.textContent = "URL: " + imageUrl.substring(0, 80);

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
              statusEl.textContent = "Ошибка VK Bridge: " + code + (reason ? " — " + reason : "");
            }
            retryEl.style.display = "inline-block";
          });
      })
      .catch(function () {
        statusEl.textContent = "Открой это приложение в мобильном ВКонтакте.";
      });
  }

  retryEl.addEventListener("click", share);

  // Init VK Bridge first, then run share flow.
  vkBridge.send("VKWebAppInit").then(share).catch(share);
})();
