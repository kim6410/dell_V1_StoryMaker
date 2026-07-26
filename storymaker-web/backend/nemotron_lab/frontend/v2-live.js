(() => {
  const API = '/api/nemotron-lab';
  const state = { models: [], model: localStorage.getItem('storymakerNemotronModel') || '', result: '', busy: false };
  let pollTimer = null;

  const esc = (v) => String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const num = (v) => Number(v || 0).toLocaleString('ko-KR');
  const latency = (v) => v ? `${(Number(v)/1000).toFixed(2)}초` : '—';

  async function api(path, options={}) {
    const response = await fetch(API + path, { credentials:'include', cache:'no-store', headers:{'Content-Type':'application/json'}, ...options });
    let payload = null; try { payload = await response.json(); } catch (_) {}
    if (response.status === 401) throw new Error('로그인 세션이 만료되었습니다.');
    if (!response.ok) throw new Error(payload?.detail || payload?.message || `HTTP ${response.status}`);
    return payload;
  }

  function toast(host, message) {
    const el = host.querySelector('.lab2-live-toast');
    if (!el) return;
    el.textContent = message; el.classList.add('show');
    clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove('show'), 2400);
  }

  function log(host, tag, message) {
    const box = host.querySelector('.lab2-console-body'); if (!box) return;
    const p = document.createElement('p'); p.innerHTML = `<b>[${esc(tag)}]</b> ${esc(message)}`; box.prepend(p);
    while (box.children.length > 7) box.lastElementChild?.remove();
  }

  function modelMeta(id) {
    if (id.includes('nemotron-3-ultra-550b-a55b')) return '550B · A55B';
    return (id.match(/(?:^|[-_/])(\d+(?:\.\d+)?b)(?:[-_/]|$)/i)?.[1] || id.split('/')[0] || 'NVIDIA').toUpperCase();
  }

  function modalMarkup() {
    return `<div class="lab2-model-modal" hidden><section class="lab2-model-dialog"><header><div><p>MODEL CATALOG</p><h3>사용할 모델 선택</h3><small>NVIDIA 계정에서 조회된 텍스트 생성 모델만 표시합니다.</small></div><button class="lab2-model-close" type="button">×</button></header><div class="lab2-model-tools"><input type="search" placeholder="모델 이름 또는 ID 검색"><button type="button" data-model-refresh>목록 새로고침</button></div><div class="lab2-model-list"></div></section></div><div class="lab2-live-toast"></div>`;
  }

  function selected() { return state.models.find(x => x.id === state.model) || state.models[0] || null; }

  function renderModel(host) {
    const item = selected(); if (!item) return;
    state.model = item.id; localStorage.setItem('storymakerNemotronModel', item.id);
    const card = host.querySelectorAll('.lab2-metric')[1];
    card.querySelector('strong').textContent = item.name || item.id;
    card.querySelector('p').textContent = modelMeta(item.id);
    card.querySelector('code').textContent = item.id;
  }

  function renderModelList(host, filter='') {
    const list = host.querySelector('.lab2-model-list'); if (!list) return;
    const q = filter.trim().toLowerCase();
    const items = state.models.filter(x => !q || x.id.toLowerCase().includes(q) || String(x.name).toLowerCase().includes(q));
    list.innerHTML = items.length ? items.map(x => `<button class="lab2-model-option ${x.id===state.model?'selected':''}" type="button" data-model="${esc(x.id)}"><div><strong>${esc(x.name||x.id)}</strong><span>${esc(x.description||'NVIDIA 텍스트 생성 모델')}</span><code>${esc(x.id)}</code></div><aside><b>${esc(modelMeta(x.id))}</b><em>${x.id===state.model?'선택됨':'선택'}</em></aside></button>`).join('') : '<p>조건에 맞는 모델이 없습니다.</p>';
    list.querySelectorAll('[data-model]').forEach(btn => btn.onclick = () => { state.model = btn.dataset.model; renderModel(host); renderModelList(host, host.querySelector('.lab2-model-tools input').value); host.querySelector('.lab2-model-modal').hidden = true; toast(host,'선택 모델이 변경되었습니다.'); log(host,'MODEL',state.model); });
  }

  async function loadModels(host, force=false) {
    const payload = await api(`/models${force?'?refresh=true':''}`);
    state.models = payload?.data?.models || [];
    const def = payload?.data?.default_model || '';
    if (!state.models.some(x => x.id === state.model)) state.model = state.models.find(x => x.id===def)?.id || state.models[0]?.id || '';
    renderModel(host); renderModelList(host); log(host,'MODEL',`${state.models.length}개 모델 조회 완료`);
  }

  function updateStatus(host, data) {
    const cards = host.querySelectorAll('.lab2-metric'); const online = data.status === 'online';
    const strong = cards[0].querySelector('strong'); strong.textContent = online ? '정상 연결' : '연결 안 됨'; strong.className = online ? 'lab2-live-online' : 'danger lab2-live-error';
    cards[0].querySelector('p').textContent = online ? `${data.model_count||state.models.length}개 모델 사용 가능` : (data.last_error || 'NVIDIA 연결 확인 필요');
    const hero = host.querySelector('.lab2-hero .lab2-state'); hero.innerHTML = `<i></i> ${online?'LIVE · NVIDIA CONNECTED':'OFFLINE · 연결 확인 필요'}`; hero.classList.toggle('online',online);
    const side = host.querySelector('.lab2-telemetry .lab2-state'); side.innerHTML = `<i></i> ${online?'ONLINE':'OFFLINE'}`;
    const radar = host.querySelector('.lab2-radarbox'); radar.querySelector('strong').textContent = online?'연결 정상':'연결 대기'; radar.querySelector('small').textContent = online?'모델 목록과 API 준비 완료':'모델 연결 상태 진단 필요';
    const health = host.querySelectorAll('.lab2-health p'); health[0].querySelector('i').className = `lab2-dot ${online?'':'off'}`; health[0].querySelector('b').textContent = online?'연결됨':'미연결'; health[4].querySelector('b').textContent = '23:59 실행';
  }

  function updateUsage(host, data) {
    const s = data.summary || data || {}; const cards = host.querySelectorAll('.lab2-metric');
    host.querySelector('#lab2RequestCount').innerHTML = `${num(s.requests)}<small> 건</small>`;
    cards[2].querySelector('p').textContent = `성공 ${num(s.success)} · 실패 ${num(s.failed)} · 지연 종료 ${num(s.timeouts)}`;
    host.querySelector('#lab2TokenCount').textContent = num(s.total_tokens); cards[3].querySelector('p').textContent = `입력 ${num(s.input_tokens)} · 출력 ${num(s.output_tokens)}`;
    const lat = host.querySelectorAll('.lab2-latency b'); lat[1].textContent = latency(s.average_latency_ms); lat[2].textContent = s.requests ? `${Math.round(Number(s.success||0)/Number(s.requests)*100)}%` : '—';
    const activity = host.querySelector('#lab2Activity'); const recent = data.recent || [];
    if (recent.length) { activity.className=''; activity.innerHTML = recent.map(x => `<div class="lab2-activity-item"><strong>${esc({chat:'대화',translate:'번역',prompt:'프롬프트'}[x.mode]||x.mode)} · ${esc(x.status)}</strong><p>${esc(x.prompt_preview||'')}</p><small>${esc(x.model||'')} · ${latency(x.latency_ms)} · ${num(x.total_tokens)} tokens</small></div>`).join(''); }
  }

  async function refresh(host, force=false) {
    try {
      const [models,status,usage] = await Promise.all([loadModels(host,force),api('/status'),api('/usage')]);
      updateStatus(host,status.data||{}); updateUsage(host,usage.data||{}); log(host,'READY','실제 NVIDIA 테스트 준비 완료');
    } catch (e) { updateStatus(host,{status:'offline',last_error:e.message}); toast(host,e.message); log(host,'ERROR',e.message); }
  }

  function showResult(host, result) {
    const box = host.querySelector('#lab2Result'); box.className='lab2-result-live';
    box.innerHTML = `<pre>${esc(result.content || result.error || '표시할 응답이 없습니다.')}</pre><div class="lab2-result-meta"><span>모델 <b>${esc(result.model||state.model)}</b></span><span>응답 <b>${latency(result.latency_ms)}</b></span><span>입력 <b>${num(result.input_tokens)}</b></span><span>출력 <b>${num(result.output_tokens)}</b></span><span>전체 <b>${num(result.total_tokens)}</b></span><span>상태 <b>${esc(result.status||'unknown')}</b></span></div>`;
    state.result = result.content || ''; host.querySelectorAll('.lab2-latency b')[0].textContent = latency(result.latency_ms);
  }

  async function submit(host, send) {
    if (state.busy) return; const prompt = host.querySelector('#lab2Prompt').value.trim();
    if (!prompt) return host.querySelector('#lab2Prompt').focus(); if (!state.model) return toast(host,'모델을 먼저 선택해 주세요.');
    state.busy=true; send.disabled=true; const original=send.textContent; const start=Date.now();
    const ticker=setInterval(()=>send.textContent=`응답 기다리는 중 ${((Date.now()-start)/1000).toFixed(1)}초`,200);
    try {
      const select=host.querySelector('.lab2-params select'); const max=parseInt(String(select?.value||select?.selectedOptions?.[0]?.textContent||'2048').replace(/[^0-9]/g,''),10)||2048;
      const payload=await api('/execute',{method:'POST',body:JSON.stringify({mode:host.dataset.mode||'chat',prompt,model:state.model,source_language:host.querySelector('#lab2Source')?.value||'자동 감지',target_language:host.querySelector('#lab2Target')?.value||'영어',temperature:Number(host.querySelector('#lab2Temperature').value||.35),max_tokens:Math.min(max,4096),stream:false})});
      const result=payload.data||{}; showResult(host,result); toast(host,payload.ok?'응답이 완료되었습니다.':(result.error||payload.message||'요청 실패')); log(host,payload.ok?'DONE':'FAIL',`${latency(result.latency_ms)} · ${num(result.total_tokens)} tokens`); await refresh(host,false);
    } catch(e) { showResult(host,{error:e.message,model:state.model,status:'failed',latency_ms:Date.now()-start}); toast(host,e.message); log(host,'ERROR',e.message); }
    finally { clearInterval(ticker); state.busy=false; send.disabled=false; send.textContent=original; }
  }

  function enhance(host) {
    if (host.dataset.liveConnected) return; host.dataset.liveConnected='1';
    const css=document.createElement('link'); css.rel='stylesheet'; css.href='/static/v2/nemotron-lab/v2-live.css?v=20260718-persona-popup-2'; document.head.appendChild(css);
    host.insertAdjacentHTML('beforeend',modalMarkup());
    const card=host.querySelectorAll('.lab2-metric')[1]; card.classList.add('lab2-model-select'); card.setAttribute('role','button'); card.tabIndex=0; card.querySelector('em').textContent='MODEL ▾'; card.onclick=()=>host.querySelector('.lab2-model-modal').hidden=false; card.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();card.click();}};
    const oldSend=host.querySelector('#lab2Send'); const send=oldSend.cloneNode(true); oldSend.replaceWith(send); send.onclick=()=>submit(host,send);
    const toggle=host.querySelector('.lab2-toggle'); if(toggle) toggle.innerHTML='응답 방식 <b>완료 후 표시</b>';
    const modal=host.querySelector('.lab2-model-modal'); host.querySelector('.lab2-model-close').onclick=()=>modal.hidden=true; modal.onclick=e=>{if(e.target===modal)modal.hidden=true;};
    host.querySelector('.lab2-model-tools input').oninput=e=>renderModelList(host,e.target.value); host.querySelector('[data-model-refresh]').onclick=()=>loadModels(host,true).then(()=>toast(host,'모델 목록을 새로 불러왔습니다.')).catch(e=>toast(host,e.message));
    refresh(host,true); pollTimer=setInterval(()=>{ if(document.body.contains(host)) Promise.all([api('/status'),api('/usage')]).then(([s,u])=>{updateStatus(host,s.data||{});updateUsage(host,u.data||{});}).catch(()=>{}); else clearInterval(pollTimer); },30000);
  }

  function wait() {
    window.__nemotronLiveModuleLoaded = true;
    api('/status').then((payload) => { window.__nemotronLiveProbe = payload; }).catch((error) => { window.__nemotronLiveProbeError = error.message; });
    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      const host = document.getElementById('storymaker-ai-lab2-host');
      if (!host) {
        if (attempts >= 160) clearInterval(timer);
        return;
      }
      clearInterval(timer);
      try {
        enhance(host);
        window.__nemotronLiveModuleReady = true;
      } catch (error) {
        window.__nemotronLiveModuleError = String(error?.stack || error);
        console.error('[Nemotron Live]', error);
        const box = host.querySelector('.lab2-console-body');
        if (box) box.insertAdjacentHTML('afterbegin', `<p><b>[LIVE ERROR]</b> ${esc(error?.message || error)}</p>`);
      }
    }, 200);
  }
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',wait,{once:true}):wait();
})();
