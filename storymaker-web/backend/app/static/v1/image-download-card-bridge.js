(() => {
  "use strict";

  const handledCards = new WeakSet();
  const helperText = "버튼을 누르면 사용자 PC의 다운로드 폴더에 저장됩니다.";

  function findImageCard(button) {
    let node = button.parentElement;
    while (node && node !== document.body) {
      if (node.querySelector("img") && node.contains(button)) return node;
      node = node.parentElement;
    }
    return null;
  }

  function enhance() {
    document.querySelectorAll("button").forEach((button) => {
      const card = findImageCard(button);
      if (!card) return;

      const text = (button.textContent || "").trim();
      if (!text.includes("다운로드")) return;

      if (!text.includes("준비 중")) button.textContent = "다운로드";

      card.querySelectorAll("p").forEach((paragraph) => {
        if ((paragraph.textContent || "").trim() === helperText) paragraph.remove();
      });

      if (handledCards.has(card)) return;
      handledCards.add(card);
      card.style.cursor = "pointer";
      card.setAttribute("role", "button");
      if (!card.hasAttribute("tabindex")) card.tabIndex = 0;
      card.setAttribute("aria-label", "이미지 다운로드");

      const triggerDownload = (event) => {
        if (event.target.closest("button, a, input, select, textarea")) return;
        button.click();
      };

      card.addEventListener("click", triggerDownload);
      card.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        if (event.target.closest("button, a, input, select, textarea")) return;
        event.preventDefault();
        button.click();
      });
    });
  }

  const observer = new MutationObserver(enhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  enhance();
})();
