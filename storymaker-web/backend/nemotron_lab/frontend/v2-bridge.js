(() => {
  'use strict';

  const HOST_ID = 'storymaker-ai-lab2-host';
  const STYLE_ID = 'storymaker-ai-lab2-native-style';
  const LIVE_STYLE_ID = 'storymaker-ai-lab2-live-style';
  const API_ROOT = '/api/nemotron-lab';
  const MODEL_STORAGE_KEY = 'storymaker_nemotron_lab_model';

  const MODEL_REGISTRY = [
    {
      id: 'nvidia/nemotron-3-ultra-550b-a55b',
      name: 'Nemotron 3 Ultra',
      provider: 'NVIDIA',
      badge: 'FREE',
      billing: 'Free Endpoint 확인',
      description: '장기 추론·계획·에이전트·도구 호출용 플래그십 모델',
      recommended: true,
    },
    {
      id: 'z-ai/glm-5.2',
      name: 'GLM 5.2',
      provider: 'Z.ai',
      badge: 'FREE',
      billing: 'Free Endpoint 확인',
      description: '코딩·에이전트 워크플로우·장기 추론에 강한 모델',
      recommended: true,
    },
    {
      id: 'deepseek-ai/deepseek-v4-flash',
      name: 'DeepSeek V4 Flash',
      provider: 'DeepSeek AI',
      badge: 'FREE',
      billing: 'Free Endpoint 확인',
      description: '빠른 코딩·요약·에이전트 작업용 고속 MoE 모델',
      recommended: true,
    },
    {
      id: 'deepseek-ai/deepseek-v4-pro',
      name: 'DeepSeek V4 Pro',
      provider: 'DeepSeek AI',
      badge: 'ACCOUNT',
      billing: '계정 노출 모델',
      description: '정밀 추론과 복잡한 작업용 고성능 모델',
      recommended: false,
    },
    {
      id: 'nvidia/llama-3.3-nemotron-super-49b-v1.5',
      name: 'Llama 3.3 Nemotron Super',
      provider: 'NVIDIA',
      badge: 'ACCOUNT',
      billing: '계정 노출 모델',
      description: '대화·추론·도구 호출을 균형 있게 처리하는 범용 모델',
      recommended: false,
    },
    {
      id: 'nvidia/nemotron-3-super-120b-a12b',
      name: 'Nemotron 3 Super',
      provider: 'NVIDIA',
      badge: 'ACCOUNT',
      billing: '계정 노출 모델',
      description: '고품질 대화와 추론을 위한 중대형 Nemotron 모델',
      recommended: false,
    },
    {
      id: 'nvidia/nemotron-3-nano-30b-a3b',
      name: 'Nemotron 3 Nano',
      provider: 'NVIDIA',
      badge: 'ACCOUNT',
      billing: '계정 노출 모델',
      description: '빠른 응답과 반복 테스트에 적합한 경량 모델',
      recommended: false,
    },
  ];

  const state = {
    main: null,
    host: null,
    mode: 'chat',
    models: [],
    selectedModelId: localStorage.getItem(MODEL_STORAGE_KEY) || 'nvidia/nemotron-3-ultra-550b-a55b',
    status: null,
    usage: null,
    busy: false,
    ttsVoices: [],
    ttsLanguages: [],
    ttsObjectUrl: null,
    ttsBusy: false,
    countdownTimer: null,
    refreshTimer: null,
  };

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatNumber(value) {
    return new Intl.NumberFormat('ko-KR').format(Number(value || 0));
  }

  function renderInlineMarkdown(value) {
    let html = escapeHtml(value);
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>');
    html = html.replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
    return html;
  }

  function renderMarkdown(markdown) {
    const lines = String(markdown || '').replace(/\r\n?/g, '\n').split('\n');
    let html = '';
    let inCode = false;
    let codeLanguage = '';
    let listType = '';

    const closeList = () => {
      if (!listType) return;
      html += `</${listType}>`;
      listType = '';
    };

    for (const rawLine of lines) {
      const fence = rawLine.match(/^```\s*([\w#+.-]*)\s*$/);
      if (fence) {
        closeList();
        if (!inCode) {
          inCode = true;
          codeLanguage = fence[1] || '';
          html += `<pre><code${codeLanguage ? ` data-language="${escapeHtml(codeLanguage)}"` : ''}>`;
        } else {
          inCode = false;
          html += '</code></pre>';
        }
        continue;
      }

      if (inCode) {
        html += `${escapeHtml(rawLine)}\n`;
        continue;
      }

      if (!rawLine.trim()) {
        closeList();
        continue;
      }

      const heading = rawLine.match(/^(#{1,4})\s+(.+)$/);
      if (heading) {
        closeList();
        const level = heading[1].length;
        html += `<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`;
        continue;
      }

      if (/^\s*(---|___|\*\*\*)\s*$/.test(rawLine)) {
        closeList();
        html += '<hr>';
        continue;
      }

      const quote = rawLine.match(/^>\s?(.*)$/);
      if (quote) {
        closeList();
        html += `<blockquote>${renderInlineMarkdown(quote[1])}</blockquote>`;
        continue;
      }

      const unordered = rawLine.match(/^\s*[-*+]\s+(.+)$/);
      if (unordered) {
        if (listType !== 'ul') {
          closeList();
          listType = 'ul';
          html += '<ul>';
        }
        html += `<li>${renderInlineMarkdown(unordered[1])}</li>`;
        continue;
      }

      const ordered = rawLine.match(/^\s*\d+[.)]\s+(.+)$/);
      if (ordered) {
        if (listType !== 'ol') {
          closeList();
          listType = 'ol';
          html += '<ol>';
        }
        html += `<li>${renderInlineMarkdown(ordered[1])}</li>`;
        continue;
      }

      closeList();
      html += `<p>${renderInlineMarkdown(rawLine)}</p>`;
    }

    closeList();
    if (inCode) html += '</code></pre>';
    return html;
  }

  function scrollChatToBottom(smooth = false) {
    const thread = state.host?.querySelector('#lab2ChatThread');
    if (!thread) return;
    thread.scrollTo({ top: thread.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
  }

  function revealMarkdown(element, markdown) {
    const fullText = String(markdown || '표시할 응답이 없습니다.');
    const total = fullText.length;
    const chunkSize = total > 3000 ? 14 : total > 1600 ? 9 : total > 700 ? 6 : 3;
    const delay = total > 2500 ? 12 : 16;
    let index = 0;
    element.classList.add('typing');

    return new Promise((resolve) => {
      const step = () => {
        index = Math.min(total, index + chunkSize);
        element.innerHTML = renderMarkdown(fullText.slice(0, index));
        scrollChatToBottom(false);
        if (index < total) {
          window.setTimeout(step, delay);
        } else {
          element.classList.remove('typing');
          element.innerHTML = renderMarkdown(fullText);
          scrollChatToBottom(true);
          resolve();
        }
      };
      step();
    });
  }

  function createChatTurn(question, model) {
    const thread = state.host?.querySelector('#lab2ChatThread');
    if (!thread) return null;
    thread.querySelector('.lab2-chat-empty')?.remove();

    const turn = document.createElement('article');
    turn.className = 'lab2-chat-turn';
    turn.innerHTML = `
      <div class="lab2-chat-user"></div>
      <div class="lab2-chat-assistant">
        <div class="lab2-chat-head"><span>${escapeHtml(model?.name || 'AI 모델')}</span><span>응답 생성 중</span></div>
        <div class="lab2-chat-answer"><span class="lab2-chat-loading"><i></i><i></i><i></i></span></div>
        <div class="lab2-chat-meta"></div>
        <div class="lab2-chat-tools"></div>
      </div>`;
    turn.querySelector('.lab2-chat-user').textContent = question;
    thread.appendChild(turn);
    scrollChatToBottom(true);
    return turn;
  }

  async function finishChatTurn(turn, data) {
    if (!turn) return;
    const headStatus = turn.querySelector('.lab2-chat-head span:last-child');
    const answer = turn.querySelector('.lab2-chat-answer');
    const meta = turn.querySelector('.lab2-chat-meta');
    const tools = turn.querySelector('.lab2-chat-tools');
    if (headStatus) headStatus.textContent = '답변 중';
    answer.innerHTML = '';
    await revealMarkdown(answer, data.content || data.error || '표시할 응답이 없습니다.');
    if (headStatus) headStatus.textContent = '완료';
    meta.innerHTML = `
      <span>${formatNumber(data.input_tokens || 0)} input</span>
      <span>${formatNumber(data.output_tokens || 0)} output</span>
      <span>${formatNumber(data.total_tokens || 0)} total</span>
      <span>${formatNumber(data.latency_ms || 0)} ms</span>`;
    const ttsButton = document.createElement('button');
    ttsButton.type = 'button';
    ttsButton.textContent = '🔊 이 답변 음성으로 듣기';
    ttsButton.addEventListener('click', () => openTtsModal(data.content || ''));
    tools.replaceChildren(ttsButton);
    state.host.querySelector('#lab2LastLatency').textContent = `${formatNumber(data.latency_ms || 0)} ms`;
  }

  function failChatTurn(turn, message) {
    if (!turn) return;
    const headStatus = turn.querySelector('.lab2-chat-head span:last-child');
    const answer = turn.querySelector('.lab2-chat-answer');
    if (headStatus) headStatus.textContent = '오류';
    answer.classList.remove('typing');
    answer.innerHTML = `<p><strong>요청을 처리하지 못했습니다.</strong></p><p>${escapeHtml(message)}</p>`;
    scrollChatToBottom(true);
  }

  function ensureStyle() {
    if (!document.getElementById(STYLE_ID)) {
      const link = document.createElement('link');
      link.id = STYLE_ID;
      link.rel = 'stylesheet';
      link.href = '/static/v2/nemotron-lab/v2-native.css?v=20260715-native-1';
      document.head.appendChild(link);

      const liveLink = document.createElement('link');
      liveLink.id = 'storymaker-ai-lab2-layout-style';
      liveLink.rel = 'stylesheet';
      liveLink.href = '/static/v2/nemotron-lab/v2-live.css?v=20260718-persona-popup-2';
      document.head.appendChild(liveLink);
    }

    if (!document.getElementById(LIVE_STYLE_ID)) {
      const style = document.createElement('style');
      style.id = LIVE_STYLE_ID;
      style.textContent = `
        #${HOST_ID} .lab2-model-picker { cursor:pointer; position:relative; transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease; }
        #${HOST_ID} .lab2-model-picker:hover { transform:translateY(-2px); border-color:#2dd4bf; box-shadow:0 16px 34px rgba(9,18,38,.26); }
        #${HOST_ID} .lab2-model-picker::after { content:'모델 선택 ▾'; position:absolute; right:16px; bottom:14px; font-size:12px; font-weight:800; color:#5eead4; }
        #${HOST_ID} .lab2-model-badge { display:inline-flex; align-items:center; gap:6px; margin-left:8px; padding:3px 8px; border-radius:999px; font-size:10px; font-style:normal; letter-spacing:.04em; background:rgba(45,212,191,.14); color:#5eead4; border:1px solid rgba(45,212,191,.3); }
        #${HOST_ID} .lab2-model-badge.account { background:rgba(96,165,250,.12); color:#93c5fd; border-color:rgba(96,165,250,.28); }
        #${HOST_ID} .lab2-state.online i, #${HOST_ID} .lab2-dot.online { background:#34d399; box-shadow:0 0 12px rgba(52,211,153,.8); }
        #${HOST_ID} .lab2-state.loading i, #${HOST_ID} .lab2-dot.loading { background:#60a5fa; box-shadow:0 0 12px rgba(96,165,250,.8); }
        #${HOST_ID} .lab2-state.error i, #${HOST_ID} .lab2-dot.error { background:#fb7185; box-shadow:0 0 12px rgba(251,113,133,.8); }
        #${HOST_ID} .lab2-send:disabled { opacity:.55; cursor:wait; transform:none; }
        #${HOST_ID} .lab2-result-output { white-space:pre-wrap; word-break:break-word; line-height:1.75; font-size:15px; color:#dce8f8; }
        #${HOST_ID} .lab2-result-meta { display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }
        #${HOST_ID} .lab2-result-meta span { padding:5px 9px; border:1px solid rgba(148,163,184,.18); border-radius:8px; background:rgba(15,23,42,.58); color:#9fb1c9; font-size:11px; }
        #${HOST_ID} .lab2-activity-list { display:grid; gap:10px; }
        #${HOST_ID} .lab2-activity-item { padding:13px 14px; border:1px solid rgba(148,163,184,.14); border-radius:12px; background:rgba(8,17,32,.58); }
        #${HOST_ID} .lab2-activity-item strong { display:block; margin-bottom:6px; color:#e7eef9; font-size:13px; }
        #${HOST_ID} .lab2-activity-item p { margin:0 0 6px; color:#aebdd1; font-size:12px; line-height:1.5; }
        #${HOST_ID} .lab2-activity-item small { color:#71839b; font-size:10px; }
        #${HOST_ID} .lab2-modal[hidden] { display:none; }
        #${HOST_ID} .lab2-modal { position:fixed; inset:0; z-index:10020; display:grid; place-items:center; padding:22px; background:rgba(2,6,15,.76); backdrop-filter:blur(8px); }
        #${HOST_ID} .lab2-modal-panel { width:min(780px,96vw); max-height:82vh; overflow:auto; border:1px solid rgba(45,212,191,.32); border-radius:18px; background:#0a1628; box-shadow:0 28px 80px rgba(0,0,0,.46); }
        #${HOST_ID} .lab2-modal-head { position:sticky; top:0; z-index:2; display:flex; align-items:center; justify-content:space-between; gap:16px; padding:18px 20px; border-bottom:1px solid rgba(148,163,184,.14); background:rgba(10,22,40,.96); }
        #${HOST_ID} .lab2-modal-head h3 { margin:0; color:#f3f7fd; font-size:19px; }
        #${HOST_ID} .lab2-modal-head p { margin:4px 0 0; color:#8fa2ba; font-size:12px; }
        #${HOST_ID} .lab2-modal-close { border:0; background:transparent; color:#9fb1c9; font-size:24px; cursor:pointer; }
        #${HOST_ID} .lab2-model-list { display:grid; gap:10px; padding:16px; }
        #${HOST_ID} .lab2-model-option { display:grid; grid-template-columns:1fr auto; gap:12px; width:100%; padding:15px 16px; text-align:left; border:1px solid rgba(148,163,184,.15); border-radius:14px; background:rgba(13,27,48,.78); color:#e8eef8; cursor:pointer; }
        #${HOST_ID} .lab2-model-option:hover { border-color:rgba(45,212,191,.52); background:rgba(15,36,60,.95); }
        #${HOST_ID} .lab2-model-option.selected { border-color:#2dd4bf; box-shadow:inset 0 0 0 1px rgba(45,212,191,.25); }
        #${HOST_ID} .lab2-model-option:disabled { opacity:.42; cursor:not-allowed; }
        #${HOST_ID} .lab2-model-option strong { display:block; font-size:15px; }
        #${HOST_ID} .lab2-model-option p { margin:6px 0; color:#9fb1c9; font-size:12px; line-height:1.45; }
        #${HOST_ID} .lab2-model-option code { color:#6ee7d4; font-size:10px; word-break:break-all; }
        #${HOST_ID} .lab2-model-option aside { display:flex; flex-direction:column; align-items:flex-end; gap:7px; }
        #${HOST_ID} .lab2-model-option aside span { padding:4px 7px; border-radius:999px; font-size:10px; font-weight:800; background:rgba(45,212,191,.12); color:#5eead4; }
        #${HOST_ID} .lab2-model-option aside small { color:#71839b; white-space:nowrap; }
        #${HOST_ID} .lab2-refresh-models { margin:0 16px 16px; width:calc(100% - 32px); padding:10px 14px; border:1px solid rgba(96,165,250,.3); border-radius:10px; background:rgba(30,64,175,.12); color:#bfdbfe; cursor:pointer; }
        #${HOST_ID} .lab2-tts-button { border-color:rgba(167,139,250,.35); color:#ddd6fe; background:rgba(109,40,217,.12); }
        #${HOST_ID} .lab2-tts-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:16px 18px 4px; }
        #${HOST_ID} .lab2-tts-grid label, #${HOST_ID} .lab2-tts-text label { display:grid; gap:7px; color:#aebdd1; font-size:12px; font-weight:700; }
        #${HOST_ID} .lab2-tts-grid select, #${HOST_ID} .lab2-tts-text textarea { width:100%; border:1px solid rgba(148,163,184,.2); border-radius:11px; background:#081321; color:#e6eef9; padding:11px 12px; font:inherit; }
        #${HOST_ID} .lab2-tts-text { padding:12px 18px; }
        #${HOST_ID} .lab2-tts-text textarea { min-height:132px; resize:vertical; line-height:1.65; }
        #${HOST_ID} .lab2-tts-note { margin:0 18px 4px; padding:10px 12px; border-radius:10px; border:1px solid rgba(251,191,36,.24); background:rgba(120,53,15,.14); color:#fcd34d; font-size:11px; line-height:1.55; }
        #${HOST_ID} .lab2-tts-actions { display:flex; gap:10px; align-items:center; padding:12px 18px 16px; }
        #${HOST_ID} .lab2-tts-actions button { flex:1; padding:12px 14px; border:0; border-radius:10px; background:linear-gradient(135deg,#7c3aed,#2563eb); color:white; font-weight:800; cursor:pointer; }
        #${HOST_ID} .lab2-tts-actions button:disabled { opacity:.55; cursor:wait; }
        #${HOST_ID} .lab2-tts-result { margin:0 18px 18px; padding:14px; border:1px solid rgba(148,163,184,.17); border-radius:12px; background:rgba(7,16,30,.66); }
        #${HOST_ID} .lab2-tts-result[hidden] { display:none; }
        #${HOST_ID} .lab2-tts-result audio { width:100%; margin:8px 0 10px; }
        #${HOST_ID} .lab2-tts-result a { display:inline-flex; align-items:center; justify-content:center; padding:8px 11px; border-radius:8px; border:1px solid rgba(96,165,250,.28); color:#bfdbfe; text-decoration:none; font-size:11px; }
        #${HOST_ID} .lab2-tts-meta { margin-top:8px; color:#8294aa; font-size:10px; }
        #${HOST_ID} .lab2-chat-thread { min-height:280px; max-height:620px; overflow:auto; display:grid; gap:18px; margin:14px 0 18px; padding:18px; border:1px solid rgba(148,163,184,.14); border-radius:16px; background:linear-gradient(180deg,rgba(4,12,25,.72),rgba(8,19,35,.56)); scroll-behavior:smooth; }
        #${HOST_ID} .lab2-chat-empty { display:grid; place-items:center; min-height:220px; text-align:center; color:#7f91a8; }
        #${HOST_ID} .lab2-chat-empty strong { color:#dce8f8; font-size:15px; }
        #${HOST_ID} .lab2-chat-empty p { margin:7px 0 0; font-size:12px; line-height:1.55; }
        #${HOST_ID} .lab2-chat-turn { display:grid; gap:10px; animation:lab2TurnIn .28s ease both; }
        #${HOST_ID} .lab2-chat-user { justify-self:end; max-width:min(82%,760px); padding:12px 15px; border-radius:16px 16px 4px 16px; background:linear-gradient(135deg,#1d4ed8,#2563eb); color:#fff; white-space:pre-wrap; word-break:break-word; line-height:1.6; box-shadow:0 10px 24px rgba(37,99,235,.2); }
        #${HOST_ID} .lab2-chat-assistant { justify-self:start; width:min(92%,900px); padding:15px 17px; border:1px solid rgba(45,212,191,.18); border-radius:4px 16px 16px 16px; background:rgba(10,24,42,.92); color:#dce8f8; box-shadow:0 12px 28px rgba(0,0,0,.2); }
        #${HOST_ID} .lab2-chat-head { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:10px; color:#7dd3fc; font-size:11px; font-weight:800; }
        #${HOST_ID} .lab2-chat-head span:last-child { color:#71839b; font-weight:600; }
        #${HOST_ID} .lab2-chat-answer { min-height:24px; line-height:1.72; font-size:14px; word-break:break-word; }
        #${HOST_ID} .lab2-chat-answer.typing::after { content:'▍'; display:inline-block; margin-left:2px; color:#5eead4; animation:lab2Cursor .72s steps(1) infinite; }
        #${HOST_ID} .lab2-chat-answer p { margin:.62em 0; }
        #${HOST_ID} .lab2-chat-answer h1, #${HOST_ID} .lab2-chat-answer h2, #${HOST_ID} .lab2-chat-answer h3, #${HOST_ID} .lab2-chat-answer h4 { margin:1.05em 0 .48em; color:#f4f8ff; line-height:1.35; }
        #${HOST_ID} .lab2-chat-answer h1 { font-size:1.55em; } #${HOST_ID} .lab2-chat-answer h2 { font-size:1.35em; } #${HOST_ID} .lab2-chat-answer h3 { font-size:1.18em; }
        #${HOST_ID} .lab2-chat-answer ul, #${HOST_ID} .lab2-chat-answer ol { margin:.65em 0 .65em 1.4em; padding:0; }
        #${HOST_ID} .lab2-chat-answer li { margin:.3em 0; }
        #${HOST_ID} .lab2-chat-answer blockquote { margin:.8em 0; padding:9px 12px; border-left:3px solid #2dd4bf; background:rgba(45,212,191,.07); color:#b9cadc; }
        #${HOST_ID} .lab2-chat-answer pre { overflow:auto; margin:.85em 0; padding:13px 14px; border:1px solid rgba(148,163,184,.14); border-radius:11px; background:#050d19; color:#d8e5f5; }
        #${HOST_ID} .lab2-chat-answer code { padding:2px 5px; border-radius:5px; background:rgba(148,163,184,.12); color:#8ff3df; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.9em; }
        #${HOST_ID} .lab2-chat-answer pre code { padding:0; background:transparent; color:inherit; }
        #${HOST_ID} .lab2-chat-answer a { color:#7dd3fc; text-decoration:underline; text-underline-offset:3px; }
        #${HOST_ID} .lab2-chat-answer hr { border:0; border-top:1px solid rgba(148,163,184,.18); margin:1em 0; }
        #${HOST_ID} .lab2-chat-meta { display:flex; flex-wrap:wrap; gap:7px; margin-top:12px; color:#71839b; font-size:10px; }
        #${HOST_ID} .lab2-chat-meta span { padding:4px 7px; border:1px solid rgba(148,163,184,.13); border-radius:7px; background:rgba(2,8,18,.45); }
        #${HOST_ID} .lab2-chat-tools { display:flex; gap:8px; margin-top:10px; }
        #${HOST_ID} .lab2-chat-tools button { padding:6px 9px; border:1px solid rgba(167,139,250,.25); border-radius:8px; background:rgba(109,40,217,.1); color:#ddd6fe; font-size:10px; cursor:pointer; }
        #${HOST_ID} .lab2-chat-loading { display:inline-flex; gap:5px; align-items:center; min-height:22px; }
        #${HOST_ID} .lab2-chat-loading i { width:6px; height:6px; border-radius:999px; background:#5eead4; animation:lab2Dots 1s ease-in-out infinite; }
        #${HOST_ID} .lab2-chat-loading i:nth-child(2) { animation-delay:.16s; } #${HOST_ID} .lab2-chat-loading i:nth-child(3) { animation-delay:.32s; }
        #${HOST_ID} .lab2-enter-hint { display:flex; justify-content:flex-end; margin-top:7px; color:#71839b; font-size:10px; }
        #${HOST_ID} .lab2-tts-inline-slot[hidden] { display:none; }
        #${HOST_ID} .lab2-tts-inline-slot { margin-top:14px; }
        #${HOST_ID} .lab2-tts-inline-host { position:static; inset:auto; display:block; padding:0; background:transparent; backdrop-filter:none; }
        #${HOST_ID} .lab2-tts-inline-host .lab2-modal-panel { width:100%; max-height:none; overflow:visible; border-radius:14px; box-shadow:none; }
        #${HOST_ID} .lab2-results > article:first-child { display:none; }
        #${HOST_ID} .lab2-results { grid-template-columns:1fr; }
        @keyframes lab2TurnIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:none; } }
        @keyframes lab2Cursor { 50% { opacity:0; } }
        @keyframes lab2Dots { 0%,80%,100% { transform:translateY(0); opacity:.35; } 40% { transform:translateY(-5px); opacity:1; } }
        @media (max-width:900px) { #${HOST_ID} .lab2-modal { padding:10px; } #${HOST_ID} .lab2-model-option { grid-template-columns:1fr; } #${HOST_ID} .lab2-model-option aside { align-items:flex-start; } #${HOST_ID} .lab2-tts-grid { grid-template-columns:1fr; } #${HOST_ID} .lab2-chat-user { max-width:92%; } #${HOST_ID} .lab2-chat-assistant { width:100%; } }
      `;
      document.head.appendChild(style);
    }
  }

  function findMain() {
    const direct = document.querySelector('main > div > section');
    if (direct) return direct;
    const candidates = [...document.querySelectorAll('main > div > section, main section')]
      .map((element) => ({ element, rect: element.getBoundingClientRect() }))
      .filter(({ rect }) => rect.width > 480 && rect.height > 300)
      .sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height));
    return candidates[0]?.element || null;
  }

  function pageTemplate() {
    return `
      <div class="lab2-page">
        <section class="lab2-current">
          <div><small>현재 화면</small><strong>AI 연구실 2</strong></div>
          <button class="lab2-back" type="button" data-lab2-close>대시보드로 돌아가기</button>
        </section>

        <section class="lab2-hero">
          <div>
            <p class="lab2-kicker">NVIDIA MULTI MODEL CONTROL CENTER</p>
            <h1>네모트론 관제형 실험실</h1>
            <p>사용 가능한 NVIDIA 모델을 직접 선택해 대화·번역·프롬프트 품질을 비교합니다.</p>
            <div class="lab2-hero-summary" aria-label="AI 연구실 요약 상태">
              <span><small>서비스</small><b id="lab2ServiceState">확인 중</b></span>
              <span class="lab2-hero-model-picker" id="lab2ModelCard" tabindex="0" role="button" aria-label="사용할 모델 선택"><small>사용 모델</small><b id="lab2HeroModelCount">모델 선택</b></span>
              <span><small>오늘 요청</small><b id="lab2RequestCount">0건</b></span>
              <span><small>누적 토큰</small><b id="lab2TokenCount">0</b></span>
              <span><small>최근 응답</small><b id="lab2LastLatency">-</b></span>
            </div>
          </div>
          <span class="lab2-state loading" id="lab2TopState"><i></i> 연결 확인 중</span>
        </section>

        <section class="lab2-metrics">
          <article class="lab2-card lab2-metric"><label>서비스 상태 <em>LIVE</em></label><strong class="small" id="lab2ServiceState">확인 중</strong><p id="lab2ServiceDetail">NVIDIA Endpoint 연결 검사</p><span class="lab2-progress"><i></i></span></article>
          <article class="lab2-card lab2-metric lab2-model-picker" id="lab2ModelCardHidden">
            <label>선택 모델 <em>MODEL</em></label>
            <strong class="small" id="lab2ModelName">모델 불러오는 중</strong>
            <p id="lab2ModelDescription">계정에 노출된 모델을 확인합니다.</p>
            <code class="lab2-model-code" id="lab2ModelCode">—</code>
          </article>
          <article class="lab2-card lab2-metric"><label>오늘 요청 <em>24H</em></label><strong id="lab2RequestCount">0<small> 건</small></strong><p id="lab2RequestBreakdown">성공 0 · 실패 0 · 타임아웃 0</p></article>
          <article class="lab2-card lab2-metric"><label>누적 토큰 <em>TOKENS</em></label><strong id="lab2TokenCount">0</strong><p id="lab2TokenBreakdown">입력 0 · 출력 0</p></article>
          <article class="lab2-card lab2-metric"><label>자동 삭제 <em>23:59</em></label><strong id="lab2Countdown">--:--:--</strong><p>상세 대화·로그 자동 삭제</p><span class="lab2-progress"><i></i></span></article>
        </section>

        <section class="lab2-work">
          <article class="lab2-card">
            <header class="lab2-panel-head">
              <div><p>PROMPT WORKSPACE</p><h2>모델 선택형 직접 테스트</h2></div>
              <div class="lab2-tabs" role="tablist">
                <button class="lab2-tab active" type="button" data-mode="chat">대화하기</button>
                <button class="lab2-tab" type="button" data-mode="translate">번역하기</button>
                <button class="lab2-tab" type="button" data-mode="prompt">프롬프트 테스트</button>
                <button class="lab2-tab lab2-tts-button" type="button" id="lab2TtsOpen">🔊 TTS 테스트</button>
              </div>
            </header>
            <div class="lab2-body">
              <p class="lab2-desc" id="lab2Description">질문을 입력하고 선택한 모델의 한국어 이해력과 답변 품질을 확인합니다.</p>
              <div class="lab2-languages" id="lab2Languages" hidden>
                <label>원문 언어<select id="lab2Source"><option>자동 감지</option><option>한국어</option><option>영어</option><option>일본어</option><option>중국어</option></select></label>
                <button class="lab2-swap" type="button" id="lab2Swap">⇄</button>
                <label>번역 언어<select id="lab2Target"><option>영어</option><option>한국어</option><option>일본어</option><option>중국어</option><option>스페인어</option></select></label>
              </div>
              <div class="lab2-chat-thread" id="lab2ChatThread" aria-live="polite">
                <div class="lab2-chat-empty"><div><strong>대화를 시작해 보세요</strong><p>질문을 입력하고 Enter를 두 번 누르면 선택한 모델이 바로 답변합니다.</p></div></div>
              </div>
              <div class="lab2-prompt">
                <header><b>메시지 입력</b><span><span id="lab2Chars">0</span> / 12,000자</span></header>
                <textarea id="lab2Prompt" maxlength="12000" placeholder="질문을 입력하세요. Enter 두 번으로 전송하고, Shift+Enter는 줄바꿈입니다."></textarea>
                <div class="lab2-enter-hint">Enter 두 번 전송 · Shift+Enter 줄바꿈</div>
                <div class="lab2-chips">
                  <button type="button" id="lab2Persona" class="lab2-persona-trigger">페르소나</button>
                  <button type="button" data-sample="문장을 더 자연스럽고 신뢰감 있게 다듬어줘.">문장 다듬기</button>
                  <button type="button" data-sample="다음 내용을 핵심만 남겨 5줄로 요약해줘.">긴 글 요약</button>
                  <button type="button" data-sample="울산 지역 집수리 업체의 친근한 홍보 문구를 만들어줘.">홍보 문구</button>
                  <button type="button" data-sample="다음 한국어 문장을 자연스러운 영어로 번역해줘.">자연스러운 번역</button>
                  <button type="button" id="lab2Clear">입력 지우기</button>
                </div>
              </div>
              <div class="lab2-params">
                <label>창의성<input id="lab2Temperature" type="range" min="0" max="1" step="0.05" value="0.35"><b id="lab2TempValue">0.35</b></label>
                <label>최대 출력<select id="lab2MaxTokens"><option value="1024">1,024 토큰</option><option value="2048" selected>2,048 토큰</option><option value="4096">4,096 토큰</option></select><b></b></label>
                <label class="lab2-toggle">응답 저장<input id="lab2SaveToggle" type="checkbox" checked></label>
              </div>
              <div class="lab2-actions">
                <p><span>✓</span>Enter 두 번으로 전송됩니다. 버튼은 마우스·모바일용 보조 전송입니다.</p>
                <button class="lab2-send" type="button" id="lab2Send">메시지 보내기 →</button>
              </div>
              <div class="lab2-tts-inline-slot" id="lab2TtsInlineSlot" hidden></div>
            </div>
          </article>

          <aside class="lab2-card lab2-telemetry">
            <header class="lab2-panel-head"><div><p>LIVE TELEMETRY</p><h2>실시간 상태</h2></div><span class="lab2-state loading" id="lab2SideState"><i></i> CHECKING</span></header>
            <div class="lab2-radarbox"><div class="lab2-radar"></div><div><strong id="lab2RadarTitle">연결 확인 중</strong><small id="lab2RadarDetail">모델과 API 상태를 조회합니다.</small></div></div>
            <div class="lab2-health">
              <p><span><i class="lab2-dot loading" id="lab2EndpointDot"></i>NVIDIA Endpoint</span><b id="lab2EndpointText">확인 중</b></p>
              <p><span><i class="lab2-dot"></i>StoryMaker Queue</span><b>완전 분리</b></p>
              <p><span><i class="lab2-dot"></i>Gemini Worker</span><b>접근 차단</b></p>
              <p><span><i class="lab2-dot"></i>로그인 보호</span><b>서버 전용</b></p>
              <p><span><i class="lab2-dot warn"></i>Daily Purge</span><b>23:59 자동</b></p>
            </div>
            <div class="lab2-latency">
              <p><span>최근 응답</span><b id="lab2LastLatency">— ms</b></p>
              <p><span>평균 응답</span><b id="lab2AverageLatency">— sec</b></p>
              <p><span>성공률</span><b id="lab2SuccessRate">— %</b></p>
            </div>
          </aside>
        </section>

        <section class="lab2-results">
          <article class="lab2-card">
            <header class="lab2-panel-head"><div><p>MODEL RESPONSE</p><h2>응답 결과</h2></div></header>
            <div class="lab2-empty" id="lab2Result"><div class="lab2-orb"><i></i></div><strong>아직 실행된 요청이 없습니다</strong><p>모델을 선택하고 프롬프트를 입력한 뒤 실행하면 실제 결과가 표시됩니다.</p></div>
          </article>
          <article class="lab2-card">
            <header class="lab2-panel-head"><div><p>SESSION ACTIVITY</p><h2>최근 요청</h2></div></header>
            <div class="lab2-empty" id="lab2Activity"><div class="lab2-activity-icon">◌</div><strong>오늘 생성된 요청이 없습니다</strong><p>상세 내용은 매일 23:59에 자동 삭제됩니다.</p></div>
          </article>
        </section>

        <section class="lab2-card lab2-console">
          <header><span class="lab2-lights"><i></i><i></i><i></i></span><span>NEMOTRON LAB · ISOLATED CONSOLE</span><span id="lab2ConsoleState">CONNECTING</span></header>
          <div class="lab2-console-body" id="lab2Console"><p><b>[BOOT]</b> AI 연구실 2 전용 모듈을 초기화했습니다.</p><p><b>[SAFE]</b> 기존 v2 작업 큐와 Gemini Worker 접근은 차단되어 있습니다.</p></div>
        </section>

        <footer class="lab2-footer"><span>Nemotron Lab v1.0 · Native v2 module</span><span id="lab2User">로그인 사용자 확인 중</span><span>상세 기록 23:59 자동 삭제</span></footer>

        <div class="lab2-modal" id="lab2TtsModal" hidden>
          <div class="lab2-modal-panel" role="dialog" aria-modal="true" aria-labelledby="lab2TtsModalTitle">
            <header class="lab2-modal-head"><div><h3 id="lab2TtsModalTitle">Magpie 다국어 TTS 테스트</h3><p>언어와 음성을 선택해 WAV를 생성하고 바로 재생합니다.</p></div><button class="lab2-modal-close" type="button" data-tts-close>×</button></header>
            <div class="lab2-tts-grid">
              <label>언어<select id="lab2TtsLanguage"><option value="en-US">영어(미국)</option><option value="es-US">스페인어(미국)</option><option value="fr-FR">프랑스어</option><option value="de-DE">독일어</option><option value="zh-CN">중국어(간체)</option><option value="vi-VN">베트남어</option><option value="it-IT">이탈리아어</option><option value="hi-IN">힌디어</option><option value="ja-JP">일본어</option></select></label>
              <label>음성<select id="lab2TtsVoice"><option value="">음성 목록 불러오는 중</option></select></label>
              <label>샘플레이트<select id="lab2TtsRate"><option value="44100">44.1 kHz</option><option value="22050">22.05 kHz</option></select></label>
              <label>모델<select disabled><option>nvidia/magpie-tts-multilingual</option></select></label>
            </div>
            <p class="lab2-tts-note">Magpie Multilingual은 현재 한국어를 지원하지 않습니다. 한국어 원고는 먼저 번역 탭에서 지원 언어로 변환한 뒤 TTS를 실행해 주세요.</p>
            <div class="lab2-tts-text"><label>읽을 문장<textarea id="lab2TtsText" maxlength="2000" placeholder="예: Welcome to StoryMaker. Create your marketing content faster with AI."></textarea></label></div>
            <div class="lab2-tts-actions"><button type="button" id="lab2TtsRun">음성 생성하고 재생하기</button></div>
            <div class="lab2-tts-result" id="lab2TtsResult" hidden><strong id="lab2TtsResultTitle">음성 생성 완료</strong><audio id="lab2TtsAudio" controls preload="metadata"></audio><a id="lab2TtsDownload" href="#" download="nemotron-magpie-tts.wav">WAV 저장</a><p class="lab2-tts-meta" id="lab2TtsMeta"></p></div>
          </div>
        </div>

        <div class="lab2-modal" id="lab2PersonaModal" hidden>
          <div class="lab2-modal-panel lab2-persona-panel" role="dialog" aria-modal="true" aria-labelledby="lab2PersonaModalTitle">
            <header class="lab2-modal-head"><div><h3 id="lab2PersonaModalTitle">네모트론 페르소나 초안</h3><p>서버가 로그인 사용자의 업체 정보와 업종 기준을 읽어 조립한 휘발성 초안입니다.</p></div><button class="lab2-modal-close" type="button" data-persona-close>×</button></header>
            <div class="lab2-persona-warning" id="lab2PersonaWarning" hidden></div>
            <textarea id="lab2PersonaText" maxlength="12000" spellcheck="false"></textarea>
            <div class="lab2-persona-actions"><button type="button" data-persona-close>취소</button><button type="button" id="lab2PersonaInsert">입력하기</button></div>
          </div>
        </div>

        <div class="lab2-modal" id="lab2ModelModal" hidden>
          <div class="lab2-modal-panel" role="dialog" aria-modal="true" aria-labelledby="lab2ModelModalTitle">
            <header class="lab2-modal-head"><div><h3 id="lab2ModelModalTitle">사용 모델 선택</h3><p>현재 NVIDIA 계정에서 실제 노출된 모델만 선택할 수 있습니다.</p></div><button class="lab2-modal-close" type="button" data-model-close>×</button></header>
            <div class="lab2-model-list" id="lab2ModelList"></div>
            <button class="lab2-refresh-models" type="button" id="lab2RefreshModels">NVIDIA 모델 목록 새로고침</button>
          </div>
        </div>
      </div>`;
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_ROOT}${path}`, {
      credentials: 'include',
      cache: 'no-store',
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload || payload.ok === false) {
      const message = payload?.message || payload?.detail || payload?.data?.error || `HTTP ${response.status}`;
      throw new Error(String(message));
    }
    return payload.data ?? payload;
  }

  function addConsole(message, level = 'INFO') {
    const consoleBody = state.host?.querySelector('#lab2Console');
    if (!consoleBody) return;
    const p = document.createElement('p');
    const b = document.createElement('b');
    b.textContent = `[${level}]`;
    p.appendChild(b);
    p.append(` ${message}`);
    consoleBody.appendChild(p);
    while (consoleBody.children.length > 8) consoleBody.firstElementChild?.remove();
    consoleBody.scrollTop = consoleBody.scrollHeight;
  }

  function setConnectionState(kind, title, detail) {
    const online = kind === 'online';
    const error = kind === 'error';
    const loading = kind === 'loading';
    const stateClass = online ? 'online' : error ? 'error' : loading ? 'loading' : '';
    ['#lab2TopState', '#lab2SideState'].forEach((selector) => {
      const element = state.host?.querySelector(selector);
      if (!element) return;
      element.className = `lab2-state ${stateClass}`.trim();
      element.innerHTML = `<i></i> ${escapeHtml(online ? 'ONLINE' : error ? 'ERROR' : 'CHECKING')}`;
    });
    const serviceState = state.host?.querySelector('#lab2ServiceState');
    const serviceDetail = state.host?.querySelector('#lab2ServiceDetail');
    const endpointDot = state.host?.querySelector('#lab2EndpointDot');
    const endpointText = state.host?.querySelector('#lab2EndpointText');
    const radarTitle = state.host?.querySelector('#lab2RadarTitle');
    const radarDetail = state.host?.querySelector('#lab2RadarDetail');
    const consoleState = state.host?.querySelector('#lab2ConsoleState');
    if (serviceState) serviceState.textContent = title;
    if (serviceDetail) serviceDetail.textContent = detail;
    if (endpointDot) endpointDot.className = `lab2-dot ${stateClass}`.trim();
    if (endpointText) endpointText.textContent = online ? '정상 연결' : error ? '연결 오류' : '확인 중';
    if (radarTitle) radarTitle.textContent = title;
    if (radarDetail) radarDetail.textContent = detail;
    if (consoleState) consoleState.textContent = online ? 'ONLINE' : error ? 'ERROR' : 'CONNECTING';
  }

  function getSelectedModel() {
    return state.models.find((model) => model.id === state.selectedModelId) || state.models[0] || null;
  }

  function renderSelectedModel() {
    const model = getSelectedModel();
    const name = state.host?.querySelector('#lab2ModelName');
    const description = state.host?.querySelector('#lab2ModelDescription');
    const code = state.host?.querySelector('#lab2ModelCode');
    const heroModel = state.host?.querySelector('#lab2HeroModelCount');
    if (!model) {
      if (name) name.textContent = '선택 가능한 모델 없음';
      if (description) description.textContent = 'NVIDIA 계정 모델 목록을 다시 확인해 주세요.';
      if (code) code.textContent = '—';
      if (heroModel) heroModel.textContent = '선택 가능한 모델 없음';
      return;
    }
    if (name) name.innerHTML = `${escapeHtml(model.name)} <em class="lab2-model-badge ${model.badge === 'FREE' ? '' : 'account'}">${escapeHtml(model.badge)}</em>`;
    if (description) description.textContent = model.description;
    if (code) code.textContent = model.id;
    if (heroModel) heroModel.textContent = model.name;
  }

  function renderModelList() {
    const list = state.host?.querySelector('#lab2ModelList');
    if (!list) return;
    if (!state.models.length) {
      list.innerHTML = '<div class="lab2-empty"><strong>선택 가능한 모델이 없습니다</strong><p>NVIDIA API 상태와 계정 권한을 확인해 주세요.</p></div>';
      return;
    }
    list.innerHTML = state.models.map((model) => `
      <button class="lab2-model-option ${model.id === state.selectedModelId ? 'selected' : ''}" type="button" data-model-id="${escapeHtml(model.id)}">
        <div><strong>${escapeHtml(model.name)}</strong><p>${escapeHtml(model.description)}</p><code>${escapeHtml(model.id)}</code></div>
        <aside><span>${escapeHtml(model.badge)}</span><small>${escapeHtml(model.billing)}</small></aside>
      </button>`).join('');
    list.querySelectorAll('[data-model-id]').forEach((button) => {
      button.addEventListener('click', () => {
        state.selectedModelId = button.dataset.modelId || state.selectedModelId;
        localStorage.setItem(MODEL_STORAGE_KEY, state.selectedModelId);
        renderSelectedModel();
        renderModelList();
        closeModelModal();
        addConsole(`모델을 ${getSelectedModel()?.name || state.selectedModelId}(으)로 변경했습니다.`, 'MODEL');
      });
    });
  }

  function renderTtsVoices() {
    const language = state.host?.querySelector('#lab2TtsLanguage')?.value || 'en-US';
    const select = state.host?.querySelector('#lab2TtsVoice');
    if (!select) return;
    const group = state.ttsLanguages.find((item) => item.code === language);
    const voices = Array.isArray(group?.voices) ? group.voices : [];
    if (!voices.length) {
      select.innerHTML = '<option value="">사용 가능한 음성 없음</option>';
      return;
    }
    select.innerHTML = voices.map((voice) => `<option value="${escapeHtml(voice)}">${escapeHtml(voice.replace('Magpie-Multilingual.', ''))}</option>`).join('');
    const preferred = voices.find((voice) => !/\.(Angry|Calm|Fearful|Happy|Neutral|Sad|Disgust|PleasantSurprised)$/.test(voice)) || voices[0];
    select.value = preferred;
  }

  async function loadTtsVoices(force = false) {
    const select = state.host?.querySelector('#lab2TtsVoice');
    if (select) select.innerHTML = '<option value="">음성 목록 불러오는 중</option>';
    try {
      const data = await api(`/tts/voices${force ? '?refresh=true' : ''}`);
      state.ttsVoices = Array.isArray(data.voices) ? data.voices : [];
      state.ttsLanguages = Array.isArray(data.languages) ? data.languages : [];
      renderTtsVoices();
      addConsole(`Magpie TTS 음성 ${state.ttsVoices.length}개를 확인했습니다.`, 'TTS');
      return data;
    } catch (error) {
      if (select) select.innerHTML = '<option value="">음성 목록 조회 실패</option>';
      addConsole(error.message, 'ERROR');
      throw error;
    }
  }

  async function openTtsModal(initialText = '') {
    const modal = state.host?.querySelector('#lab2TtsModal');
    const slot = state.host?.querySelector('#lab2TtsInlineSlot');
    if (!modal || !slot) return;
    modal.classList.add('lab2-tts-inline-host');
    slot.appendChild(modal);
    slot.hidden = false;
    modal.hidden = false;
    const sourceText = String(initialText || state.host.querySelector('#lab2Prompt')?.value || '').trim();
    const ttsText = state.host.querySelector('#lab2TtsText');
    if (sourceText) ttsText.value = sourceText.slice(0, 2000);
    if (!state.ttsLanguages.length) {
      try { await loadTtsVoices(false); } catch (_) { /* 화면에 오류 표시 */ }
    }
    slot.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function closeTtsModal() {
    const modal = state.host?.querySelector('#lab2TtsModal');
    const slot = state.host?.querySelector('#lab2TtsInlineSlot');
    if (modal) modal.hidden = true;
    if (slot) slot.hidden = true;
  }

  const TTS_LANGUAGE_NAMES = {
    'en-US': '영어',
    'es-US': '스페인어',
    'fr-FR': '프랑스어',
    'de-DE': '독일어',
    'zh-CN': '중국어 간체',
    'vi-VN': '베트남어',
    'it-IT': '이탈리아어',
    'hi-IN': '힌디어',
    'ja-JP': '일본어',
  };

  async function prepareTtsText(text, language) {
    if (!/[ㄱ-ㅎㅏ-ㅣ가-힣]/.test(text)) {
      return { text, translated: false };
    }
    const model = getSelectedModel();
    if (!model) throw new Error('자동 번역에 사용할 Nemotron 모델이 없습니다.');
    const targetLanguage = TTS_LANGUAGE_NAMES[language] || '영어';
    addConsole(`한국어 입력 감지 · ${targetLanguage}로 자동 번역합니다.`, 'TTS');
    const translated = await api('/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: 'translate',
        prompt: text,
        model: model.id,
        source_language: '한국어',
        target_language: targetLanguage,
        temperature: 0.15,
        max_tokens: 1024,
        stream: false,
      }),
    });
    const translatedText = String(translated?.content || '').trim();
    if (!translatedText) throw new Error('TTS용 자동 번역 결과가 비어 있습니다.');
    return { text: translatedText, translated: true, sourceText: text, targetLanguage };
  }

  async function synthesizeTts() {
    if (state.ttsBusy) return;
    const textArea = state.host?.querySelector('#lab2TtsText');
    const text = textArea?.value?.trim() || '';
    const language = state.host?.querySelector('#lab2TtsLanguage')?.value || 'en-US';
    const voice = state.host?.querySelector('#lab2TtsVoice')?.value || '';
    const sampleRate = Number(state.host?.querySelector('#lab2TtsRate')?.value || 44100);
    const runButton = state.host?.querySelector('#lab2TtsRun');
    const result = state.host?.querySelector('#lab2TtsResult');
    const audio = state.host?.querySelector('#lab2TtsAudio');
    const download = state.host?.querySelector('#lab2TtsDownload');
    const meta = state.host?.querySelector('#lab2TtsMeta');

    if (!text) {
      textArea?.focus();
      addConsole('TTS로 읽을 문장을 입력해 주세요.', 'WAIT');
      return;
    }
    if (!voice) {
      addConsole('사용 가능한 TTS 음성을 먼저 선택해 주세요.', 'WAIT');
      return;
    }

    state.ttsBusy = true;
    runButton.disabled = true;
    runButton.textContent = '음성 생성 중…';
    result.hidden = false;
    state.host.querySelector('#lab2TtsResultTitle').textContent = 'NVIDIA Magpie가 음성을 생성하고 있습니다';
    meta.textContent = '문장 길이에 따라 수십 초가 걸릴 수 있습니다.';
    audio.removeAttribute('src');
    download.href = '#';
    setConnectionState('loading', 'TTS 생성 중', `${language} · ${voice}`);
    addConsole(`Magpie TTS 요청을 전송했습니다 · ${language} · ${voice}`, 'TTS');

    try {
      const prepared = await prepareTtsText(text, language);
      if (prepared.translated) {
        state.host.querySelector('#lab2TtsResultTitle').textContent = `${prepared.targetLanguage} 자동 번역 완료 · 음성 생성 중`;
        meta.textContent = `번역문: ${prepared.text.slice(0, 240)}`;
        addConsole(`자동 번역 완료 · ${prepared.text.slice(0, 80)}`, 'TTS');
      }
      const response = await fetch(`${API_ROOT}/tts/synthesize`, {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: prepared.text,
          language,
          voice,
          sample_rate_hz: sampleRate,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || payload?.message || `HTTP ${response.status}`);
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error('빈 오디오가 반환되었습니다.');
      if (state.ttsObjectUrl) URL.revokeObjectURL(state.ttsObjectUrl);
      state.ttsObjectUrl = URL.createObjectURL(blob);
      audio.src = state.ttsObjectUrl;
      download.href = state.ttsObjectUrl;
      download.download = `magpie-tts-${language}-${Date.now()}.wav`;
      const latency = Number(response.headers.get('X-Nemotron-Latency-Ms') || 0);
      const bytes = Number(response.headers.get('X-Nemotron-Audio-Bytes') || blob.size);
      state.host.querySelector('#lab2TtsResultTitle').textContent = '음성 생성 완료';
      meta.textContent = `${formatNumber(bytes)} bytes · ${formatNumber(latency)} ms · ${sampleRate.toLocaleString()} Hz · ${voice}`;
      state.host.querySelector('#lab2LastLatency').textContent = `${formatNumber(latency)} ms`;
      addConsole(`TTS 생성 완료 · ${formatNumber(bytes)} bytes · ${formatNumber(latency)} ms`, 'DONE');
      await audio.play().catch(() => {});
      await refreshDashboard();
    } catch (error) {
      state.host.querySelector('#lab2TtsResultTitle').textContent = 'TTS 생성 실패';
      meta.textContent = error.message;
      setConnectionState('error', 'TTS 요청 실패', error.message);
      addConsole(error.message, 'ERROR');
      await refreshDashboard().catch(() => {});
    } finally {
      state.ttsBusy = false;
      runButton.disabled = false;
      runButton.textContent = '음성 생성하고 재생하기';
    }
  }

  function openModelModal() {
    renderModelList();
    const modal = state.host?.querySelector('#lab2ModelModal');
    if (modal) modal.hidden = false;
  }

  function closeModelModal() {
    const modal = state.host?.querySelector('#lab2ModelModal');
    if (modal) modal.hidden = true;
  }

  async function loadModels(force = false) {
    try {
      setConnectionState('loading', '모델 조회 중', 'NVIDIA 계정의 사용 가능 모델을 확인합니다.');
      const data = await api(`/models${force ? '?refresh=true' : ''}`);
      const remoteModels = Array.isArray(data.models) ? data.models : [];
      const remoteById = new Map(remoteModels.map((model) => [String(model.id), model]));
      state.models = MODEL_REGISTRY
        .filter((registered) => remoteById.has(registered.id))
        .map((registered) => ({ ...registered, remote: remoteById.get(registered.id) }));

      if (!state.models.some((model) => model.id === state.selectedModelId)) {
        state.selectedModelId = state.models[0]?.id || '';
        if (state.selectedModelId) localStorage.setItem(MODEL_STORAGE_KEY, state.selectedModelId);
      }
      renderSelectedModel();
      renderModelList();
      addConsole(`계정 모델 ${remoteModels.length}개 중 연구실 허용 모델 ${state.models.length}개를 확인했습니다.`, 'MODEL');
      return state.models;
    } catch (error) {
      state.models = [];
      renderSelectedModel();
      setConnectionState('error', '모델 조회 실패', error.message);
      addConsole(error.message, 'ERROR');
      throw error;
    }
  }

  function renderUsage(summary = {}) {
    state.usage = summary;
    const requests = Number(summary.requests || 0);
    const success = Number(summary.success || 0);
    const failed = Number(summary.failed || 0);
    const timeouts = Number(summary.timeouts || 0);
    const inputTokens = Number(summary.input_tokens || 0);
    const outputTokens = Number(summary.output_tokens || 0);
    const totalTokens = Number(summary.total_tokens || inputTokens + outputTokens);
    const avgMs = Number(summary.average_latency_ms || 0);
    const rate = requests ? Math.round((success / requests) * 100) : 0;

    state.host.querySelector('#lab2RequestCount').innerHTML = `${formatNumber(requests)}<small> 건</small>`;
    state.host.querySelector('#lab2RequestBreakdown').textContent = `성공 ${formatNumber(success)} · 실패 ${formatNumber(failed)} · 타임아웃 ${formatNumber(timeouts)}`;
    state.host.querySelector('#lab2TokenCount').textContent = formatNumber(totalTokens);
    state.host.querySelector('#lab2TokenBreakdown').textContent = `입력 ${formatNumber(inputTokens)} · 출력 ${formatNumber(outputTokens)}`;
    state.host.querySelector('#lab2AverageLatency').textContent = avgMs ? `${(avgMs / 1000).toFixed(2)} sec` : '— sec';
    state.host.querySelector('#lab2SuccessRate').textContent = requests ? `${rate} %` : '— %';
  }

  function renderRecent(items = []) {
    const container = state.host?.querySelector('#lab2Activity');
    if (!container) return;
    if (!items.length) {
      container.className = 'lab2-empty';
      container.innerHTML = '<div class="lab2-activity-icon">◌</div><strong>오늘 생성된 요청이 없습니다</strong><p>상세 내용은 매일 23:59에 자동 삭제됩니다.</p>';
      return;
    }
    container.className = 'lab2-activity-list';
    container.innerHTML = items.slice(0, 8).map((item) => {
      const status = item.status === 'completed' ? '성공' : item.status === 'timeout' ? '타임아웃' : '실패';
      const model = MODEL_REGISTRY.find((entry) => entry.id === item.model)?.name || item.model || '모델';
      const preview = item.response_preview || item.prompt_preview || item.error || '';
      return `<div class="lab2-activity-item"><strong>${escapeHtml(model)} · ${escapeHtml(status)}</strong><p>${escapeHtml(preview)}</p><small>${formatNumber(item.total_tokens || 0)} tokens · ${formatNumber(item.latency_ms || 0)} ms · ${escapeHtml(item.created_at || '')}</small></div>`;
    }).join('');
  }

  async function refreshDashboard() {
    try {
      const [statusData, usageData] = await Promise.all([
        api('/status'),
        api('/usage'),
      ]);
      state.status = statusData;
      const summary = usageData.summary || statusData.usage || {};
      renderUsage(summary);
      renderRecent(usageData.recent || []);
      const user = statusData.current_user;
      if (user) state.host.querySelector('#lab2User').textContent = `로그인 사용자 · ${user.username || user.id}`;
      const online = statusData.status === 'online' && statusData.enabled !== false;
      setConnectionState(online ? 'online' : 'error', online ? '정상 연결' : '연결 대기', online ? `선택 가능한 모델 ${state.models.length}개` : (statusData.last_error || 'NVIDIA API 상태를 확인해 주세요.'));
    } catch (error) {
      setConnectionState('error', '연결 오류', error.message);
      addConsole(error.message, 'ERROR');
    }
  }

  function setMode(mode) {
    state.mode = mode;
    state.host.querySelectorAll('[data-mode]').forEach((button) => button.classList.toggle('active', button.dataset.mode === mode));
    const description = state.host.querySelector('#lab2Description');
    const languages = state.host.querySelector('#lab2Languages');
    const send = state.host.querySelector('#lab2Send');
    if (mode === 'translate') {
      description.textContent = '원문의 의미와 감정을 유지하면서 선택한 언어로 자연스럽게 번역합니다.';
      languages.hidden = false;
      send.textContent = '선택 모델로 번역하기 →';
    } else if (mode === 'prompt') {
      description.textContent = '같은 프롬프트를 여러 모델로 실행해 지시 이행력과 결과 편차를 비교합니다.';
      languages.hidden = true;
      send.textContent = '프롬프트 테스트 실행 →';
    } else {
      description.textContent = '질문을 입력하고 선택한 모델의 한국어 이해력과 답변 품질을 확인합니다.';
      languages.hidden = true;
      send.textContent = '선택 모델에 보내기 →';
    }
  }

  function showResult(data) {
    const container = state.host.querySelector('#lab2Result');
    container.className = 'lab2-preview-result';
    container.innerHTML = '<div class="lab2-result-output"></div><div class="lab2-result-meta"></div>';
    container.querySelector('.lab2-result-output').textContent = data.content || data.error || '표시할 응답이 없습니다.';
    container.querySelector('.lab2-result-meta').innerHTML = `
      <span>${escapeHtml(getSelectedModel()?.name || data.model || '')}</span>
      <span>${formatNumber(data.input_tokens || 0)} input</span>
      <span>${formatNumber(data.output_tokens || 0)} output</span>
      <span>${formatNumber(data.total_tokens || 0)} total</span>
      <span>${formatNumber(data.latency_ms || 0)} ms</span>`;
    state.host.querySelector('#lab2LastLatency').textContent = `${formatNumber(data.latency_ms || 0)} ms`;
  }

  async function executeRequest() {
    if (state.busy) return;
    const prompt = state.host.querySelector('#lab2Prompt');
    const text = prompt.value.trim();
    const model = getSelectedModel();
    if (!text) {
      prompt.focus();
      addConsole('프롬프트를 입력해 주세요.', 'WAIT');
      return;
    }
    if (!model) {
      openModelModal();
      addConsole('사용할 모델을 먼저 선택해 주세요.', 'WAIT');
      return;
    }

    const send = state.host.querySelector('#lab2Send');
    const turn = createChatTurn(text, model);
    state.busy = true;
    send.disabled = true;
    send.textContent = '모델 응답 대기 중…';
    prompt.value = '';
    state.host.querySelector('#lab2Chars').textContent = '0';
    setConnectionState('loading', '요청 처리 중', `${model.name} 응답을 기다리고 있습니다.`);
    addConsole(`${model.name}에 ${state.mode} 요청을 전송했습니다.`, 'SEND');

    const body = {
      mode: state.mode,
      prompt: text,
      model: model.id,
      source_language: state.host.querySelector('#lab2Source').value,
      target_language: state.host.querySelector('#lab2Target').value,
      temperature: Number(state.host.querySelector('#lab2Temperature').value),
      max_tokens: Number(state.host.querySelector('#lab2MaxTokens').value),
      stream: false,
    };

    try {
      const data = await api('/execute', { method: 'POST', body: JSON.stringify(body) });
      await finishChatTurn(turn, data);
      addConsole(`응답 완료 · ${formatNumber(data.total_tokens || 0)} tokens · ${formatNumber(data.latency_ms || 0)} ms`, 'DONE');
      await refreshDashboard();
    } catch (error) {
      failChatTurn(turn, error.message);
      setConnectionState('error', '요청 실패', error.message);
      addConsole(error.message, 'ERROR');
      await refreshDashboard().catch(() => {});
    } finally {
      state.busy = false;
      send.disabled = false;
      setMode(state.mode);
    }
  }

  function formatPersonaDraftForReading(value) {
    const source = String(value || '').replace(/\r\n?/g, '\n').trim();
    if (!source) return '';

    const formattedLines = source.split('\n').map((rawLine) => {
      const line = rawLine.trimEnd();
      if (!line.trim()) return '';
      if (/^\s*(?:\[[^\]]+\]|\d+\.\s+|[-•]\s+)/.test(line)) return line;
      return line.replace(/\.\s+/g, '.\n\n');
    });

    return formattedLines
      .join('\n')
      .replace(/\n(?=\[[^\]]+\])/g, '\n\n')
      .replace(/\n(?=\d+\.\s+)/g, '\n\n')
      .replace(/\n(?=[-•]\s+)/g, '\n\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  async function openPersonaModal() {
    const modal = state.host?.querySelector('#lab2PersonaModal');
    const textarea = state.host?.querySelector('#lab2PersonaText');
    const warning = state.host?.querySelector('#lab2PersonaWarning');
    const button = state.host?.querySelector('#lab2Persona');
    if (!modal || !textarea || !warning || !button) return;

    modal.hidden = false;
    textarea.value = '';
    textarea.placeholder = '로그인 사용자의 업체 정보와 업종 기준을 불러오는 중입니다…';
    textarea.disabled = true;
    warning.hidden = false;
    warning.textContent = '페르소나 초안을 불러오는 중입니다.';
    button.disabled = true;
    button.textContent = '불러오는 중…';

    try {
      const data = await api('/persona-draft');
      textarea.value = formatPersonaDraftForReading(data.prompt);
      const missing = Array.isArray(data.missing) ? data.missing : [];
      if (missing.length) {
        warning.hidden = false;
        warning.textContent = `기초정보가 충분하지 않아 정확한 페르소나 생성이 어렵습니다. 누락 항목: ${missing.join(', ')}`;
      } else {
        warning.hidden = true;
        warning.textContent = '';
      }
      addConsole('로그인 사용자 기준 페르소나 초안을 불러왔습니다.', 'PERSONA');
    } catch (error) {
      warning.hidden = false;
      warning.textContent = `페르소나 초안을 불러오지 못했습니다. 팝업에서 직접 내용을 작성할 수 있습니다. 오류: ${error.message}`;
      textarea.value = '';
      addConsole(error.message, 'ERROR');
    } finally {
      textarea.disabled = false;
      textarea.placeholder = '업체 정보와 업종 기준을 바탕으로 만든 페르소나 초안을 확인하고 직접 수정하세요.';
      button.disabled = false;
      button.textContent = '페르소나';
      textarea.focus();
    }
  }

  function closePersonaModal() {
    const modal = state.host?.querySelector('#lab2PersonaModal');
    const textarea = state.host?.querySelector('#lab2PersonaText');
    const warning = state.host?.querySelector('#lab2PersonaWarning');
    if (modal) modal.hidden = true;
    if (textarea) textarea.value = '';
    if (warning) { warning.hidden = true; warning.textContent = ''; }
  }

  function insertPersonaPrompt() {
    const source = state.host?.querySelector('#lab2PersonaText');
    const prompt = state.host?.querySelector('#lab2Prompt');
    if (!source || !prompt) return;
    prompt.value = source.value.slice(0, 12000);
    state.host.querySelector('#lab2Chars').textContent = String(prompt.value.length);
    const maxTokens = state.host.querySelector('#lab2MaxTokens');
    if (maxTokens) maxTokens.value = '4096';
    closePersonaModal();
    prompt.focus();
    addConsole('페르소나 초안을 입력창에 넣었습니다. 자동 전송하지 않았습니다.', 'PERSONA');
  }

  function updateCountdown() {
    const now = new Date();
    const target = new Date(now);
    target.setHours(23, 59, 0, 0);
    if (target <= now) target.setDate(target.getDate() + 1);
    const seconds = Math.max(0, Math.floor((target.getTime() - now.getTime()) / 1000));
    const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
    const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
    const s = String(seconds % 60).padStart(2, '0');
    const output = state.host?.querySelector('#lab2Countdown');
    if (output) output.textContent = `${h}:${m}:${s}`;
  }

  function bind() {
    state.host.querySelector('[data-lab2-close]')?.addEventListener('click', closeLab);

    if (!window.__storyMakerLab2SidebarNavigationBound) {
      window.__storyMakerLab2SidebarNavigationBound = true;
      document.addEventListener('click', (event) => {
        if (!state.host) return;
        const clickable = event.target instanceof Element ? event.target.closest('a, button') : null;
        if (!clickable || state.host.contains(clickable)) return;
        const navigationArea = clickable.closest('aside, nav');
        if (!navigationArea) return;
        closeLab();
      }, true);
    }
    state.host.querySelectorAll('[data-mode]').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.mode || 'chat')));
    state.host.querySelectorAll('[data-sample]').forEach((button) => button.addEventListener('click', () => {
      const prompt = state.host.querySelector('#lab2Prompt');
      prompt.value = button.dataset.sample || '';
      state.host.querySelector('#lab2Chars').textContent = String(prompt.value.length);
      prompt.focus();
    }));
    const prompt = state.host.querySelector('#lab2Prompt');
    let lastEnterAt = 0;
    let composing = false;
    prompt.addEventListener('compositionstart', () => { composing = true; });
    prompt.addEventListener('compositionend', () => { composing = false; });
    prompt.addEventListener('input', () => { state.host.querySelector('#lab2Chars').textContent = String(prompt.value.length); });
    prompt.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' || event.shiftKey || event.isComposing || composing) return;
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault();
        prompt.value = prompt.value.replace(/\n+$/g, '').trimEnd();
        state.host.querySelector('#lab2Chars').textContent = String(prompt.value.length);
        executeRequest();
        return;
      }
      const now = Date.now();
      if (now - lastEnterAt <= 750) {
        event.preventDefault();
        lastEnterAt = 0;
        prompt.value = prompt.value.replace(/\n+$/g, '').trimEnd();
        state.host.querySelector('#lab2Chars').textContent = String(prompt.value.length);
        executeRequest();
      } else {
        lastEnterAt = now;
      }
    });
    state.host.querySelector('#lab2Persona')?.addEventListener('click', openPersonaModal);
    state.host.querySelectorAll('[data-persona-close]').forEach((button) => button.addEventListener('click', closePersonaModal));
    state.host.querySelector('#lab2PersonaInsert')?.addEventListener('click', insertPersonaPrompt);
    state.host.querySelector('#lab2PersonaModal')?.addEventListener('click', (event) => { if (event.target.id === 'lab2PersonaModal') closePersonaModal(); });
    state.host.querySelector('#lab2Clear')?.addEventListener('click', () => { prompt.value = ''; state.host.querySelector('#lab2Chars').textContent = '0'; prompt.focus(); });
    state.host.querySelector('#lab2Temperature')?.addEventListener('input', (event) => { state.host.querySelector('#lab2TempValue').textContent = event.target.value; });
    state.host.querySelector('#lab2Swap')?.addEventListener('click', () => {
      const source = state.host.querySelector('#lab2Source');
      const target = state.host.querySelector('#lab2Target');
      const previous = source.value;
      source.value = target.value;
      target.value = previous === '자동 감지' ? '한국어' : previous;
    });
    state.host.querySelector('#lab2Send')?.addEventListener('click', executeRequest);
    state.host.querySelector('#lab2TtsOpen')?.addEventListener('click', () => openTtsModal(''));
    state.host.querySelectorAll('[data-tts-close]').forEach((button) => button.addEventListener('click', closeTtsModal));
    state.host.querySelector('#lab2TtsModal')?.addEventListener('click', (event) => { if (event.target.id === 'lab2TtsModal') closeTtsModal(); });
    state.host.querySelector('#lab2TtsLanguage')?.addEventListener('change', renderTtsVoices);
    state.host.querySelector('#lab2TtsRun')?.addEventListener('click', synthesizeTts);
    const modelCard = state.host.querySelector('#lab2ModelCard');
    modelCard?.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      openModelModal();
    });
    modelCard?.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      openModelModal();
    });
    state.host.addEventListener('click', (event) => {
      const trigger = event.target instanceof Element ? event.target.closest('#lab2ModelCard') : null;
      if (!trigger || !state.host.contains(trigger)) return;
      event.preventDefault();
      event.stopPropagation();
      openModelModal();
    });
    state.host.querySelectorAll('[data-model-close]').forEach((button) => button.addEventListener('click', closeModelModal));
    state.host.querySelector('#lab2ModelModal')?.addEventListener('click', (event) => { if (event.target.id === 'lab2ModelModal') closeModelModal(); });
    state.host.querySelector('#lab2RefreshModels')?.addEventListener('click', async () => {
      const button = state.host.querySelector('#lab2RefreshModels');
      button.disabled = true;
      button.textContent = '모델 목록 새로고침 중…';
      try { await loadModels(true); await refreshDashboard(); } finally { button.disabled = false; button.textContent = 'NVIDIA 모델 목록 새로고침'; }
    });
  }

  async function initialise() {
    updateCountdown();
    state.countdownTimer = window.setInterval(updateCountdown, 1000);
    try {
      await loadModels(false);
      await refreshDashboard();
      state.refreshTimer = window.setInterval(refreshDashboard, 30000);
    } catch (_) {
      // 상세 오류는 화면 콘솔에 표시됩니다.
    }
  }

  function mount(main) {
    if (document.getElementById(HOST_ID)) return;
    ensureStyle();
    state.main = main;
    state.main.classList.add('sm-lab2-active');
    state.host = document.createElement('section');
    state.host.id = HOST_ID;
    state.host.setAttribute('aria-label', 'AI 연구실 2');
    state.host.dataset.mode = 'chat';
    state.host.innerHTML = pageTemplate();
    state.main.appendChild(state.host);
    bind();
    initialise();

    const url = new URL(window.location.href);
    url.searchParams.set('page', 'aiLab2');
    window.history.replaceState({}, '', url.pathname + url.search + url.hash);
  }

  function openLab() {
    if (document.getElementById(HOST_ID)) return;
    let attempts = 0;
    const timer = window.setInterval(() => {
      const main = findMain();
      attempts += 1;
      if (main) {
        window.clearInterval(timer);
        mount(main);
      } else if (attempts > 100) {
        window.clearInterval(timer);
      }
    }, 100);
  }

  function closeLab() {
    if (state.countdownTimer) window.clearInterval(state.countdownTimer);
    if (state.refreshTimer) window.clearInterval(state.refreshTimer);
    if (state.ttsObjectUrl) {
      URL.revokeObjectURL(state.ttsObjectUrl);
      state.ttsObjectUrl = null;
    }
    state.host?.remove();
    state.main?.classList.remove('sm-lab2-active');
    state.host = null;
    state.main = null;
    const url = new URL(window.location.href);
    url.searchParams.delete('page');
    window.history.replaceState({}, '', url.pathname + url.search + url.hash);
  }

  function applyLabNaming() {
    const root = document.body;
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const text = String(node.nodeValue || '').trim();
      if (!text) return;
      const parent = node.parentElement;
      const inSidebar = Boolean(parent?.closest('aside, nav'));
      if (text === 'AI 연구실' && !inSidebar) node.nodeValue = node.nodeValue.replace('AI 연구실', '체험 연구실');
      if (text === '네모트론 연구실') node.nodeValue = node.nodeValue.replace('네모트론 연구실', 'AI API 연구실');
      if (text === '체험 연구실' && inSidebar) node.nodeValue = node.nodeValue.replace('체험 연구실', '체험');
    });
  }

  applyLabNaming();
  const namingObserver = new MutationObserver(() => applyLabNaming());
  namingObserver.observe(document.documentElement, { childList: true, subtree: true });

  window.StoryMakerNemotronLab = { open: openLab, close: closeLab };
  const boot = () => {
    const page = new URLSearchParams(window.location.search).get('page');
    if (page === 'aiLab2') openLab();
  };
  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', boot, { once: true })
    : boot();
})();
