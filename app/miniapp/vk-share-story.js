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

  // Init VK Bridge — required before any bridge.send() call.
  vkBridge.send("VKWebAppInit");

  function share() {
    if (!imageUrl) {
      statusEl.textContent = "Нет изображения для истории.";
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
      .catch(function () {
        statusEl.textContent = "Публикация отменена.";
        retryEl.style.display = "inline-block";
      });
  }

  retryEl.addEventListener("click", share);
  share();
})();
