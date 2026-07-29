(() => {
  'use strict';

  if (window.__STORYMAKER_V1_COMPANY_INFO_UI_TUNE__) return;
  window.__STORYMAKER_V1_COMPANY_INFO_UI_TUNE__ = true;

  const TOOLBAR_ID = 'storymaker-v1-company-add-toolbar';
  const STYLE_ID = 'storymaker-v1-company-info-ui-style';
  const INQUIRY_OVERLAY_ID = 'storymaker-v1-inquiry-frame-overlay';
  const INQUIRY_FRAME_URL = '/static/v1/feature-requests-frame.html';
  const KEYWORD_EDITOR_CLASS = 'storymaker-v1-keyword-slots';
  const clean = (value = '') => String(value ?? '').replace(/\s+/g, ' ').trim();
  const esc = (value = '') => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  function findExact(root, selector, text) {
    return [...root.querySelectorAll(selector)].find(
      (node) => clean(node.textContent) === text
    ) || null;
  }


  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      [data-v1-company-hero-hidden="1"] {
        display: none !important;
      }
      #${TOOLBAR_ID} {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
        margin-bottom: 12px;
        min-height: 42px;
      }
      #${TOOLBAR_ID} button {
        min-height: 42px;
        border: 1px solid rgba(103, 232, 249, 0.68);
        border-radius: 8px;
        background: #22d3ee;
        padding: 10px 18px;
        color: #082f49;
        font-size: 16px;
        font-weight: 900;
        cursor: pointer;
        box-shadow: 0 8px 24px rgba(34, 211, 238, 0.18);
      }
      #${TOOLBAR_ID} button:hover {
        background: #67e8f9;
        border-color: #a5f3fc;
      }
      #${INQUIRY_OVERLAY_ID} {
        position: fixed;
        inset: 0;
        z-index: 99990;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 28px;
        background: rgba(2, 6, 23, 0.72);
        backdrop-filter: blur(4px);
      }
      #${INQUIRY_OVERLAY_ID}[hidden] { display: none !important; }
      #${INQUIRY_OVERLAY_ID} .sm-v1-inquiry-frame-shell {
        position: relative;
        width: min(1180px, calc(100vw - 56px));
        height: min(820px, calc(100vh - 56px));
        overflow: hidden;
        border: 1px solid rgba(103, 232, 249, 0.38);
        border-radius: 18px;
        background: #07111f;
        box-shadow: 0 28px 90px rgba(0, 0, 0, 0.52);
      }
      #${INQUIRY_OVERLAY_ID} iframe {
        display: block;
        width: 100%;
        height: 100%;
        border: 0;
        background: #07111f;
      }
      #${INQUIRY_OVERLAY_ID} .sm-v1-inquiry-frame-close {
        position: absolute;
        top: 12px;
        right: 12px;
        z-index: 2;
        width: 38px;
        height: 38px;
        padding: 0;
        border: 1px solid rgba(148, 163, 184, 0.34);
        border-radius: 10px;
        background: rgba(15, 23, 42, 0.92);
        color: #f8fafc;
        font-size: 22px;
        line-height: 1;
        cursor: pointer;
      }
      #${INQUIRY_OVERLAY_ID} .sm-v1-inquiry-frame-close:hover {
        background: #1e293b;
        border-color: rgba(103, 232, 249, 0.7);
      }
      [data-v1-company-card-action="1"] {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        min-height: 36px !important;
        padding: 0 !important;
        border-radius: 9px !important;
        cursor: pointer;
        transition: transform .15s ease, background .15s ease, border-color .15s ease;
      }
      [data-v1-company-card-action="1"] svg {
        width: 18px;
        height: 18px;
        pointer-events: none;
      }
      [data-v1-company-inquiry="1"] {
        border: 1px solid rgba(148, 163, 184, .34) !important;
        background: #0f172a !important;
        color: #cbd5e1 !important;
        margin-left: 8px !important;
      }
      [data-v1-company-inquiry="1"]:hover {
        background: #164e63 !important;
        border-color: #67e8f9 !important;
        color: #ffffff !important;
        transform: translateY(-1px);
      }
      [data-v1-company-delete="1"] {
        border: 1px solid rgba(248, 113, 113, .42) !important;
        background: rgba(239, 68, 68, .10) !important;
        color: #f87171 !important;
        margin-left: 8px !important;
      }
      [data-v1-company-delete="1"]:hover {
        background: #ef4444 !important;
        border-color: #fca5a5 !important;
        color: #fff !important;
        transform: translateY(-1px);
      }
      [data-v1-company-edit="1"] {
        order: 999;
        margin-left: auto !important;
        min-width: 86px;
        min-height: 38px;
        border: 1px solid rgba(103, 232, 249, 0.72) !important;
        border-radius: 8px !important;
        background: rgba(34, 211, 238, 0.16) !important;
        padding: 8px 16px !important;
        color: #a5f3fc !important;
        font-size: 13px !important;
        box-shadow: 0 6px 18px rgba(34, 211, 238, 0.12);
      }
      [data-v1-company-edit="1"]:hover {
        background: #22d3ee !important;
        color: #082f49 !important;
      }
      [data-v1-company-card="1"] [data-v1-company-header="1"] > p {
        font-size: 20px !important;
        line-height: 1.45 !important;
      }
      [data-v1-company-card="1"] [data-v1-company-header="1"] span,
      [data-v1-company-card="1"] [data-v1-company-meta="1"] {
        font-size: 14px !important;
        line-height: 1.55 !important;
      }
      [data-v1-company-persona-toggle="1"] {
        display: flex !important;
        width: 100% !important;
        align-items: center !important;
        justify-content: space-between !important;
        gap: 12px !important;
        margin-top: 16px !important;
        border: 0 !important;
        border-bottom: 1px solid rgba(51, 65, 85, .82) !important;
        background: transparent !important;
        padding: 0 0 10px !important;
        color: #67e8f9 !important;
        font-size: 16px !important;
        font-weight: 900 !important;
        text-align: left !important;
        cursor: pointer !important;
      }
      [data-v1-company-persona-toggle="1"]:hover {
        color: #a5f3fc !important;
      }
      [data-v1-company-persona-arrow="1"] {
        display: inline-block;
        color: #cbd5e1;
        font-size: 18px;
        line-height: 1;
        transition: transform .18s ease;
      }
      [data-v1-company-persona-toggle="1"][aria-expanded="true"] [data-v1-company-persona-arrow="1"] {
        transform: rotate(180deg);
      }
      [data-v1-company-persona="1"] {
        height: 264px !important;
        min-height: 264px !important;
        margin-top: 10px !important;
      }
      [data-v1-company-persona="1"][hidden] {
        display: none !important;
      }
      [data-v1-company-persona="1"] p {
        font-size: 16px !important;
        line-height: 1.78 !important;
      }
      [data-v1-company-summary-source="1"],
      [data-v1-company-keyword-source-line="1"] {
        display: none !important;
      }
      [data-v1-company-summary="1"] {
        display: grid;
        gap: 10px;
        margin-top: 16px;
        border: 1px solid #1e293b;
        border-radius: 16px;
        background: rgba(15, 23, 42, 0.72);
        padding: 15px 16px;
      }
      [data-v1-company-summary-row="1"] {
        display: grid;
        grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.55fr) minmax(0, 1fr);
        gap: 16px;
        align-items: start;
      }
      [data-v1-company-summary-row="2"],
      [data-v1-company-summary-row="3"] {
        display: grid;
        grid-template-columns: 92px minmax(0, 1fr);
        gap: 12px;
        align-items: start;
      }
      .sm-v1-company-summary-item {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: 9px;
        min-width: 0;
        font-size: 16px;
        line-height: 1.55;
      }
      .sm-v1-company-summary-label {
        color: #67e8f9;
        font-weight: 900;
        white-space: nowrap;
      }
      .sm-v1-company-summary-value {
        min-width: 0;
        color: #e2e8f0;
        font-weight: 750;
        overflow-wrap: anywhere;
      }
      .sm-v1-company-summary-wide-label {
        color: #67e8f9;
        font-size: 14px;
        font-weight: 900;
        line-height: 1.55;
        white-space: nowrap;
      }
      .sm-v1-company-summary-wide-value {
        color: #e2e8f0;
        font-size: 16px;
        font-weight: 750;
        line-height: 1.55;
        overflow-wrap: anywhere;
      }
      [data-v1-keyword-source="1"] {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
      }
      .${KEYWORD_EDITOR_CLASS} {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
        gap: 8px;
        margin-top: 8px;
      }
      .${KEYWORD_EDITOR_CLASS} input {
        width: 100%;
        min-width: 0;
        min-height: 44px;
        border: 1px solid #334155;
        border-radius: 8px;
        background: #020617;
        padding: 10px 12px;
        color: #f8fafc;
        font-size: 14px;
        font-weight: 700;
        outline: none;
      }
      .${KEYWORD_EDITOR_CLASS} input::placeholder {
        color: #64748b;
      }
      .${KEYWORD_EDITOR_CLASS} input:focus {
        border-color: #22d3ee;
        box-shadow: 0 0 0 2px rgba(34, 211, 238, 0.2);
      }
      .${KEYWORD_EDITOR_CLASS}[data-theme="light"] input {
        border-color: #cbd5e1;
        background: rgba(255, 255, 255, 0.9);
        color: #0f172a;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
      }
      .${KEYWORD_EDITOR_CLASS}[data-theme="light"] input::placeholder {
        color: #94a3b8;
      }
      @media (max-width: 900px) {
        [data-v1-company-summary-row="1"] {
          grid-template-columns: 1fr;
          gap: 8px;
        }
      }
      @media (max-width: 640px) {
        [data-v1-company-summary="1"] {
          padding: 13px;
        }
        [data-v1-company-summary-row="2"],
        [data-v1-company-summary-row="3"] {
          grid-template-columns: 1fr;
          gap: 3px;
        }
        #${TOOLBAR_ID} button {
          width: 100%;
        }
        [data-v1-company-edit="1"] {
          min-width: 92px;
        }
        [data-v1-company-persona="1"] {
          height: 240px !important;
          min-height: 240px !important;
        }
        [data-v1-company-persona-toggle="1"] {
          font-size: 16px !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function parseKeywords(value) {
    return String(value || '')
      .split(',')
      .map((keyword) => keyword.trim())
      .filter(Boolean)
      .slice(0, 5);
  }

  function setReactInputValue(input, value) {
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value'
    )?.set;

    if (setter) setter.call(input, value);
    else input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function populateKeywordSlots(editor, value) {
    const keywords = parseKeywords(value);
    editor.querySelectorAll('input').forEach((slot, index) => {
      slot.value = keywords[index] || '';
    });
    editor.dataset.sourceValue = String(value || '');
    editor.dataset.dirty = '0';
  }

  function commitKeywordSlots(editor, source) {
    if (editor.dataset.dirty !== '1') return;
    const value = [...editor.querySelectorAll('input')]
      .map((input) => input.value.trim())
      .filter(Boolean)
      .join(', ');
    editor.dataset.sourceValue = value;
    editor.dataset.dirty = '0';
    setReactInputValue(source, value);
  }

  function installKeywordSlots(source, theme) {
    if (!source || source.dataset.v1KeywordSource === '1') return;

    const label = source.closest('label');
    if (!label) return;

    const editor = document.createElement('div');
    editor.className = KEYWORD_EDITOR_CLASS;
    editor.dataset.v1KeywordEditor = '1';
    editor.dataset.theme = theme;

    for (let index = 0; index < 5; index += 1) {
      const slot = document.createElement('input');
      slot.type = 'text';
      slot.autocomplete = 'off';
      slot.placeholder = `키워드 ${index + 1}`;
      slot.setAttribute('aria-label', `핵심 키워드 ${index + 1}`);
      slot.dataset.keywordIndex = String(index);

      slot.addEventListener('input', () => {
        editor.dataset.dirty = '1';
      });

      slot.addEventListener('blur', () => {
        slot.value = slot.value.trim();
      });

      slot.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        const next = editor.querySelector(
          `input[data-keyword-index="${index + 1}"]`
        );
        if (next) next.focus();
        else slot.blur();
      });

      editor.appendChild(slot);
    }

    editor.addEventListener('focusout', () => {
      requestAnimationFrame(() => {
        if (!editor.contains(document.activeElement)) {
          commitKeywordSlots(editor, source);
        }
      });
    });

    const form = source.closest('form');
    if (form && form.dataset.v1KeywordSubmitSync !== '1') {
      form.dataset.v1KeywordSubmitSync = '1';
      form.addEventListener('submit', () => {
        const currentEditor = form.querySelector(`.${KEYWORD_EDITOR_CLASS}`);
        const currentSource = form.querySelector('[data-v1-keyword-source="1"]');
        if (currentEditor && currentSource) {
          commitKeywordSlots(currentEditor, currentSource);
        }
      }, true);
    }

    source.dataset.v1KeywordSource = '1';
    source.tabIndex = -1;
    source.setAttribute('aria-hidden', 'true');
    label.insertAdjacentElement('afterend', editor);
    populateKeywordSlots(editor, source.value);
  }

  function syncKeywordSlots(source) {
    const editor = source?.closest('label')?.nextElementSibling;
    if (!editor?.matches(`.${KEYWORD_EDITOR_CLASS}`)) return;
    if (editor.contains(document.activeElement)) return;
    if (editor.dataset.sourceValue !== source.value) {
      populateKeywordSlots(editor, source.value);
    }
  }

  function tuneKeywordEditors() {
    const mypageDialog = [...document.querySelectorAll('[role="dialog"]')].find(
      (dialog) => Boolean(findExact(dialog, 'h2,h3', '마이페이지'))
    );
    const mypageKeywordLabel = mypageDialog
      ? [...mypageDialog.querySelectorAll('label')].find((label) => {
          const directText = [...label.childNodes]
            .filter((child) => child.nodeType === Node.TEXT_NODE)
            .map((child) => clean(child.nodeValue))
            .filter(Boolean);
          return directText.includes('핵심 키워드');
        })
      : null;
    const mypageSource = document.getElementById('mypage-keywords')
      || mypageKeywordLabel?.querySelector(':scope > input');
    if (mypageSource) {
      installKeywordSlots(mypageSource, 'dark');
      syncKeywordSlots(mypageSource);
    }

    document.querySelectorAll('form').forEach((form) => {
      const heading = findExact(form, 'h2,h3', '기존 업체 수정')
        || findExact(form, 'h2,h3', '신규 업체 저장');
      if (!heading) return;

      const keywordLabel = [...form.querySelectorAll('label')].find((label) => {
        const directText = [...label.childNodes]
          .filter((child) => child.nodeType === Node.TEXT_NODE)
          .map((child) => clean(child.nodeValue))
          .filter(Boolean);
        return directText.includes('키워드') || directText.includes('핵심 키워드');
      });
      const companySource = keywordLabel?.querySelector(':scope > input');
      if (!companySource) return;

      installKeywordSlots(companySource, 'light');
      syncKeywordSlots(companySource);
    });
  }

  function findCompanyHero() {
    const title = findExact(document, 'h1,h2,h3', '마이페이지 업체 자산');
    return title?.closest('section') || null;
  }

  function findListPanel(hero) {
    const layout = hero?.nextElementSibling;
    if (!layout) return null;

    return [...layout.children].find((child) => {
      const text = clean(child.textContent);
      return text.includes('업체 페르소나') || text.includes('등록된 업체가 없습니다');
    }) || layout.firstElementChild;
  }

  function closeInquiryFrame() {
    const overlay = document.getElementById(INQUIRY_OVERLAY_ID);
    if (!overlay) return;
    overlay.hidden = true;
    document.body.style.removeProperty('overflow');
  }

  function openInquiryFrame() {
    let overlay = document.getElementById(INQUIRY_OVERLAY_ID);
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = INQUIRY_OVERLAY_ID;
      overlay.hidden = true;
      overlay.setAttribute('role', 'dialog');
      overlay.setAttribute('aria-modal', 'true');
      overlay.setAttribute('aria-label', '문의하기');
      overlay.innerHTML = `<div class="sm-v1-inquiry-frame-shell"><button type="button" class="sm-v1-inquiry-frame-close" aria-label="문의하기 닫기">×</button><iframe title="문의하기 목록" loading="eager"></iframe></div>`;
      document.body.appendChild(overlay);

      overlay.addEventListener('click', (event) => {
        if (event.target === overlay || event.target.closest('.sm-v1-inquiry-frame-close')) closeInquiryFrame();
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !overlay.hidden) closeInquiryFrame();
      });
    }

    const frame = overlay.querySelector('iframe');
    if (frame && !frame.getAttribute('src')) frame.setAttribute('src', INQUIRY_FRAME_URL);
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    overlay.querySelector('.sm-v1-inquiry-frame-close')?.focus();
  }

  function installAddButton(hero, listPanel) {
    const sourceButton = findExact(hero, 'button', '신규 업체 등록');
    if (!sourceButton || !listPanel) return;

    let toolbar = document.getElementById(TOOLBAR_ID);
    if (!toolbar || toolbar.parentElement !== listPanel) {
      toolbar?.remove();
      toolbar = document.createElement('div');
      toolbar.id = TOOLBAR_ID;

      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = '추가 업체 등록';
      button.setAttribute('aria-label', '추가 업체 등록');
      button.addEventListener('click', () => {
        const currentHero = findCompanyHero();
        const currentSource = currentHero
          ? findExact(currentHero, 'button', '신규 업체 등록')
          : null;
        currentSource?.click();
      });

      toolbar.appendChild(button);
      listPanel.prepend(toolbar);
    }
  }

  function valueAfterLabel(root, labelText) {
    const label = findExact(root, 'span,p,div', labelText);
    if (!label) return '';
    const parent = label.parentElement;
    if (!parent) return '';
    const values = [...parent.querySelectorAll('p,span,div')]
      .filter((node) => node !== label && !node.contains(label))
      .map((node) => clean(node.textContent))
      .filter((value) => value && value !== labelText);
    return values[0] || '';
  }

  function buildCompanySummary(article, personaLabel) {
    const existing = article.querySelector('[data-v1-company-summary="1"]');
    const websiteLabel = findExact(article, 'span', '웹사이트');
    const source = websiteLabel?.parentElement?.parentElement || null;
    if (!source || source === article || !findExact(source, 'span', '글 길이')) return;

    const metaLine = [...article.querySelectorAll('p')].find((node) => clean(node.textContent).startsWith('지역:'));
    const keywordLine = [...article.querySelectorAll('p')].find((node) => clean(node.textContent).startsWith('키워드:'));
    const regionMatch = clean(metaLine?.textContent).match(/^지역:\s*(.*?)\s*·\s*수정일:/);
    const region = clean(regionMatch?.[1]) || '미입력';
    const website = valueAfterLabel(source, '웹사이트') || '미설정';
    const length = valueAfterLabel(source, '글 길이') || '미설정';
    const style = valueAfterLabel(source, '콘텐츠 스타일') || '미설정';
    const tones = valueAfterLabel(source, '기본 말투') || '미설정';
    const keywords = clean(keywordLine?.textContent).replace(/^키워드:\s*/, '') || '미설정';

    source.dataset.v1CompanySummarySource = '1';
    if (keywordLine) keywordLine.dataset.v1CompanyKeywordSourceLine = '1';

    const summary = existing || document.createElement('div');
    summary.dataset.v1CompanySummary = '1';
    summary.innerHTML = `
      <div data-v1-company-summary-row="1">
        <div class="sm-v1-company-summary-item"><span class="sm-v1-company-summary-label">지역</span><span class="sm-v1-company-summary-value">${esc(region)}</span></div>
        <div class="sm-v1-company-summary-item"><span class="sm-v1-company-summary-label">웹사이트</span><span class="sm-v1-company-summary-value">${esc(website)}</span></div>
        <div class="sm-v1-company-summary-item"><span class="sm-v1-company-summary-label">콘텐츠</span><span class="sm-v1-company-summary-value">${esc(style)} · ${esc(length)}</span></div>
      </div>
      <div data-v1-company-summary-row="2"><span class="sm-v1-company-summary-wide-label">기본 말투</span><span class="sm-v1-company-summary-wide-value">${esc(tones)}</span></div>
      <div data-v1-company-summary-row="3"><span class="sm-v1-company-summary-wide-label">키워드</span><span class="sm-v1-company-summary-wide-value">${esc(keywords)}</span></div>
    `;
    if (!existing) article.insertBefore(summary, personaLabel.parentElement || personaLabel);
  }

  function tuneCompanyCards(listPanel) {
    if (!listPanel) return;

    listPanel.querySelectorAll('article').forEach((article) => {
      const personaLabel = [...article.querySelectorAll('p,span,div')].find(
        (node) => clean(node.textContent) === '업체 페르소나'
          && !node.closest('[data-v1-company-persona-toggle="1"]')
      ) || null;
      if (!personaLabel) return;

      article.dataset.v1CompanyCard = '1';
      const personaBox = personaLabel.nextElementSibling;
      if (personaBox) {
        personaBox.dataset.v1CompanyPersona = '1';
        if (personaBox.dataset.v1CompanyPersonaReady !== '1') {
          personaBox.dataset.v1CompanyPersonaReady = '1';
          personaBox.hidden = true;
        }
      }
      buildCompanySummary(article, personaLabel);

      let personaToggle = article.querySelector('[data-v1-company-persona-toggle="1"]');
      if (!personaToggle && personaBox) {
        personaToggle = document.createElement('button');
        personaToggle.type = 'button';
        personaToggle.dataset.v1CompanyPersonaToggle = '1';
        personaToggle.setAttribute('aria-expanded', 'false');
        personaToggle.innerHTML = '<span>업체 페르소나</span><span data-v1-company-persona-arrow="1" aria-hidden="true">⌄</span>';
        personaToggle.addEventListener('click', () => {
          const expanded = personaToggle.getAttribute('aria-expanded') === 'true';
          personaToggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
          personaBox.hidden = expanded;
        });
        personaLabel.hidden = true;
        personaLabel.parentElement?.insertBefore(personaToggle, personaLabel);
      }

      const editButton = findExact(article, 'button', '수정');
      const header = editButton?.parentElement;
      if (!editButton || !header) return;

      header.dataset.v1CompanyHeader = '1';
      const metaLine = [...article.querySelectorAll('p')].find((node) => clean(node.textContent).startsWith('지역:'));
      if (metaLine) metaLine.dataset.v1CompanyMeta = '1';
      editButton.dataset.v1CompanyEdit = '1';
      if (header.lastElementChild !== editButton) header.appendChild(editButton);

      const deleteButton = findExact(article, 'button', '삭제');
      const actionRow = deleteButton?.parentElement;
      if (!deleteButton || !actionRow) return;

      deleteButton.dataset.v1CompanyCardAction = '1';
      deleteButton.dataset.v1CompanyDelete = '1';
      deleteButton.setAttribute('aria-label', '업체 삭제');
      deleteButton.setAttribute('title', '업체 삭제');
      deleteButton.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v5"/><path d="M14 11v5"/></svg>';

      let inquiryButton = actionRow.querySelector('[data-v1-company-inquiry="1"]');
      if (!inquiryButton) {
        inquiryButton = document.createElement('button');
        inquiryButton.type = 'button';
        inquiryButton.dataset.v1CompanyCardAction = '1';
        inquiryButton.dataset.v1CompanyInquiry = '1';
        inquiryButton.setAttribute('aria-label', '문의하기');
        inquiryButton.setAttribute('title', '문의하기');
        inquiryButton.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/><path d="M8 10h.01"/><path d="M12 10h.01"/><path d="M16 10h.01"/></svg>';
        inquiryButton.addEventListener('click', openInquiryFrame);
      }
      if (deleteButton.nextElementSibling !== inquiryButton) {
        deleteButton.insertAdjacentElement('afterend', inquiryButton);
      }
    });
  }

  function renameDirectText(container, before, after) {
    const node = [...container.childNodes].find(
      (child) => child.nodeType === Node.TEXT_NODE && clean(child.nodeValue) === before
    );
    if (node) node.nodeValue = after;
  }

  function directLabelText(label) {
    return [...label.childNodes]
      .filter((child) => child.nodeType === Node.TEXT_NODE)
      .map((child) => clean(child.nodeValue))
      .filter(Boolean)
      .join(' ');
  }

  function findLabel(form, names) {
    return [...form.querySelectorAll('label')].find((label) => {
      const value = directLabelText(label).replace(/^\*\s*/, '');
      return names.includes(value);
    }) || null;
  }

  function markRequired(label, title) {
    if (!label) return;
    [...label.childNodes]
      .filter((child) => child.nodeType === Node.TEXT_NODE)
      .forEach((child) => {
        if (clean(child.nodeValue).replace(/^\*\s*/, '') === title) child.nodeValue = `* ${title}`;
      });
    label.dataset.v1RequiredCompanyField = '1';
  }

  function tuneEditor(layout) {
    const form = layout?.querySelector('form');
    const heading = form && (
      findExact(form, 'h2,h3', '기존 업체 수정')
      || findExact(form, 'h2,h3', '신규 업체 저장')
      || findExact(form, 'h2,h3', '업체 등록 / 수정')
    );
    if (!form || !heading) return;

    heading.textContent = '업체 등록 / 수정';

    const labels = {
      '웹사이트': '홈페이지/SNS 선택',
      '콘텐츠 스타일': '기본 작성 채널',
      '키워드': '핵심 키워드',
      '업체 페르소나 내용': '페르소나 상세 설명'
    };

    form.querySelectorAll('label').forEach((label) => {
      Object.entries(labels).forEach(([before, after]) => {
        renameDirectText(label, before, after);
      });
    });

    const companyLabel = findLabel(form, ['업체명']);
    const regionLabel = findLabel(form, ['지역', '지역 필수']);
    const phoneLabel = findLabel(form, ['전화번호']);
    const keywordLabel = findLabel(form, ['핵심 키워드']);
    const personaLabel = findLabel(form, ['페르소나 상세 설명']);

    markRequired(companyLabel, '업체명');
    markRequired(regionLabel, directLabelText(regionLabel).replace(/^\*\s*/, '') || '지역');
    markRequired(phoneLabel, '전화번호');
    markRequired(keywordLabel, '핵심 키워드');
    markRequired(personaLabel, '페르소나 상세 설명');

    const requiredFields = [
      ['업체명', companyLabel?.querySelector('input,select,textarea')],
      ['지역', regionLabel?.querySelector('input,select,textarea')],
      ['전화번호', phoneLabel?.querySelector('input,select,textarea')],
      ['핵심 키워드', keywordLabel?.querySelector('input,select,textarea')],
      ['페르소나 상세 설명', personaLabel?.querySelector('input,select,textarea')]
    ];

    requiredFields.forEach(([, field]) => {
      if (field) field.required = true;
    });

    if (form.dataset.v1RequiredCompanyValidation !== '1') {
      form.dataset.v1RequiredCompanyValidation = '1';
      form.addEventListener('submit', (event) => {
        const editor = form.querySelector(`.${KEYWORD_EDITOR_CLASS}`);
        const source = form.querySelector('[data-v1-keyword-source="1"]');
        if (editor && source) commitKeywordSlots(editor, source);

        const missing = requiredFields
          .filter(([name, field]) => {
            const value = clean(field?.value);
            return name === '페르소나 상세 설명' ? value.length < 10 : !value;
          })
          .map(([name]) => name);

        if (!missing.length) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        window.alert(`필수 입력 항목을 확인해 주세요.\n\n누락: ${missing.join(', ')}\n\n* 표시 항목은 반드시 입력해야 합니다.`);
        requiredFields.find(([name]) => missing.includes(name))?.[1]?.focus();
      }, true);
    }

    const toneLabel = findExact(form, 'span', '기본 말투');
    if (toneLabel) toneLabel.textContent = '기본 감성 톤';

    const websiteInput = form.querySelector('input[value^="http"], input[placeholder="https://"]');
    if (websiteInput) {
      websiteInput.placeholder = '홈페이지, 블로그, 인스타그램, 스마트플레이스 URL';
    }

    const personaTextarea = form.querySelector('textarea');
    if (personaTextarea) {
      personaTextarea.placeholder = '경력, 전문 분야, 주요 고객, 말투, 지역, 차별점과 피할 표현을 구체적으로 작성하세요.';
    }
  }

  function apply() {
    ensureStyle();
    tuneKeywordEditors();

    const hero = findCompanyHero();
    if (!hero) return;

    const layout = hero.nextElementSibling;
    const listPanel = findListPanel(hero);

    installAddButton(hero, listPanel);
    tuneCompanyCards(listPanel);
    tuneEditor(layout);
    hero.dataset.v1CompanyHeroHidden = '1';
  }

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      apply();
    });
  }

  const root = document.getElementById('root') || document.body;
  new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
  window.addEventListener('popstate', schedule);
  document.addEventListener('click', schedule, true);
  document.addEventListener('change', schedule, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedule, { once: true });
  } else {
    schedule();
  }
})();
