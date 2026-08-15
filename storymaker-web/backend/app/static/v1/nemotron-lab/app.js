(() => {
  const $ = (q) => document.querySelector(q);
  const $$ = (q) => [...document.querySelectorAll(q)];

  let currentConvId = null;
  let isComposing = false;
  let activePersona = null;
  let approvedSourceProfile = null;
  let isGenerating = false;
  let lastUserPrompt = '';

  const toast = $('#toast');

  function notify(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(notify.t);
    notify.t = setTimeout(() => toast.classList.remove('show'), 2800);
  }

  // --- API Wrappers ---
  async function apiFetch(path, options = {}) {
    const savedToken = String(
      localStorage.getItem('storymaker_token') ||
      sessionStorage.getItem('storymaker_token') ||
      ''
    ).trim();
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };
    if (savedToken && !headers.Authorization) {
      headers.Authorization = `Bearer ${savedToken}`;
    }
    const apiBase = location.hostname === '127.0.0.1' || location.hostname === 'localhost' || location.port === '8011'
      ? '/api/nemotron-lab'
      : '/v1-api/nemotron-lab';
    const res = await fetch(apiBase + path, {
      ...options,
      credentials: 'include',
      headers
    });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (res.status === 401) {
      notify('로그인 세션이 필요합니다.');
      return { ok: false, message: '로그인 필요' };
    }
    if (!res.ok) {
      const errMsg = data?.detail || data?.message || `HTTP ${res.status}`;
      console.error(`[Nemotron API Error] ${options.method || 'GET'} ${path} -> HTTP ${res.status}:`, data);
      throw new Error(errMsg);
    }
    return data;
  }

  // --- Status Check & Personalized Greeting ---
  async function checkStatus() {
    try {
      const res = await apiFetch('/status');
      if (res?.ok && res?.data) {
        const d = res.data;
        const online = d.status === 'online';
        $('#statStatus').textContent = online ? 'ONLINE' : 'OFFLINE';
        $('#statRequests').textContent = `${d.usage?.requests || 0}건`;
        $('#statTokens').textContent = (d.usage?.total_tokens || 0).toLocaleString();
        $('#statLatency').textContent = `${((d.usage?.average_latency_ms || 0) / 1000).toFixed(2)}초`;
        
        const username = d.current_user?.username || '';
        if (username) {
          $('#currentUser').textContent = username;
          updatePersonalizedGreeting(username);
        }
      }
    } catch (e) {
      console.warn('[Nemotron] Status check warning:', e);
    }
  }

  // --- Models Loader ---
  async function loadModels() {
    const selector = $('#modelSelector');
    if (!selector) return;

    selector.disabled = true;
    selector.innerHTML = '<option>모델 불러오는 중...</option>';

    try {
      const response = await apiFetch('/models');
      const models = response?.data?.models || [];
      const defaultModel = 'nvidia/nemotron-mini-4b-instruct';

      selector.innerHTML = '';

      const nemotronModels = models.filter(m => {
        const id = typeof m === 'string' ? m : (m.id || '');
        return id.toLowerCase().includes('nemotron');
      });

      const list = nemotronModels.length ? nemotronModels : models;

      for (const m of list) {
        const id = typeof m === 'string' ? m : m.id;
        const name = typeof m === 'object' ? (m.name || id) : id;
        if (!id) continue;

        const option = document.createElement('option');
        option.value = id;
        option.textContent = name;
        option.selected = (id === defaultModel);
        selector.appendChild(option);
      }

      if (!selector.options.length) {
        selector.innerHTML = '<option value="nvidia/nemotron-mini-4b-instruct" selected>Nemotron Mini 4b Instruct</option>';
      }
    } catch (error) {
      console.error('[Nemotron] model load failed:', error);
      selector.innerHTML = '<option value="nvidia/nemotron-mini-4b-instruct" selected>Nemotron Mini 4b Instruct</option>';
    } finally {
      selector.disabled = false;
    }
  }

  async function updatePersonalizedGreeting(username) {
    try {
      const pRes = await apiFetch('/persona/source-profile');
      if (pRes?.ok && pRes?.data) {
        approvedSourceProfile = pRes.data;
        const compName = pRes.data.company_name || '';
        const nameTag = compName ? `${compName}의` : `${username}님,`;
        $('#welcomeGreeting').textContent = `안녕하세요! ${nameTag} 오늘 어떤 콘텐츠를 만들어볼까요?`;
      }
    } catch (_) {
      $('#welcomeGreeting').textContent = `안녕하세요! ${username}님, 오늘 어떤 콘텐츠를 만들어볼까요?`;
    }
  }

  // --- Conversations ---
  async function loadConversations() {
    try {
      const res = await apiFetch('/conversations');
      if (res?.ok && Array.isArray(res.data)) {
        renderConversationsList(res.data);
      }
    } catch (e) {
      console.warn('[Nemotron] Load conversations error:', e);
    }
  }

  function renderConversationsList(items) {
    const todayBox = $('#convToday');
    const prevBox = $('#convPrevious');
    todayBox.innerHTML = '';
    prevBox.innerHTML = '';

    const todayStr = new Date().toISOString().slice(0, 10);

    items.forEach(c => {
      const div = document.createElement('div');
      div.className = `conv-item ${c.id === currentConvId ? 'active' : ''}`;
      div.innerHTML = `<span>${escapeHtml(c.title || '새 대화')}</span><button class="btn-del" title="삭제">✕</button>`;
      
      div.onclick = (e) => {
        if (e.target.classList.contains('btn-del')) return;
        selectConversation(c.id, c.title);
      };

      div.querySelector('.btn-del').onclick = async (e) => {
        e.stopPropagation();
        if (confirm('이 대화를 삭제하시겠습니까?')) {
          await apiFetch(`/conversations/${c.id}`, { method: 'DELETE' });
          if (currentConvId === c.id) startNewChat();
          loadConversations();
        }
      };

      if (c.updated_at && c.updated_at.startsWith(todayStr)) {
        todayBox.appendChild(div);
      } else {
        prevBox.appendChild(div);
      }
    });
  }

  async function selectConversation(convId, title) {
    currentConvId = convId;
    $('#currentChatTitle').textContent = title || 'AI 비서';
    $('#welcomeScreen').classList.add('hidden');
    $('#messagesList').innerHTML = '';
    
    loadConversations();

    try {
      const res = await apiFetch(`/conversations/${convId}`);
      if (res?.ok && res?.data?.messages) {
        res.data.messages.forEach(m => appendMessageBubble(m.role, m.content));
        scrollToBottom();
      }
    } catch (e) {
      console.error('[Nemotron] Select conversation failed:', e);
      notify(`대화 내용을 불러오지 못했습니다: ${e.message}`);
    }
  }

  async function startNewChat() {
    currentConvId = null;
    $('#currentChatTitle').textContent = 'AI 비서';
    $('#welcomeScreen').classList.remove('hidden');
    $('#messagesList').innerHTML = '';
    $('#chatInput').value = '';
    $('#chatInput').focus();
    loadConversations();
  }

  // --- Persona ---
  async function loadActivePersona() {
    try {
      const res = await apiFetch('/persona');
      if (res?.ok && res?.data) {
        activePersona = res.data;
        $('#activePersonaTag')?.classList.add('hidden');
      } else {
        activePersona = null;
        $('#activePersonaTag')?.classList.add('hidden');
      }
    } catch (_) {}
  }

  // --- Unified Message Sending ---
  async function sendMessage(customPrompt) {
    const text = (customPrompt || $('#chatInput').value).trim();
    if (!text || isGenerating) return;

    lastUserPrompt = text;

    // Step 1: If no conversation ID, create new conversation first
    if (!currentConvId) {
      try {
        const newRes = await apiFetch('/conversations', {
          method: 'POST',
          body: JSON.stringify({ title: text.slice(0, 30) })
        });
        if (newRes?.ok && newRes?.data?.id) {
          currentConvId = newRes.data.id;
          $('#currentChatTitle').textContent = text.slice(0, 30);
        } else {
          console.error('[Nemotron] Conversation creation response invalid:', newRes);
          notify(`대화를 시작하지 못했습니다: ${newRes?.message || '응답 데이터 이상'}`);
          return;
        }
      } catch (e) {
        console.error('[Nemotron] Conversation creation failed:', e);
        notify(`대화를 시작하지 못했습니다: ${e.message}`);
        return;
      }
    }

    // Step 2: Render User Message Bubble
    $('#welcomeScreen').classList.add('hidden');
    if (!customPrompt) {
      appendMessageBubble('user', text);
      $('#chatInput').value = '';
      adjustTextareaHeight();
    }
    scrollToBottom();

    // Step 3: Send message to backend and render Nemotron Assistant Bubble
    isGenerating = true;
    $('#sendBtn').disabled = true;
    $('#sendBtnIcon').textContent = '...';

    const tempBotRow = appendMessageBubble('assistant', '네모트론 3 Ultra 답변을 생성 중입니다...');

    try {
      const mode = $('#settingMode').value || 'chat';
      const temp = Number($('#settingTemp').value) / 100;
      const maxTokens = Number($('#settingMaxTokens').value) || 2048;

      const res = await apiFetch(`/conversations/${currentConvId}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          prompt: text,
          model: $('#modelSelector').value,
          temperature: temp,
          max_tokens: maxTokens
        })
      });

      if (res?.ok && res?.data?.assistant_message) {
        const botContent = res.data.assistant_message.content;
        tempBotRow.querySelector('.msg-bubble').innerHTML = renderMarkdown(botContent);
        addMessageActions(tempBotRow, botContent);
        notify('답변이 완료되었습니다.');
      } else {
        tempBotRow.querySelector('.msg-bubble').textContent = `[오류] ${res?.message || '응답을 받지 못했습니다.'}`;
      }
    } catch (e) {
      console.error('[Nemotron] Message execution error:', e);
      tempBotRow.querySelector('.msg-bubble').textContent = `[통신 오류] ${e.message}`;
    } finally {
      isGenerating = false;
      $('#sendBtn').disabled = false;
      $('#sendBtnIcon').textContent = '↑';
      scrollToBottom();
      loadConversations();
      checkStatus();
    }
  }

  // --- UI Render Helpers ---
  function appendMessageBubble(role, content) {
    const list = $('#messagesList');
    const row = document.createElement('div');
    row.className = `msg-row ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.textContent = role === 'user' ? 'U' : 'N';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.innerHTML = renderMarkdown(content);

    if (role === 'user') {
      row.appendChild(bubble);
      row.appendChild(avatar);
    } else {
      row.appendChild(avatar);
      row.appendChild(bubble);
      addMessageActions(row, content);
    }

    list.appendChild(row);
    return row;
  }

  function addMessageActions(row, content) {
    const actions = document.createElement('div');
    actions.className = 'msg-actions';
    actions.innerHTML = `
      <button class="btn-msg-act copy-btn">📋 복사</button>
      <button class="btn-msg-act regen-btn">↻ 다시 생성</button>
    `;
    actions.querySelector('.copy-btn').onclick = () => {
      navigator.clipboard.writeText(content);
      notify('메시지가 복사되었습니다.');
    };
    actions.querySelector('.regen-btn').onclick = () => {
      if (lastUserPrompt) {
        sendMessage(lastUserPrompt);
      }
    };
    row.querySelector('.msg-bubble').appendChild(actions);
  }

  function renderMarkdown(text) {
    if (window.marked) {
      try { return marked.parse(text); } catch (_) {}
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
  }

  function escapeHtml(str) {
    return String(str || '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m]));
  }

  function scrollToBottom() {
    const container = $('#messagesContainer');
    container.scrollTop = container.scrollHeight;
  }

  function adjustTextareaHeight() {
    const ta = $('#chatInput');
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  }

  // --- Keyboard Handling (Step 9 Guidelines) ---
  const chatInput = $('#chatInput');

  chatInput.addEventListener('compositionstart', () => {
    isComposing = true;
  });

  chatInput.addEventListener('compositionend', () => {
    isComposing = false;
  });

  chatInput.addEventListener('input', adjustTextareaHeight);

  chatInput.addEventListener('keydown', (event) => {
    if (
      event.key !== 'Enter' ||
      event.shiftKey ||
      event.isComposing ||
      isComposing ||
      event.keyCode === 229
    ) {
      return;
    }

    event.preventDefault();

    if (!isGenerating) {
      sendMessage();
    }
  });

  // Focus on page load
  window.addEventListener('load', () => chatInput.focus());

  // --- Button Listeners ---
  $('#sendBtn').onclick = () => sendMessage();
  $('#newChatBtn').onclick = startNewChat;
  $('#newChatSidebarBtn').onclick = startNewChat;

  $('#sidebarToggleBtn').onclick = () => {
    $('#sidebar').classList.toggle('collapsed');
    $('#sidebar').classList.toggle('active');
  };

  // Quick Feature Chips
  $$('[data-sample]').forEach(btn => {
    btn.onclick = () => {
      const type = btn.dataset.sample;
      const presets = {
        blog: '블로그 홍보용 서두와 핵심 본문 구성을 작성해 주세요:\n\n',
        shorts: '15초 숏폼 영상용 강렬한 후킹 대본을 작성해 주세요:\n\n',
        sns: '인스타그램/카드뉴스용 대중적인 SNS 홍보 캡션을 작성해 주세요:\n\n',
        podcast: '라디오/팟캐스트 대화형 2인 대본을 작성해 주세요:\n\n',
        trans_en: '다음 문장을 세련되고 매끄러운 영어로 번역해 주세요:\n\n',
        rewrite: '다음 문장을 더 깔끔하고 인상적으로 교정해 주세요:\n\n'
      };
      chatInput.value = presets[type] || '';
      chatInput.focus();
      adjustTextareaHeight();
    };
  });

  $$('[data-preset]').forEach(card => {
    card.onclick = () => {
      const p = card.dataset.preset;
      const presets = {
        marketing: '울산 남구 소상공인을 위한 친근하고 정직한 느낌의 블로그 홍보 서두 문장을 작성해 줘.',
        summary: '다음 주요 소식과 핵심 사안을 요약해 주세요.',
        translate: 'StoryMaker V1은 독립된 AI 콘텐츠 제작 시스템입니다. 이 문장을 영어와 일본어로 번역해 줘.',
        rewrite: '다음 문장을 더 깔끔하고 인상적으로 교정해 줘.'
      };
      chatInput.value = presets[p] || '';
      chatInput.focus();
      adjustTextareaHeight();
    };
  });

  // Settings Modal
  $('#openSettingsBtn').onclick = () => $('#settingsModal').classList.remove('hidden');
  $('#closeSettingsBtn').onclick = () => $('#settingsModal').classList.add('hidden');
  $('#settingTemp').oninput = (e) => $('#settingTempVal').textContent = (Number(e.target.value) / 100).toFixed(2);

  // Persona Modal
  $('#openPersonaModalBtn').onclick = openPersonaModal;
  $('#inlinePersonaBtn').onclick = openPersonaModal;
  $('#closePersonaBtn').onclick = () => $('#personaModal').classList.add('hidden');

  async function openPersonaModal() {
    $('#personaModal').classList.remove('hidden');
    $('#personaStep1').classList.remove('hidden');
    $('#personaStep2').classList.add('hidden');

    try {
      const res = await apiFetch('/persona/source-profile');
      if (res?.ok && res?.data) {
        approvedSourceProfile = res.data;
        const d = res.data;
        $('#profilePreviewBox').innerHTML = `
          <strong>사용자명:</strong> ${escapeHtml(d.username)}<br>
          <strong>업체명:</strong> ${escapeHtml(d.company_name || '미설정')}<br>
          <strong>업종:</strong> ${escapeHtml(d.industry_label || d.industry_key || '일반')}<br>
          <strong>지역:</strong> ${escapeHtml(d.region || '전국')}<br>
          <strong>주요 서비스:</strong> ${escapeHtml(d.services || '없음')}<br>
          <strong>소개:</strong> ${escapeHtml(d.content_intro || '없음')}
        `;
      }
    } catch (e) {
      $('#profilePreviewBox').textContent = `프로필 정보를 불러오지 못했습니다: ${e.message}`;
    }
  }

  $('#generatePersonaBtn').onclick = async () => {
    notify('네모트론 3 Ultra가 페르소나를 생성하는 중입니다...');
    try {
      const draftRes = await apiFetch('/persona/source-profile');
      if (draftRes?.ok && draftRes?.data) {
        approvedSourceProfile = draftRes.data;
      }
      const genRes = await apiFetch('/persona/generate', {
        method: 'POST',
        body: JSON.stringify({ approved_profile: approvedSourceProfile || draftRes.data })
      });

      if (genRes?.ok && genRes?.data) {
        const p = genRes.data;
        $('#pRole').value = p.role || (approvedSourceProfile?.company_name ? `${approvedSourceProfile.company_name} 대표` : '전담 마케터');
        $('#pBusiness').value = p.business || approvedSourceProfile?.company_name || '';
        $('#pServices').value = p.services || approvedSourceProfile?.services || '';
        $('#pAudience').value = p.target_audience || '지역 고객층';
        $('#pRegion').value = p.region || approvedSourceProfile?.region || '전국';
        $('#pStrengths').value = p.strengths || '신뢰성 및 풍부한 경험';
        $('#pTone').value = p.tone || '친근하고 정중한 어조';
        $('#pContentDirection').value = p.content_direction || '실제 사례 중심 정보 전달';
        $('#pAvoidPhrases').value = p.avoid_phrases || '지나친 과장 광고 표현';
        $('#pGuideline').value = p.guideline || '자연스러운 한국어 및 지역 특성 반영';
        
        $('#personaStep1').classList.add('hidden');
        $('#personaStep2').classList.remove('hidden');
        notify('생성된 페르소나 10개 필드를 검토해 주세요.');
      }
    } catch (e) {
      notify('페르소나 생성 실패: ' + e.message);
    }
  };

  $('#reGeneratePersonaBtn').onclick = () => $('#generatePersonaBtn').click();

  $('#savePersonaBtn').onclick = async () => {
    const personaObj = {
      role: $('#pRole').value.trim(),
      business: $('#pBusiness').value.trim(),
      services: $('#pServices').value.trim(),
      target_audience: $('#pAudience').value.trim(),
      region: $('#pRegion').value.trim(),
      strengths: $('#pStrengths').value.trim(),
      tone: $('#pTone').value.trim(),
      content_direction: $('#pContentDirection').value.trim(),
      avoid_phrases: $('#pAvoidPhrases').value.trim(),
      guideline: $('#pGuideline').value.trim()
    };

    const realCompName = approvedSourceProfile?.company_name || $('#pBusiness').value.trim();
    const realIndKey = approvedSourceProfile?.industry_key || 'general';
    const realRegion = approvedSourceProfile?.region || $('#pRegion').value.trim();
    const realWebUrl = approvedSourceProfile?.website_url || '';

    try {
      const res = await apiFetch('/persona/save', {
        method: 'POST',
        body: JSON.stringify({
          company_name: realCompName,
          industry_key: realIndKey,
          region: realRegion,
          website_url: realWebUrl,
          persona: personaObj
        })
      });

      if (res?.ok) {
        notify('페르소나가 DB에 정상 저장 및 활성화되었습니다.');
        $('#personaModal').classList.add('hidden');
        loadActivePersona();
      }
    } catch (e) {
      notify('저장 실패: ' + e.message);
    }
  };

  const deactivatePersonaBtn = $('#deactivatePersonaBtn');
  if (deactivatePersonaBtn) deactivatePersonaBtn.onclick = async () => {
    try {
      const res = await apiFetch('/persona/deactivate', { method: 'POST' });
      if (res?.ok) {
        activePersona = null;
        $('#activePersonaTag')?.classList.add('hidden');
        notify('페르소나가 서버에서 비활성화되었습니다. 마이페이지 기본 정보가 기본 적용됩니다.');
      }
    } catch (e) {
      notify('비활성화 실패: ' + e.message);
    }
  };

  // Search filter
  $('#chatSearchInput').oninput = (e) => {
    const q = e.target.value.toLowerCase();
    $$('.conv-item').forEach(item => {
      const title = item.querySelector('span').textContent.toLowerCase();
      item.style.display = title.includes(q) ? 'flex' : 'none';
    });
  };

  // --- Initial Load ---
  checkStatus();
  loadModels();
  loadConversations();
  loadActivePersona();
  setInterval(checkStatus, 30000);
})();
