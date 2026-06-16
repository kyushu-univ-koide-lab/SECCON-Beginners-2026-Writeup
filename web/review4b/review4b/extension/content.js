function byteLength(value) {
  return new TextEncoder().encode(value).length;
}

function storeReviewResult(settings) {
  const htmlSize = byteLength(document.documentElement.outerHTML);
  const textLength = document.body ? document.body.innerText.length : 0;
  const version = settings?.helperVersion || "unknown";

  const result = document.createElement("template");
  result.id = "review4b-helper-result";
  result.textContent = [
    "review4b helper",
    `HTML: ${htmlSize} bytes`,
    `Text: ${textLength} chars`,
    `Version: ${version}`
  ].join("\n");

  document.documentElement.appendChild(result);
}

(async () => {
  const settingsResponse = await chrome.runtime.sendMessage({
    cmd: "settings.get",
    keys: ["helperVersion"]
  });
  storeReviewResult(settingsResponse?.result);

  const elements = document.querySelectorAll("[data-review4b]");

  for (const el of elements) {
    const encoded = el.getAttribute("data-review4b");

    let msg;

    try {
      msg = JSON.parse(atob(encoded));
    } catch {
      el.setAttribute("data-review4b-result", JSON.stringify({
        ok: false,
        error: "invalid request"
      }));
      continue;
    }

    const response = await chrome.runtime.sendMessage(msg);

    el.setAttribute(
      "data-review4b-result",
      JSON.stringify(response)
    );
  }
})();
