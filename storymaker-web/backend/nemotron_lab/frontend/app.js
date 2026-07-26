(() => {
  const embedded = window.self !== window.top || new URLSearchParams(location.search).get('embed') === '1';
  if (embedded) {
    document.documentElement.classList.add('embedded');
    document.body.classList.add('embedded');
  }
  const $ = (q) => document.querySelector(q);
  const $$ = (q) => [...document.querySelectorAll(q)];
  const prompt = $('#prompt');
  const result = $('#result');
  const meta = $('#meta');
  const activity = $('#activity');
  const toast = $('#toast');
  let mode = 'chat';

  function notify(message) {
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(notify.timer);
    notify.timer = setTimeout(() => toast.classList.remove('show'), 2400);
  }

  async function checkLogin() {
    try {
      const response = await fetch('/api/auth/me', { credentials: 'include', cache: 'no-store' });
      if (!response.ok) throw new Error('login required');
      const payload = await response.json();
      const user = payload?.data || payload?.user || payload;
      $('#currentUser').textContent = user?.username || user?.name || '로그인 사용자';
    } catch (_) {
      location.replace('/v2?page=nemotronLab');
    }
  }

  function updateClock() {
    const now = new Date();
    const target = new Date(now);
    target.setHours(23, 59, 0, 0);
    if (target <= now) target.setDate(target.getDate() + 1);
    const left = Math.max(0, target - now);
    const h = String(Math.floor(left / 3600000)).padStart(2, '0');
    const m = String(Math.floor(left % 3600000 / 60000)).padStart(2, '0');
    const s = String(Math.floor(left % 60000 / 1000)).padStart(2, '0');
    $('#countdown').textContent = `${h}:${m}:${s}`;
    const elapsed = (now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()) / 86400;
    $('#dayProgress').style.width = `${Math.max(2, elapsed * 100)}%`;
  }

  const modeInfo = {
    chat: ['질문 또는 요청', '네모트론에게 보내기', '자유롭게 질문하고 네모트론의 한국어 이해력과 답변 품질을 확인합니다.'],
    translate: ['번역할 원문', '번역하기', '원문과 목표 언어를 선택해 자연스러운 번역과 의역 품질을 확인합니다.'],
    prompt: ['테스트 프롬프트', '프롬프트 실행', '시스템 지시와 출력 형식을 포함한 프롬프트의 수행 품질을 실험합니다.']
  };

  $$('.tab').forEach((button) => button.addEventListener('click', () => {
    mode = button.dataset.mode;
    $$('.tab').forEach((item) => item.classList.toggle('active', item === button));
    $('#languages').classList.toggle('hidden', mode !== 'translate');
    $('#inputLabel').textContent = modeInfo[mode][0];
    $('#runLabel').textContent = modeInfo[mode][1];
    $('#description').textContent = modeInfo[mode][2];
  }));

  const samples = {
    rewrite: '다음 문장을 전문적이고 자연스럽게 다듬어 주세요. 핵심 의미는 유지하고 과장된 표현은 줄여 주세요.\n\n',
    summary: '다음 내용을 핵심 사실, 문제점, 다음 조치로 구분하여 간결하게 요약해 주세요.\n\n',
    marketing: '지역 고객이 신뢰할 수 있는 자연스러운 홍보 문구를 작성해 주세요. 지나친 광고 표현은 피하고 실제 도움이 되는 정보를 포함해 주세요.\n\n',
    translation: '다음 한국어 문장을 직역하지 말고 원래 감정과 맥락을 살려 자연스러운 영어로 번역해 주세요.\n\n'
  };

  $$('[data-sample]').forEach((button) => button.addEventListener('click', () => {
    prompt.value = samples[button.dataset.sample];
    prompt.dispatchEvent(new Event('input'));
    prompt.focus();
  }));

  prompt.addEventListener('input', () => $('#chars').textContent = prompt.value.length.toLocaleString());
  $('#clearInput').addEventListener('click', () => { prompt.value = ''; prompt.dispatchEvent(new Event('input')); prompt.focus(); });
  $('#temperature').addEventListener('input', (event) => $('#tempValue').textContent = (Number(event.target.value) / 100).toFixed(2));
  $('#swap').addEventListener('click', () => {
    const source = $('#sourceLang'); const target = $('#targetLang');
    if (source.value === 'auto') source.value = 'ko';
    const old = source.value; source.value = target.value; target.value = old;
  });

  const langMap = { auto: '자동 감지', ko: '한국어', en: '영어', ja: '일본어', zh: '중국어', vi: '베트남어' };

  async function checkApiStatus() {
    try {
      const response = await fetch('/api/nemotron-lab/status', { credentials: 'include', cache: 'no-store' });
      if (!response.ok) return;
      const json = await response.json();
      if (json?.ok && json?.data) {
        const data = json.data;
        if (data.status === 'online') {
          const preview = document.querySelector('.preview');
          if (preview) { preview.innerHTML = '<i></i>LIVE · NEMOTRON 3 ULTRA ONLINE'; preview.style.color = '#10b981'; }
          const metricDanger = document.querySelector('.metric.danger strong');
          if (metricDanger) { metricDanger.textContent = '연결 완료'; metricDanger.style.color = '#10b981'; }
          const metricDangerText = document.querySelector('.metric.danger p');
          if (metricDangerText) { metricDangerText.textContent = 'NVIDIA API Catalog 정상 연결'; }
          const telemetryOffline = document.querySelector('.telemetry .offline');
          if (telemetryOffline) { telemetryOffline.innerHTML = '<i style="background:#10b981;"></i>ONLINE'; telemetryOffline.style.color = '#10b981'; }
          const radarBoxSmall = document.querySelector('.radarbox small');
          if (radarBoxSmall) { radarBoxSmall.textContent = `기본 모델: ${data.default_model || 'Nemotron 3 Ultra'}`; }
          $('#console')?.insertAdjacentHTML('beforeend', `<p><time>CONNECT</time><b>[ONLINE]</b> NVIDIA Nemotron 3 Ultra API 백엔드와 연결되었습니다.</p>`);
        }
      }
    } catch (e) {
      console.warn('Nemotron Lab status check failed:', e);
    }
  }

  $('#run').addEventListener('click', async () => {
    const text = prompt.value.trim();
    if (!text) { notify('먼저 테스트할 내용을 입력해 주세요.'); prompt.focus(); return; }
    const runBtn = $('#run');
    const runLabel = $('#runLabel');
    if (runBtn.disabled) return;

    const label = mode === 'translate' ? '번역' : mode === 'prompt' ? '프롬프트' : '대화';
    const sourceLangVal = $('#sourceLang')?.value || 'auto';
    const targetLangVal = $('#targetLang')?.value || 'en';

    runBtn.disabled = true;
    runLabel.textContent = '네모트론 생성 중…';
    result.className = 'preview-result loading';
    result.textContent = `[${label} 모드 · NVIDIA API 요청 전송 중]\n\nNemotron 3 Ultra 모델로 프롬프트를 전송 중입니다. 잠시만 기다려 주세요...`;

    try {
      const payload = {
        mode: mode,
        prompt: text,
        model: 'nvidia/nemotron-3-ultra-550b-a55b',
        source_language: langMap[sourceLangVal] || '자동 감지',
        target_language: langMap[targetLangVal] || '영어',
        temperature: Number($('#temperature').value) / 100,
        max_tokens: 2048,
        stream: false
      };

      const res = await fetch('/api/nemotron-lab/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });

      const json = await res.json();
      const resData = json?.data || json;

      if (json?.ok && resData?.content) {
        result.className = 'preview-result success';
        result.textContent = resData.content;

        meta.classList.remove('hidden');
        meta.innerHTML = `<span>상태 <b>200 OK (${resData.status})</b></span><span>응답 시간 <b>${(resData.latency_ms / 1000).toFixed(2)}초</b></span><span>입력 토큰 <b>${resData.input_tokens || 0}</b></span><span>출력 토큰 <b>${resData.output_tokens || 0}</b></span>`;

        activity.className = '';
        activity.innerHTML = `<div class="activity-item"><strong>${label} 완료 · Nemotron 3 Ultra</strong><p>${resData.content.replace(/[<>]/g, '').slice(0, 120)}...</p><small>응답 시간: ${resData.latency_ms}ms · 토큰: ${resData.total_tokens || 0}</small></div>` + activity.innerHTML;

        $('#console').insertAdjacentHTML('beforeend', `<p><time>EXECUTE</time><b>[SUCCESS]</b> ${label} 응답 완료 (${resData.latency_ms}ms, 토큰: ${resData.total_tokens || 0})</p>`);
        notify('네모트론 3 울트라 응답이 완료되었습니다.');
      } else {
        const errorMsg = json?.message || resData?.error || 'NVIDIA API 응답을 가져오지 못했습니다.';
        result.className = 'preview-result error';
        result.textContent = `[NVIDIA API 호출 오류]\n\n${errorMsg}`;
        $('#console').insertAdjacentHTML('beforeend', `<p><time>ERROR</time><b>[FAILED]</b> ${errorMsg.slice(0, 100)}</p>`);
        notify(`오류 발생: ${errorMsg.slice(0, 60)}`);
      }
    } catch (err) {
      result.className = 'preview-result error';
      result.textContent = `[네트워크 통신 오류]\n\n${err.message}`;
      notify('서버 통신 실패');
    } finally {
      runBtn.disabled = false;
      runLabel.textContent = modeInfo[mode][1];
    }
  });

  $('#clearResult').addEventListener('click', () => location.reload());
  $('#copy').addEventListener('click', async () => {
    const text = result.textContent.trim();
    if (!text) return;
    await navigator.clipboard.writeText(text);
    notify('응답 영역을 복사했습니다.');
  });
  $('#refresh').addEventListener('click', () => { updateClock(); checkApiStatus(); notify('관제 화면 상태를 새로 확인했습니다.'); });
  $$('.nav').forEach((button, index) => button.addEventListener('click', () => {
    const targets = ['.composer', '.telemetry', '.activity'];
    document.querySelector(targets[index])?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    $$('.nav').forEach((item) => item.classList.toggle('active', item === button));
  }));

  checkLogin();
  checkApiStatus();
  updateClock();
  setInterval(updateClock, 1000);
})();
