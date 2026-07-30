(() => {
  'use strict';

  const API_ROOT = '/v1-api/admin/industry-templates';
  const PANEL_CLASS = 'v1-industry-prompt-inline-panel';
  const BUTTON_CLASS = 'v1-industry-prompt-inline-button';

  function buttonStyle(button) {
    button.style.border = '1px solid rgb(103 232 249 / 0.55)';
    button.style.borderRadius = '0.5rem';
    button.style.padding = '0.375rem 0.75rem';
    button.style.fontSize = '0.875rem';
    button.style.fontWeight = '900';
    button.style.color = '#a5f3fc';
    button.style.background = 'rgb(8 145 178 / 0.12)';
    button.style.cursor = 'pointer';
    button.style.whiteSpace = 'nowrap';
  }

  async function readJson(response, fallback) {
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body.ok === false) {
      throw new Error(body.detail || body.message || `${fallback} · HTTP ${response.status}`);
    }
    return body.data || {};
  }

  async function loadPrompt(industryKey) {
    const response = await fetch(`${API_ROOT}/${encodeURIComponent(industryKey)}/prompt`, {
      credentials: 'include',
      cache: 'no-store'
    });
    return readJson(response, '프롬프트 조회 실패');
  }

  async function savePrompt(industryKey, content) {
    const response = await fetch(`${API_ROOT}/${encodeURIComponent(industryKey)}/prompt`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    });
    return readJson(response, '프롬프트 저장 실패');
  }

  function closeOtherPanels(exceptPanel) {
    document.querySelectorAll(`.${PANEL_CLASS}`).forEach((panel) => {
      if (panel !== exceptPanel) panel.remove();
    });
    document.querySelectorAll(`.${BUTTON_CLASS}`).forEach((button) => {
      if (!exceptPanel || button.dataset.industryKey !== exceptPanel.dataset.industryKey) {
        button.textContent = '프롬프트';
      }
    });
  }

  function makePanel(industryKey, industryName) {
    const panel = document.createElement('div');
    panel.className = PANEL_CLASS;
    panel.dataset.industryKey = industryKey;
    panel.style.borderTop = '1px solid rgb(14 116 144 / 0.5)';
    panel.style.background = '#f8fafc';
    panel.style.padding = '1.25rem';
    panel.style.color = '#0f172a';

    panel.innerHTML = `
      <div style="display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:0.75rem;margin-bottom:0.9rem;">
        <div>
          <div style="font-size:0.8rem;font-weight:900;color:#0e7490;letter-spacing:0.04em;">업종 전용 프롬프트</div>
          <div style="margin-top:0.25rem;font-size:1.25rem;font-weight:900;">${industryName}</div>
          <div data-role="meta" style="margin-top:0.35rem;font-size:0.8rem;font-weight:700;color:#64748b;">프롬프트를 불러오는 중입니다.</div>
        </div>
        <button type="button" data-role="close" style="border:1px solid #cbd5e1;border-radius:999px;padding:0.5rem 0.9rem;background:white;font-size:0.8rem;font-weight:900;color:#475569;cursor:pointer;">접기</button>
      </div>
      <textarea data-role="content" spellcheck="false" placeholder="이 업종에서 사용할 전체 프롬프트를 붙여넣으세요." style="display:block;width:100%;min-height:520px;resize:vertical;border:1px solid #bae6fd;border-radius:1rem;background:white;padding:1rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:0.88rem;line-height:1.65;color:#0f172a;outline:none;"></textarea>
      <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:0.75rem;margin-top:0.9rem;">
        <div data-role="status" style="font-size:0.82rem;font-weight:800;color:#64748b;">현재 업종 키: ${industryKey}</div>
        <button type="button" data-role="save" style="border:0;border-radius:999px;padding:0.72rem 1.35rem;background:#06b6d4;font-size:0.9rem;font-weight:900;color:#082f49;cursor:pointer;">프롬프트 저장</button>
      </div>
    `;
    return panel;
  }

  async function toggleEditor(button, rowContainer, industryKey, industryName) {
    const existing = rowContainer.querySelector(`:scope > .${PANEL_CLASS}`);
    if (existing) {
      existing.remove();
      button.textContent = '프롬프트';
      return;
    }

    const panel = makePanel(industryKey, industryName);
    closeOtherPanels(panel);
    rowContainer.appendChild(panel);
    button.textContent = '프롬프트 닫기';

    const textarea = panel.querySelector('[data-role="content"]');
    const meta = panel.querySelector('[data-role="meta"]');
    const status = panel.querySelector('[data-role="status"]');
    const saveButton = panel.querySelector('[data-role="save"]');

    panel.querySelector('[data-role="close"]').addEventListener('click', () => {
      panel.remove();
      button.textContent = '프롬프트';
    });

    saveButton.addEventListener('click', async () => {
      const content = textarea.value.trim();
      if (content.length < 500) {
        status.textContent = '프롬프트는 500자 이상 입력해 주세요.';
        status.style.color = '#be123c';
        return;
      }
      saveButton.disabled = true;
      saveButton.textContent = '저장 중';
      status.textContent = '업종 전용 프롬프트로 저장하고 있습니다.';
      status.style.color = '#475569';
      try {
        const data = await savePrompt(industryKey, content);
        meta.textContent = `전용 프롬프트 · ${data.prompt_key} · 버전 ${data.version}`;
        status.textContent = '저장 완료. 다음 콘텐츠 생성부터 이 업종에 적용됩니다.';
        status.style.color = '#047857';
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : '프롬프트 저장 실패';
        status.style.color = '#be123c';
      } finally {
        saveButton.disabled = false;
        saveButton.textContent = '프롬프트 저장';
      }
    });

    try {
      const data = await loadPrompt(industryKey);
      textarea.value = data.content || '';
      meta.textContent = `${data.inherited ? '공통 프롬프트 상속 중' : '업종 전용 프롬프트'} · ${data.prompt_key} · 버전 ${data.version}`;
      status.textContent = data.inherited
        ? '현재는 공통 프롬프트를 사용합니다. 저장하면 이 업종 전용으로 분리됩니다.'
        : '이 업종만 사용하는 전용 프롬프트입니다.';
      status.style.color = data.inherited ? '#a16207' : '#047857';
    } catch (error) {
      meta.textContent = '프롬프트 조회 실패';
      status.textContent = error instanceof Error ? error.message : '프롬프트 조회 실패';
      status.style.color = '#be123c';
    }
  }

  function enhanceRows() {
    const titleButtons = Array.from(document.querySelectorAll('button[title$=" 수정"]'));
    titleButtons.forEach((titleButton) => {
      const row = titleButton.closest('div.grid');
      const rowContainer = row?.parentElement;
      if (!row || !rowContainer || row.querySelector(`.${BUTTON_CLASS}`)) return;

      const cells = Array.from(row.children);
      const industryKey = String(cells[2]?.textContent || '').trim();
      const industryName = String(titleButton.textContent || '').trim();
      const managementCell = cells[4];
      if (!industryKey || !managementCell) return;

      const button = document.createElement('button');
      button.type = 'button';
      button.className = BUTTON_CLASS;
      button.dataset.industryKey = industryKey;
      button.textContent = '프롬프트';
      buttonStyle(button);
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleEditor(button, rowContainer, industryKey, industryName);
      });
      managementCell.appendChild(button);
    });
  }

  let scheduled = false;
  function scheduleEnhance() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      enhanceRows();
    });
  }

  const observer = new MutationObserver(scheduleEnhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', scheduleEnhance);
  scheduleEnhance();
})();
