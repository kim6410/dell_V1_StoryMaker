(() => {
  if (window.__STORYMAKER_IMAGE_FIRST_BRIDGE__) return;
  window.__STORYMAKER_IMAGE_FIRST_BRIDGE__ = true;

  const state = {
    files: [],
    confirmed: false,
    draggedIndex: null,
    uploadByJob: new Map(),
    mountedFor: null,
    currentMainJobId: "",
    thumbnailTriggerPromise: null,
    thumbnailTriggerSnapshot: null,
  };

  const originalFetch = window.fetch.bind(window);
  const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  function findRouteButton(target) {
    let node = target instanceof Element ? target : null;
    while (node && node !== document.body) {
      if (node.tagName === "BUTTON") {
        const label = String(node.textContent || "").replace(/\s+/g, " ").trim();
        if (label === "작업 시작" || label === "새 콘텐츠 만들기") return node;
      }
      node = node.parentElement;
    }
    return null;
  }

  function scrollToCurrentOneShot() {
    const target =
      document.querySelector("[data-image-first-panel]") ||
      document.getElementById("storymaker-one-shot-stage-input") ||
      Array.from(document.querySelectorAll("section, div")).find((node) => {
        const text = String(node.textContent || "").replace(/\s+/g, " ").trim();
        return text.includes("이미지 업로드") && text.includes("1단계");
      });

    if (target) {
      const top = target.getBoundingClientRect().top + window.scrollY - 24;
      window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
      if (typeof target.focus === "function") target.focus({ preventScroll: true });
      return true;
    }

    const bottom = Math.max(
      document.documentElement?.scrollHeight || 0,
      document.body?.scrollHeight || 0
    );
    window.scrollTo({ top: bottom, behavior: "smooth" });
    return false;
  }

  document.addEventListener("click", (event) => {
    const button = findRouteButton(event.target);
    if (!button) return;

    const label = String(button.textContent || "").replace(/\s+/g, " ").trim();
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    if (label === "작업 시작") {
      window.location.assign("/v1?page=workpanel");
      return;
    }

    [0, 120, 350].forEach((wait) => {
      window.setTimeout(scrollToCurrentOneShot, wait);
    });
  }, true);

  function authHeaders() {
    const token = String(localStorage.getItem("storymaker_token") || "").trim();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function uploadImagesForJob(jobId) {
    if (!jobId || !state.files.length) throw new Error("업로드할 이미지가 없습니다.");
    if (state.uploadByJob.has(jobId)) return state.uploadByJob.get(jobId);

    const task = (async () => {
      setStatus("이미지를 현재 작업에 연결하고 있습니다...");
      const formData = new FormData();
      state.files.slice(0, 12).forEach((file) => formData.append("images", file));
      const response = await originalFetch(`/v1-api/mobile/one-shot/main-jobs/${encodeURIComponent(jobId)}/images`, {
        method: "POST",
        credentials: "include",
        headers: authHeaders(),
        body: formData,
      });
      const payload = await response.clone().json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.detail || payload.message || "이미지 업로드에 실패했습니다.");
      }
      setStatus(`이미지 ${state.files.length}장을 현재 작업에 연결했습니다.`);
      return true;
    })().catch((error) => {
      state.uploadByJob.delete(jobId);
      setStatus(error instanceof Error ? error.message : "이미지 업로드에 실패했습니다.", true);
      throw error;
    });

    state.uploadByJob.set(jobId, task);
    return task;
  }

  function responseFromSnapshot(snapshot) {
    return new Response(snapshot.body, {
      status: snapshot.status,
      statusText: snapshot.statusText,
      headers: snapshot.headers,
    });
  }

  function findProjectTitle() {
    const companyLine = Array.from(document.querySelectorAll("div, p, span"))
      .map((node) => String(node.textContent || "").trim())
      .find((text) => text && text.length < 100 && text.includes("/") && /\d{2,4}-\d{3,4}-\d{4}/.test(text));
    return companyLine ? companyLine.split("/")[0].trim() : "StoryMaker 썸네일";
  }

  async function triggerThumbnailEarly(blocks) {
    if (state.thumbnailTriggerPromise) return state.thumbnailTriggerPromise;
    if (!state.files.length) return null;

    const instagramText = String(
      blocks?.INSTAGRAM_POST ||
      blocks?.NAVER_BLOG ||
      blocks?.BLOG_POST ||
      "현재 콘텐츠를 바탕으로 썸네일을 제작해 주세요."
    ).trim();

    state.thumbnailTriggerPromise = (async () => {
      setStatus("콘텐츠 정리 완료 · 1초 후 썸네일 요청을 먼저 전송합니다.");
      await delay(1000);

      const form = new FormData();
      form.append("project_title", findProjectTitle());
      form.append("instagram_text", instagramText);
      form.append("content_id", state.currentMainJobId || "");
      form.append("content_path", "");
      state.files.slice(0, 3).forEach((file) => form.append("images", file, file.name));

      const response = await originalFetch("/v1-api/slideshow/thumbnail-start", {
        method: "POST",
        credentials: "include",
        headers: authHeaders(),
        body: form,
      });
      const body = await response.text();
      const headers = {};
      response.headers.forEach((value, key) => { headers[key] = value; });
      const snapshot = {
        body,
        status: response.status,
        statusText: response.statusText,
        headers,
      };
      if (!response.ok) {
        let message = "썸네일 요청 접수에 실패했습니다.";
        try {
          const payload = JSON.parse(body || "{}");
          message = payload.detail || payload.message || message;
        } catch (_) {}
        throw new Error(message);
      }
      state.thumbnailTriggerSnapshot = snapshot;
      setStatus("썸네일 요청을 먼저 접수했습니다. 팟캐스트·영상 제작을 이어갑니다.");
      return snapshot;
    })().catch((error) => {
      state.thumbnailTriggerPromise = null;
      state.thumbnailTriggerSnapshot = null;
      setStatus(error instanceof Error ? error.message : "썸네일 요청 접수에 실패했습니다.", true);
      throw error;
    });

    return state.thumbnailTriggerPromise;
  }

  window.fetch = async function storymakerImageFirstFetch(input, init = {}) {
    const url = typeof input === "string" ? input : String(input?.url || "");

    if (url.includes("/v1-api/test/trigger-start") && init?.body) {
      try {
        const body = typeof init.body === "string" ? JSON.parse(init.body) : null;
        if (body?.action === "GENERATE_GEMINI" && body?.job_id) {
          state.currentMainJobId = String(body.job_id);
          state.thumbnailTriggerPromise = null;
          state.thumbnailTriggerSnapshot = null;
          if (state.confirmed && state.files.length) await uploadImagesForJob(state.currentMainJobId);
        }
      } catch (error) {
        console.error("[IMAGE-FIRST] 메인 트리거 전 이미지 업로드 실패", error);
        throw error;
      }
    }

    if (url.includes("/v1-api/parse-result")) {
      const response = await originalFetch(input, init);
      if (!response.ok) return response;
      try {
        const payload = await response.clone().json();
        const blocks = payload?.data?.blocks || payload?.blocks || {};
        await triggerThumbnailEarly(blocks);
      } catch (error) {
        console.error("[IMAGE-FIRST] 파싱 직후 썸네일 선행 요청 실패", error);
      }
      return response;
    }

    if (url.includes("/v1-api/slideshow/thumbnail-start")) {
      if (state.thumbnailTriggerSnapshot) return responseFromSnapshot(state.thumbnailTriggerSnapshot);
      if (state.thumbnailTriggerPromise) {
        const snapshot = await state.thumbnailTriggerPromise;
        if (snapshot) return responseFromSnapshot(snapshot);
      }
    }

    return originalFetch(input, init);
  };

  function setStatus(message, isError = false) {
    const status = document.querySelector("[data-image-first-status]");
    if (!status) return;
    status.textContent = message;
    status.style.color = isError ? "#fda4af" : "#a5f3fc";
  }

  function syncCompletedStepCards() {
    const nodes = Array.from(document.querySelectorAll("div, span, p"));
    const inputText = nodes.find((node) => String(node.textContent || "").trim() === "글감 입력 완료");
    const imageText = nodes.find((node) => /^이미지\s+\d+장\s+연결\s+완료$/.test(String(node.textContent || "").trim()));
    if (!inputText || !imageText) return;

    const findCard = (node) => {
      let current = node;
      for (let depth = 0; current && depth < 10; depth += 1, current = current.parentElement) {
        const buttons = Array.from(current.querySelectorAll?.("button") || []);
        if (buttons.some((button) => String(button.textContent || "").trim() === "펼치기")) return current;
      }
      return null;
    };

    const inputCard = findCard(inputText);
    const imageCard = findCard(imageText);
    if (!inputCard || !imageCard || inputCard === imageCard) return;

    let parent = inputCard.parentElement;
    while (parent && !parent.contains(imageCard)) parent = parent.parentElement;
    if (!parent) return;

    const directChild = (card) => {
      let child = card;
      while (child.parentElement && child.parentElement !== parent) child = child.parentElement;
      return child.parentElement === parent ? child : null;
    };

    const inputItem = directChild(inputCard);
    const imageItem = directChild(imageCard);
    if (!inputItem || !imageItem || inputItem === imageItem) return;

    imageItem.style.order = "1";
    inputItem.style.order = "2";
    if (imageItem.nextElementSibling !== inputItem) parent.insertBefore(imageItem, inputItem);

    const setNumber = (card, number) => {
      const numberNode = Array.from(card.querySelectorAll("div, span")).find((node) => {
        const text = String(node.textContent || "").trim();
        return (text === "01" || text === "02") && node.children.length === 0;
      });
      if (numberNode && numberNode.textContent !== number) numberNode.textContent = number;
    };

    imageCard.style.order = "1";
    inputCard.style.order = "2";
    imageCard.dataset.storymakerStepOrder = "1";
    inputCard.dataset.storymakerStepOrder = "2";

    setNumber(imageCard, "01");
    setNumber(inputCard, "02");

    const replaceExactText = (card, fromTexts, toText) => {
      const target = Array.from(card.querySelectorAll("div, span, p")).find((node) => {
        const text = String(node.textContent || "").trim();
        return node.children.length === 0 && fromTexts.includes(text);
      });
      if (target && target.textContent !== toText) target.textContent = toText;
    };

    replaceExactText(imageCard, ["입력 정보", "이미지 업로드"], "이미지 업로드");
    replaceExactText(inputCard, ["입력 정보", "이미지 업로드"], "입력 정보");

    const imageCountText = String(imageText.textContent || "").trim();
    replaceExactText(imageCard, ["글감 입력 완료", imageCountText], imageCountText);
    replaceExactText(inputCard, ["글감 입력 완료", imageCountText], "글감 입력 완료");
  }

  function findTextarea() {
    return Array.from(document.querySelectorAll("textarea")).find((node) =>
      String(node.getAttribute("placeholder") || "").includes("오늘 있었던 일")
    );
  }

  function findGenerateButton(textarea) {
    const panel = textarea?.closest("section") || textarea?.parentElement?.parentElement;
    const buttons = Array.from((panel || document).querySelectorAll("button"));
    return buttons.find((button) => ["생성 시작", "작업 진행"].includes(button.textContent.trim()));
  }

  function renderPreviews(container) {
    container.innerHTML = "";
    state.files.forEach((file, index) => {
      const item = document.createElement("div");
      item.draggable = !state.confirmed;
      item.dataset.index = String(index);
      item.style.cssText = "position:relative;aspect-ratio:4/3;overflow:hidden;border:1px solid #1e3a5f;border-radius:14px;background:#020617;cursor:grab";

      const image = document.createElement("img");
      const objectUrl = URL.createObjectURL(file);
      image.src = objectUrl;
      image.alt = `선택 이미지 ${index + 1}`;
      image.draggable = false;
      image.style.cssText = "width:100%;height:100%;object-fit:cover";
      image.addEventListener("load", () => URL.revokeObjectURL(objectUrl), { once: true });

      const order = document.createElement("span");
      order.textContent = String(index + 1);
      order.style.cssText = "position:absolute;left:7px;top:7px;display:grid;place-items:center;min-width:28px;height:28px;padding:0 7px;border-radius:999px;background:rgba(2,6,23,.88);color:#a5f3fc;font-size:12px;font-weight:900";

      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", "선택 이미지 제거");
      remove.style.cssText = "position:absolute;right:7px;top:7px;width:28px;height:28px;border-radius:999px;border:1px solid #475569;background:rgba(2,6,23,.88);color:white;font-weight:900";
      remove.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (state.confirmed) return;
        state.files.splice(index, 1);
        renderPreviews(container);
        updateCount();
      });

      item.addEventListener("dragstart", (event) => {
        if (state.confirmed) return;
        state.draggedIndex = index;
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
        item.style.opacity = ".5";
      });
      item.addEventListener("dragover", (event) => {
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
      });
      item.addEventListener("drop", (event) => {
        event.preventDefault();
        if (state.confirmed || state.draggedIndex == null || state.draggedIndex === index) return;
        const moved = state.files.splice(state.draggedIndex, 1)[0];
        state.files.splice(index, 0, moved);
        state.draggedIndex = null;
        renderPreviews(container);
        updateCount();
      });
      item.addEventListener("dragend", () => {
        state.draggedIndex = null;
        item.style.opacity = "1";
      });

      item.append(image, order, remove);
      container.appendChild(item);
    });
  }

  function updateCount() {
    const count = document.querySelector("[data-image-first-count]");
    const confirm = document.querySelector("[data-image-first-confirm]");
    if (count) count.textContent = `선택된 이미지 ${state.files.length}장`;
    if (confirm) {
      const insufficient = state.files.length < 5;
      const completed = state.confirmed;
      const visuallyDisabled = insufficient || completed;

      confirm.disabled = completed;
      confirm.setAttribute("aria-disabled", visuallyDisabled ? "true" : "false");
      confirm.style.color = visuallyDisabled ? "#94a3b8" : "#ffffff";
      confirm.style.opacity = visuallyDisabled ? ".55" : "1";
      confirm.style.textShadow = visuallyDisabled
        ? "none"
        : "0 1px 2px rgba(0,0,0,.55)";
      confirm.style.cursor = completed ? "default" : "pointer";
    }
  }

  function mount() {
    const textarea = findTextarea();
    if (!textarea || textarea.dataset.imageFirstBound === "1") return;
    const generateButton = findGenerateButton(textarea);
    if (!generateButton) return;

    textarea.dataset.imageFirstBound = "1";
    state.mountedFor = textarea;

    const wrapper = textarea.parentElement;
    const panel = document.createElement("div");
    panel.dataset.imageFirstPanel = "1";
    panel.style.cssText = "margin-bottom:16px;border:1px solid rgba(34,211,238,.38);border-radius:24px;background:rgba(2,6,23,.72);padding:18px;box-shadow:inset 0 0 22px rgba(8,145,178,.08)";
    panel.innerHTML = `
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">
        <span style="display:grid;place-items:center;width:48px;height:48px;border-radius:999px;background:#67e8f9;color:#082f49;font-weight:900">01</span>
        <div><div style="font-size:12px;color:#67e8f9;font-weight:900">현재 과정</div><div style="margin-top:4px;color:white;font-size:18px;font-weight:900">이미지 업로드</div></div>
      </div>
      <label data-image-first-dropzone style="display:grid;min-height:300px;place-items:center;border:2px dashed rgba(34,211,238,.65);border-radius:22px;background:linear-gradient(#08334433,#020617cc);padding:24px;text-align:center;cursor:pointer;transition:border-color .16s ease,background .16s ease,box-shadow .16s ease,transform .16s ease">
        <span><b style="display:block;color:white;font-size:15px">이미지를 드래그하거나 클릭하여 추가하세요</b><small style="display:block;margin-top:8px;color:#a5f3fc;font-weight:800">JPG · PNG · WEBP · 5~12장</small></span>
        <input data-image-first-input type="file" accept="image/*" multiple style="display:none">
      </label>
      <div data-image-first-count style="margin-top:10px;color:#cbd5e1;font-size:12px;font-weight:800">선택된 이미지 0장</div>
      <div data-image-first-previews style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px"></div>
      <div data-image-first-status style="margin-top:12px;color:#a5f3fc;font-size:12px;font-weight:800">사진 5장 이상 선택 후 확인 버튼을 눌러 주세요.</div>
      <button data-image-first-confirm type="button" disabled style="width:100%;margin-top:14px;border:1px solid rgba(103,232,249,.5);border-radius:16px;background:linear-gradient(#0e7490,#155e75);padding:14px 18px;color:white;font-size:16px;font-weight:900;cursor:pointer;opacity:.55">1단계 확인</button>
    `;

    wrapper.insertBefore(panel, textarea);

    const stage2 = document.createElement("div");
    stage2.dataset.imageFirstStage2 = "1";
    stage2.style.cssText = "display:none;align-items:center;gap:14px;margin:4px 0 14px";
    stage2.innerHTML = '<span style="display:grid;place-items:center;width:48px;height:48px;border-radius:999px;background:#67e8f9;color:#082f49;font-weight:900">02</span><div><div style="font-size:12px;color:#67e8f9;font-weight:900">현재 과정</div><div style="margin-top:4px;color:white;font-size:18px;font-weight:900">기초자료 입력</div></div>';
    wrapper.insertBefore(stage2, textarea);

    textarea.style.display = "none";
    generateButton.style.display = "none";
    generateButton.textContent = "작업 진행";

    const input = panel.querySelector("[data-image-first-input]");
    const previews = panel.querySelector("[data-image-first-previews]");
    const confirm = panel.querySelector("[data-image-first-confirm]");
    const dropZone = panel.querySelector("[data-image-first-dropzone]");

    function focusBelowUpload() {
      window.setTimeout(() => {
        const target = confirm || previews;
        if (!target) return;
        const rect = target.getBoundingClientRect();
        const targetY = window.scrollY + rect.bottom + 38 - Math.round(window.innerHeight * 0.58);
        window.scrollTo({ top: Math.max(0, targetY), behavior: "smooth" });
        if (typeof target.focus === "function") {
          target.setAttribute("tabindex", target.getAttribute("tabindex") || "-1");
          target.focus({ preventScroll: true });
        }
      }, 160);
    }

    function appendImageFiles(fileList) {
      if (state.confirmed) return;

      const incoming = Array.from(fileList || []).filter((file) =>
        file && ["image/jpeg", "image/png", "image/webp"].includes(String(file.type || "").toLowerCase())
      );
      if (!incoming.length) {
        setStatus("JPG, PNG, WEBP 이미지 파일만 추가할 수 있습니다.", true);
        return;
      }

      const existingKeys = new Set(state.files.map((file) => `${file.name}|${file.size}|${file.lastModified}`));
      const uniqueIncoming = incoming.filter((file) => {
        const key = `${file.name}|${file.size}|${file.lastModified}`;
        if (existingKeys.has(key)) return false;
        existingKeys.add(key);
        return true;
      });
      const availableSlots = Math.max(0, 12 - state.files.length);
      const accepted = uniqueIncoming.slice(0, availableSlots);
      const overLimit = uniqueIncoming.length > availableSlots;

      state.files.push(...accepted);
      renderPreviews(previews);
      updateCount();

      if (overLimit) {
        setStatus("입력 한계는 12장입니다. 앞의 12장만 등록했습니다.", true);
      } else if (!accepted.length) {
        setStatus("이미 선택된 사진입니다.", true);
      } else {
        setStatus(state.files.length >= 5 ? "이미지가 준비되었습니다. 순서를 확인한 뒤 1단계 확인을 눌러 주세요." : `이미지 ${state.files.length}장 선택됨 · 사진을 5장 이상 선택해 주세요.`);
      }

      if (accepted.length > 0) focusBelowUpload();
    }

    input.addEventListener("change", () => {
      appendImageFiles(input.files);
      input.value = "";
    });

    const preventDropDefaults = (event) => {
      event.preventDefault();
      event.stopPropagation();
    };

    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        preventDropDefaults(event);
        if (state.confirmed) return;
        if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
        dropZone.style.borderColor = "#67e8f9";
        dropZone.style.background = "linear-gradient(rgba(8,145,178,.28),rgba(2,6,23,.96))";
        dropZone.style.boxShadow = "0 0 0 4px rgba(34,211,238,.12), inset 0 0 32px rgba(8,145,178,.16)";
        dropZone.style.transform = "translateY(-1px)";
        setStatus("이곳에 이미지를 놓아 주세요.");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        preventDropDefaults(event);
        dropZone.style.borderColor = "rgba(34,211,238,.65)";
        dropZone.style.background = "linear-gradient(#08334433,#020617cc)";
        dropZone.style.boxShadow = "none";
        dropZone.style.transform = "none";
      });
    });

    dropZone.addEventListener("drop", (event) => {
      if (state.confirmed) return;
      appendImageFiles(event.dataTransfer?.files || []);
    });

    confirm.addEventListener("click", () => {
      if (state.files.length < 5) {
        window.alert("사진을 5장 이상 선택해 주세요.");
        return;
      }
      state.confirmed = true;
      confirm.disabled = true;
      confirm.textContent = "1단계 완료";
      confirm.style.opacity = "1";
      panel.querySelector("label").style.display = "none";
      setStatus(`이미지 ${state.files.length}장이 준비되었습니다. 기초자료를 입력해 주세요.`);
      stage2.style.display = "flex";
      textarea.style.display = "block";
      generateButton.style.display = "block";
      textarea.focus({ preventScroll: true });
      textarea.scrollIntoView({ behavior: "smooth", block: "center" });
    });

    const focusPageBottom = () => {
      const bottom = Math.max(
        document.documentElement?.scrollHeight || 0,
        document.body?.scrollHeight || 0
      );
      window.scrollTo({
        top: bottom,
        behavior: "smooth",
      });
    };

    generateButton.addEventListener("click", () => {
      if (!state.confirmed || !state.files.length) return;

      let attempts = 0;
      const keepBottomFocused = window.setInterval(() => {
        attempts += 1;
        focusPageBottom();
        if (attempts >= 40) window.clearInterval(keepBottomFocused);
      }, 500);

      window.setTimeout(focusPageBottom, 50);
      window.setTimeout(focusPageBottom, 180);
      window.setTimeout(focusPageBottom, 350);
    }, true);
  }

  const observer = new MutationObserver(() => {
    mount();
    syncCompletedStepCards();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  window.setInterval(() => {
    mount();
    syncCompletedStepCards();
  }, 700);
})();
