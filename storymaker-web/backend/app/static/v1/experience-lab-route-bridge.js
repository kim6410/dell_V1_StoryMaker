(() => {
  if (window.__STORYMAKER_EXPERIENCE_LAB_ROUTE_BRIDGE__) return;
  window.__STORYMAKER_EXPERIENCE_LAB_ROUTE_BRIDGE__ = true;

  const TARGET_URL = "/v1/?webgpu_tts_test=1";

  const normalize = (value) => String(value || "").replace(/\s+/g, " ").trim();

  const isExperienceLabTarget = (element) => {
    if (!(element instanceof Element)) return false;

    const clickable = element.closest("button, a, [role='button']");
    if (!clickable) return false;

    const text = normalize(clickable.textContent);
    if (!text) return false;

    return (
      text.includes("체험 연구실") ||
      text === "체험" ||
      (text.includes("WebGPU") && text.includes("로컬 실험 도구"))
    );
  };

  const openExperienceLab = (event) => {
    if (!isExperienceLabTarget(event.target)) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    window.location.assign(TARGET_URL);
  };

  // 체험 메뉴는 V2 React 내부 라우팅이 처리한다.
  // WebGPU·WASM TTS 테스트 페이지로 강제 이동하던 캡처 리스너는 비활성화한다.
})();
