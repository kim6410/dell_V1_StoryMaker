(() => {
  'use strict';

  if (window.__STORYMAKER_V1_COMPANY_INFO_UI_TUNE__) return;
  window.__STORYMAKER_V1_COMPANY_INFO_UI_TUNE__ = true;

  const TOOLBAR_ID = 'storymaker-v1-company-add-toolbar';
  const STYLE_ID = 'storymaker-v1-company-info-ui-style';
  const KEYWORD_EDITOR_CLASS = 'storymaker-v1-keyword-slots';
  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();

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
        font-size: 14px;
        font-weight: 900;
        cursor: pointer;
        box-shadow: 0 8px 24px rgba(34, 211, 238, 0.18);
      }
      #${TOOLBAR_ID} button:hover {
        background: #67e8f9;
        border-color: #a5f3fc;
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
      [data-v1-company-persona="1"] {
        height: 264px !important;
        min-height: 264px !important;
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
      @media (max-width: 640px) {
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

  function tuneCompanyCards(listPanel) {
    if (!listPanel) return;

    listPanel.querySelectorAll('article').forEach((article) => {
      const personaLabel = findExact(article, 'p,span,div', '업체 페르소나');
      if (!personaLabel) return;

      const personaBox = personaLabel.nextElementSibling;
      if (personaBox) personaBox.dataset.v1CompanyPersona = '1';

      const editButton = findExact(article, 'button', '수정');
      const header = editButton?.parentElement;
      if (!editButton || !header) return;

      editButton.dataset.v1CompanyEdit = '1';
      if (header.lastElementChild !== editButton) header.appendChild(editButton);
    });
  }

  function renameDirectText(container, before, after) {
    const node = [...container.childNodes].find(
      (child) => child.nodeType === Node.TEXT_NODE && clean(child.nodeValue) === before
    );
    if (node) node.nodeValue = after;
  }

  function tuneEditor(layout) {
    const form = layout?.querySelector('form');
    const heading = form && findExact(form, 'h2,h3', '기존 업체 수정')
      || form && findExact(form, 'h2,h3', '신규 업체 저장');
    if (!form || !heading) return;

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
