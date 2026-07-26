const state = {
  titles: [],
  imageGuides: [],
  projects: [],
  currentProject: null,
  assets: { images: [], videos: [], thumbnails: [], all: [] },
  activeChannel: 'naver_blog',
  wordpress: { renderedHtml: '' },
  instagramReels: { payload: {} }
};

function byId(id) {
  return document.getElementById(id);
}

function toast(message = '복사 완료') {
  const el = byId('toast');
  if (!el) return;
  el.textContent = message;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 1300);
}

async function copyText(text, message) {
  await navigator.clipboard.writeText(text || '');
  toast(message);
}

function openNaverWrite() {
  window.open('https://blog.naver.com/GoBlogWrite.naver', '_blank', 'noopener,noreferrer');
}

function switchCopyStudioTab(channel) {
  state.activeChannel = channel || 'naver_blog';
  document.querySelectorAll('.nb-tab').forEach(btn => btn.classList.toggle('active', btn.dataset.channel === state.activeChannel));
  document.querySelectorAll('.nb-tab-pane').forEach(pane => pane.classList.toggle('active', pane.id === `pane-${state.activeChannel}`));
  if (state.activeChannel === 'wordpress') renderWordPressTab();
  if (state.activeChannel === 'instagram_reels') renderInstagramReelsTab();
}

function getStoryMakerToken() {
  let token = localStorage.getItem('storymaker_token') || '';
  const legacyToken = localStorage.getItem('access_token') || sessionStorage.getItem('storymaker_token') || sessionStorage.getItem('access_token') || '';
  if (!token && legacyToken) {
    token = legacyToken;
    localStorage.setItem('storymaker_token', token);
  }
  return token;
}

function getAuthHeaders() {
  const token = getStoryMakerToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function verifyStoryMakerSession() {
  const token = getStoryMakerToken();
  const status = byId('projectLoadStatus');
  if (!token) {
    if (status) status.textContent = 'StoryMaker 로그인 세션이 없습니다. 먼저 StoryMaker에서 로그인해 주세요.';
    return false;
  }
  try {
    const response = await fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include'
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok || !data.data) {
      throw new Error(data.detail || data.message || `HTTP ${response.status}`);
    }
    localStorage.setItem('storymaker_user', JSON.stringify(data.data));
    if (status) status.textContent = `${data.data.username || '사용자'} 로그인 세션 확인 완료. 프로젝트를 불러옵니다.`;
    return true;
  } catch (error) {
    if (status) status.textContent = `로그인 세션 확인 실패: ${error.message}`;
    return false;
  }
}

async function fetchStoryMakerJson(url, options = {}) {
  const headers = Object.assign({}, getAuthHeaders(), options.headers || {});
  const response = await fetch(url, Object.assign({}, options, { headers }));
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    throw new Error(data.detail || data.message || `HTTP ${response.status}`);
  }
  return data;
}

async function loadProjectOptions() {
  const selector = byId('projectSelector');
  const status = byId('projectLoadStatus');
  if (!selector) return;
  const hasValidSession = await verifyStoryMakerSession();
  if (!hasValidSession) {
    selector.innerHTML = '<option value="">StoryMaker에 먼저 로그인해 주세요</option>';
    if (status) status.textContent = '로그인 세션이 없어 프로젝트 목록을 불러오지 못했습니다.';
    return;
  }
  try {
    if (status) status.textContent = '프로젝트 목록을 불러오는 중입니다.';
    const res = await fetchStoryMakerJson('/api/projects?limit=50');
    state.projects = res.data || [];
    selector.innerHTML = '<option value="">프로젝트를 선택하세요</option>';
    state.projects.forEach(project => {
      const option = document.createElement('option');
      option.value = project.id;
      const date = String(project.updated_at || '').split(' ')[0] || '-';
      option.textContent = `[${date}] ${project.title || '무제 프로젝트'}`;
      selector.appendChild(option);
    });
    if (status) status.textContent = `프로젝트 ${state.projects.length}개를 불러왔습니다.`;
    await autoLoadInitialProject();
  } catch (error) {
    selector.innerHTML = '<option value="">프로젝트 목록 로드 실패</option>';
    if (status) status.textContent = `프로젝트 목록 실패: ${error.message}`;
  }
}

async function autoLoadInitialProject() {
  const selector = byId('projectSelector');
  const status = byId('projectLoadStatus');
  if (!selector || state.currentProject || !state.projects || !state.projects.length) return;

  const params = new URLSearchParams(window.location.search);
  const queryProjectId = params.get('project_id') || params.get('id');
  const savedProjectId = localStorage.getItem('current_project_id');
  const candidateId = queryProjectId || savedProjectId || String(state.projects[0].id || '');
  const exists = state.projects.some(project => String(project.id) === String(candidateId));
  const targetId = exists ? candidateId : String(state.projects[0].id || '');
  if (!targetId) return;

  selector.value = targetId;
  if (status) status.textContent = `최신 프로젝트 ID ${targetId}를 자동으로 불러옵니다.`;
  await loadSelectedProjectForBlog({ silent: true });
}

async function loadSelectedProjectForBlog(options = {}) {
  const selector = byId('projectSelector');
  const status = byId('projectLoadStatus');
  const projectId = selector?.value;
  if (!projectId) {
    toast('프로젝트를 먼저 선택하세요');
    return;
  }
  try {
    if (status) status.textContent = `프로젝트 ID ${projectId} 불러오는 중입니다.`;
    const res = await fetchStoryMakerJson(`/api/projects/${projectId}`);
    const project = res.data || {};
    state.currentProject = project;
    applyProjectToBlogStudio(project);
    await loadProjectAssetsForBlog();
    renderExtraChannelTabs();
    if (status) status.textContent = `프로젝트 [${project.title || projectId}] 불러오기 완료`;
    if (!options.silent) toast('프로젝트 불러오기 완료');
  } catch (error) {
    if (status) status.textContent = `프로젝트 불러오기 실패: ${error.message}`;
    toast('프로젝트 불러오기 실패');
  }
}

async function loadProjectAssetsForBlog() {
  const status = byId('assetLoadStatus');
  const project = state.currentProject;
  if (!project || !project.id) {
    if (status) status.textContent = '먼저 프로젝트를 불러와 주세요.';
    toast('프로젝트를 먼저 불러오세요');
    return;
  }
  try {
    if (status) status.textContent = '로그인 사용자 전체 이미지, MP4, 썸네일 자산을 불러오는 중입니다.';
    const userAssetRes = await fetchStoryMakerJson('/api/naver-blog-copy/project-assets/72');
    const legacyData = userAssetRes.data || {};
    const rawAssets = [].concat(legacyData.images || [], legacyData.videos || [], legacyData.thumbnails || [], legacyData.all || [], userAssetRes.assets || []);
    const normalizedAssets = rawAssets.map(item => {
      const kind = String(item.asset_type || item.kind || 'image').toLowerCase();
      return Object.assign({}, item, {
        kind,
        url: item.preview_url || item.public_url || item.url || '',
        name: item.stored_filename || item.original_filename || item.name || item.anchor_tag || 'asset',
        size: item.file_size || item.size || 0
      });
    }).filter(item => item.url && ['image', 'video', 'thumbnail'].includes(item.kind));
    state.assets = {
      images: normalizedAssets.filter(item => item.kind === 'image'),
      videos: normalizedAssets.filter(item => item.kind === 'video'),
      thumbnails: normalizedAssets.filter(item => item.kind === 'thumbnail'),
      all: normalizedAssets
    };
    renderAssetGallery();
    renderExtraChannelTabs();
    if (status) status.textContent = `내 자산 ${state.assets.all.length}개를 불러왔습니다. 이미지 ${state.assets.images.length}개 / 동영상 ${state.assets.videos.length}개 / 썸네일 ${state.assets.thumbnails.length}개`;
    return;
    const projectKey = project.project_key || project.title || '';
    const url = `/api/naver-blog-copy/project-assets/${project.id}?project_title=${encodeURIComponent(project.title || '')}&project_key=${encodeURIComponent(projectKey)}`;
    const res = await fetchStoryMakerJson(url);
    state.assets = res.data || { images: [], videos: [], thumbnails: [], all: [] };
    renderAssetGallery();
    renderExtraChannelTabs();
    const count = (state.assets.images || []).length + (state.assets.videos || []).length + (state.assets.thumbnails || []).length;
    if (status) status.textContent = `산출물 ${count}개를 불러왔습니다.`;
  } catch (error) {
    if (status) status.textContent = `산출물 로드 실패: ${error.message}`;
    renderAssetGallery();
  }
}

function renderAssetGallery() {
  const box = byId('assetGallery');
  if (!box) return;
  const assets = state.assets || { images: [], videos: [], thumbnails: [] };
  const parts = [];
  parts.push(renderAssetGroup('썸네일', assets.thumbnails || []));
  parts.push(renderAssetGroup('MP4 / 숏폼', assets.videos || []));
  parts.push(renderAssetGroup('이미지', assets.images || []));
  box.innerHTML = parts.join('') || '<p class="nb-mini-status">표시할 산출물이 없습니다.</p>';
}

function renderAssetGroup(title, items) {
  if (!items || !items.length) return '';
  return `<div class="nb-asset-group-title">${escapeHtml(title)} ${items.length}개</div>` + items.map(item => renderAssetCard(item)).join('');
}

function renderAssetCard(item) {
  const isVideo = item.kind === 'video';
  const media = isVideo
    ? `<video src="${escapeHtml(item.url)}" controls muted preload="metadata"></video>`
    : `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.name)}" loading="lazy">`;
  return `
    <div class="nb-asset-card">
      ${media}
      <div class="nb-asset-meta">
        <strong>${escapeHtml(item.name)}</strong>
        ${escapeHtml(item.kind)} · ${formatBytes(item.size)}
        <div class="nb-asset-actions">
          <button type="button" onclick="copyAssetUrl('${escapeJs(item.url)}')">URL 복사</button>
          <button type="button" onclick="addAssetToImageGuide('${escapeJs(item.url)}', '${escapeJs(item.name)}')">이미지 가이드</button>
        </div>
      </div>
    </div>
  `;
}

function formatBytes(size) {
  const n = Number(size || 0);
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)}MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${n}B`;
}

function copyAssetUrl(url) {
  copyText(url, '산출물 URL 복사 완료');
}

function addAssetToImageGuide(url, name) {
  const next = state.imageGuides.length + 1;
  state.imageGuides.push({
    key: `IMAGE_${next}`,
    role: '프로젝트 산출물',
    alt: name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '),
    caption: url
  });
  renderImageGuide();
  toast('이미지 가이드에 추가했습니다');
}

function escapeJs(value) {
  return String(value || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, ' ');
}

function applyProjectToBlogStudio(project) {
  const parsed = project.parsed_result_json || {};
  const company = project.company || project.company_name || project.business_name || extractCompanyFromTitle(project.title) || byId('companyName').value;
  const keywords = Array.isArray(project.keywords) ? project.keywords.join(', ') : (project.keywords || byId('mainKeyword').value);
  byId('companyName').value = company || '';
  byId('mainKeyword').value = keywords || '';
  byId('extraContext').value = project.reference_text || project.base_content || byId('extraContext').value;

  const titlesText = parsed.BLOG_TITLES || parsed.BLOG_TITLE || parsed.titles || '';
  const bodyText = parsed.BLOG_POST || parsed.BLOG || parsed.blog_post || project.raw_result || project.base_content || '';
  const hashtagsText = parsed.HASHTAGS || parsed.BLOG_HASHTAGS || extractHashtags(bodyText) || byId('hashtags').value;

  const titles = parseRecommendedTitles(titlesText);
  state.titles = titles.length ? titles : buildFallbackTitles(company, keywords);
  byId('selectedTitle').value = state.titles[0] || project.title || '제목 없음';

  const body = normalizeBlogBody(bodyText, byId('selectedTitle').value);
  byId('bodyText').value = body || makeBodyFromProject(project);
  byId('hashtags').value = hashtagsText || '';
  state.imageGuides = buildImageGuides(company);
  renderTitles();
  renderImageGuide();
  renderPreview();
  renderExtraChannelTabs();
}

function extractCompanyFromTitle(title) {
  return String(title || '').split('_')[0].replace(/마케팅작업|블로그|프로젝트/g, '').trim();
}

function parseRecommendedTitles(value) {
  const text = Array.isArray(value) ? value.join('\n') : String(value || '');
  if (!text.trim()) return [];
  const matches = Array.from(text.replace(/\r\n?/g, '\n').matchAll(/(?:^|\n|\s)(\d+)\.\s*(.*?)(?=(?:\n|\s)\d+\.\s*|$)/g));
  if (matches.length) return matches.map(m => m[2].trim()).filter(Boolean).slice(0, 5);
  return text.split('\n').map(v => v.replace(/^[-*•]\s*/, '').trim()).filter(Boolean).slice(0, 5);
}

function buildFallbackTitles(company, keywords) {
  const main = String(keywords || '').split(',')[0].trim() || '네이버 블로그';
  return [
    `${main} 찾는 분들이 ${company || '우리 업체'}에서 먼저 확인할 것`,
    `${company || '우리 업체'} 방문 전 알아두면 좋은 상담 포인트`,
    `${main} 고민을 줄이는 현실적인 선택 기준`,
    `처음 방문하는 분들을 위한 ${company || '업체'} 이용 안내`,
    `${main} 정보와 실제 방문 전 체크리스트`
  ];
}

function normalizeBlogBody(text, title) {
  let body = String(text || '').trim();
  if (!body) return '';
  body = body.replace(/^```[a-zA-Z]*\s*/g, '').replace(/```$/g, '').trim();
  body = body.replace(/^제목\s*:\s*.*$/m, '').trim();
  if (!body.includes('[IMAGE_1]')) {
    const paragraphs = body.split(/\n\s*\n/).filter(Boolean);
    if (paragraphs.length > 2) paragraphs.splice(2, 0, '[IMAGE_1]');
    if (paragraphs.length > 5) paragraphs.splice(5, 0, '[IMAGE_2]');
    if (paragraphs.length > 8) paragraphs.splice(8, 0, '[IMAGE_3]');
    body = paragraphs.join('\n\n');
  }
  return body;
}

function extractHashtags(text) {
  const matches = String(text || '').match(/#[^\s,#]+/g);
  return matches ? Array.from(new Set(matches)).join(' ') : '';
}

function makeBodyFromProject(project) {
  const company = byId('companyName').value || '우리 업체';
  const keyword = byId('mainKeyword').value || '지역 키워드';
  return `${byId('selectedTitle').value}\n\n${project.base_content || `${company}의 핵심 정보를 바탕으로 ${keyword} 블로그 원고를 준비합니다.`}\n\n[IMAGE_1]\n\n## 방문 전 확인하면 좋은 점\n\n${project.reference_text || '고객이 궁금해할 정보를 먼저 정리합니다.'}\n\n[IMAGE_2]\n\n## 상담이 필요한 이유\n\n현장 상황과 고객의 고민을 연결해 자연스럽게 방문을 유도합니다.\n\n[IMAGE_3]`;
}

function buildImageGuides(company) {
  const name = company || '업체';
  return [
    { key: 'IMAGE_1', role: '대표/외관/첫인상', alt: `${name} 대표 이미지 또는 매장 외관`, caption: '본문 초반 문제 제기 뒤' },
    { key: 'IMAGE_2', role: '상담/작업/서비스 장면', alt: `${name} 상담 또는 서비스 진행 장면`, caption: '중간 설명 뒤' },
    { key: 'IMAGE_3', role: '제품/결과/방문 유도', alt: `${name} 제품 또는 결과 확인 장면`, caption: '마무리 방문 유도 전' }
  ];
}

function generateDemoDraft() {
  const company = byId('companyName').value.trim() || '업체명';
  const keyword = byId('mainKeyword').value.trim() || '지역 키워드';
  const context = byId('extraContext').value.trim();
  const intent = byId('intent').value;

  state.titles = [
    `스마트폰 볼 때 눈이 피로하다면 ${company}에서 먼저 확인할 것`,
    `${keyword.split(',')[0].trim()} 찾는 분들이 시력검사 전에 알아야 할 이야기`,
    `하루 종일 화면을 보는 직장인과 학생을 위한 눈 건강 상담`,
    `${company}에서 안경을 맞추기 전 전문가 상담이 중요한 이유`,
    `상록수역 근처에서 눈 피로 상담이 필요할 때 확인할 체크포인트`
  ];

  const body = `${state.titles[0]}\n\n요즘은 하루의 대부분을 스마트폰과 컴퓨터 화면 앞에서 보내는 분들이 많습니다.\n\n처음에는 잠깐 뻑뻑한 정도로 느껴지지만, 시간이 지나면 눈 피로와 흐릿함이 반복되는 경우도 있습니다.\n\n[IMAGE_1]\n\n이럴 때 안경을 바로 바꾸기보다 현재 눈 상태를 먼저 확인하는 과정이 중요합니다.\n\n${company}에서는 단순히 도수만 확인하는 것이 아니라 생활 패턴과 사용 환경까지 함께 살펴보며 상담합니다.\n\n## 화면 사용 시간이 늘면서 생기는 변화\n\n스마트폰을 오래 보면 눈 깜빡임이 줄어들고, 건조함과 피로감이 쉽게 쌓일 수 있습니다.\n\n특히 학생이나 직장인처럼 가까운 거리를 오래 보는 분들은 작은 불편함도 생활의 집중도에 영향을 줄 수 있습니다.\n\n[IMAGE_2]\n\n${context}\n\n## 안경은 도수만 맞추는 일이 아닙니다\n\n안경은 시력 숫자만 보고 고르는 제품이 아닙니다.\n\n착용 시간, 화면 사용 습관, 렌즈 선택, 피팅 상태가 모두 편안함에 영향을 줍니다.\n\n[IMAGE_3]\n\n${company}에서는 예약 후 방문하시는 분들이 여유롭게 상담받을 수 있도록 안내하고 있습니다.\n\n눈이 자주 피로하거나 기존 안경이 불편했다면, 먼저 전문가와 현재 상태를 확인해보는 것이 좋습니다.`;

  state.imageGuides = [
    { key: 'IMAGE_1', role: '상담/검사 전경', alt: `${company}에서 눈 피로 상담을 받는 모습`, caption: '본문 초반, 문제 제기 뒤에 배치' },
    { key: 'IMAGE_2', role: '검안 장비/시력검사', alt: `${company} 시력검사 장비와 상담 공간`, caption: '화면 사용 시간 설명 뒤에 배치' },
    { key: 'IMAGE_3', role: '제품/피팅/매장 내부', alt: `${company} 안경 피팅과 렌즈 상담 장면`, caption: '전문가 상담 필요성 뒤에 배치' }
  ];

  byId('selectedTitle').value = state.titles[0];
  byId('bodyText').value = body;
  byId('hashtags').value = '#안산안경원 #상록수역안경원 #안산시력검사 #눈피로 #아이빌안경원';

  renderTitles();
  renderImageGuide();
  renderPreview();
  renderExtraChannelTabs();
}

function renderTitles() {
  const box = byId('titleList');
  box.innerHTML = '';
  state.titles.forEach((title, index) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'nb-title-item' + (byId('selectedTitle').value === title ? ' active' : '');
    item.innerHTML = `<span class="nb-title-num">${index + 1}</span><span>${escapeHtml(title)}</span>`;
    item.onclick = () => {
      byId('selectedTitle').value = title;
      renderTitles();
      renderPreview();
    };
    box.appendChild(item);
  });
}

function renderImageGuide() {
  const box = byId('imageGuide');
  box.innerHTML = state.imageGuides.map(item => `
    <div class="nb-image-card">
      <strong>[${item.key}]</strong><br>
      역할: ${escapeHtml(item.role)}<br>
      ALT: ${escapeHtml(item.alt)}<br>
      위치: ${escapeHtml(item.caption)}
    </div>
  `).join('');
}

let renderPreviewTimeout = null;
let lastRenderedHtml = null;
let lastMissingTokens = [];

function renderPreviewSync(bodyHtmlOverride = null, missingTokens = null) {
  const title = byId('selectedTitle').value.trim();
  const body = byId('bodyText').value.trim();
  const tags = byId('hashtags').value.trim();
  const titleList = state.titles.length ? `
    <section class="recommend-box">
      <h3>추천 제목</h3>
      <ol>${state.titles.map(v => `<li>${escapeHtml(v)}</li>`).join('')}</ol>
    </section>
  ` : '';
  
  if (bodyHtmlOverride !== null) {
    lastRenderedHtml = bodyHtmlOverride;
  }
  if (missingTokens !== null) {
    lastMissingTokens = missingTokens;
  }
  
  let bodyHtml = '';
  if (lastRenderedHtml !== null) {
    bodyHtml = lastRenderedHtml;
  } else {
    bodyHtml = body
      .split(/\n\s*\n/)
      .map(block => block.trim())
      .filter(Boolean)
      .map(block => {
        if (/^##\s+/.test(block)) return `<h2>${escapeHtml(block.replace(/^##\s+/, ''))}</h2>`;
        if (/^\[\[(IMAGE|VIDEO|THUMBNAIL):([A-Za-z0-9_-]+)\]\]$/i.test(block) || /^\[(IMAGE|VIDEO|THUMBNAIL)_([A-Za-z0-9_-]+)\]$/i.test(block)) {
          return `<div class="nb-anchor">${escapeHtml(block)} 이미지 자리</div>`;
        }
        return `<p>${escapeHtml(block).replace(/\n/g, '<br>')}</p>`;
      })
      .join('');
  }
  
  let warningHtml = '';
  if (lastMissingTokens && lastMissingTokens.length > 0) {
    const tokenList = lastMissingTokens.map(t => t.token).join(', ');
    warningHtml = `
      <div class="nb-warning-banner" style="background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; padding: 10px; border-radius: 4px; margin-bottom: 15px; font-weight: 500;">
        ⚠️ 연결되지 않은 이미지 토큰: ${escapeHtml(tokenList)}
      </div>
    `;
    
    const assetStatusEl = byId('assetLoadStatus');
    if (assetStatusEl) {
      assetStatusEl.innerHTML = `<span style="color: #c0392b; font-weight: bold;">연결되지 않은 이미지 토큰: ${escapeHtml(tokenList)}</span>`;
    }
  }
  
  byId('preview').innerHTML = `${warningHtml}${titleList}<h1>${escapeHtml(title)}</h1>${bodyHtml}<p><strong>${escapeHtml(tags)}</strong></p>`;
}

function renderPreview() {
  lastRenderedHtml = null;
  lastMissingTokens = [];
  renderPreviewSync();

  const project = state.currentProject;
  if (!project || !project.id) {
    return;
  }

  if (renderPreviewTimeout) {
    clearTimeout(renderPreviewTimeout);
  }

  renderPreviewTimeout = setTimeout(async () => {
    const body = byId('bodyText').value.trim();
    if (!body) return;

    try {
      const url = '/api/naver-blog-copy/resolve-assets';
      const payload = {
        project_id: project.id,
        project_key: project.project_key || project.title || null,
        content: body
      };
      
      const res = await fetchStoryMakerJson(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      
      if (res && res.ok && res.data && res.data.rendered_html !== undefined) {
        renderPreviewSync(res.data.rendered_html, res.data.missing_tokens || []);
      }
    } catch (err) {
      console.error('Failed to resolve assets:', err);
    }
  }, 400);
  scheduleExtraChannelRender();
}

let extraChannelTimeout = null;

function scheduleExtraChannelRender() {
  if (!state.currentProject || !state.currentProject.id) return;
  if (extraChannelTimeout) clearTimeout(extraChannelTimeout);
  extraChannelTimeout = setTimeout(renderExtraChannelTabs, 500);
}

function renderExtraChannelTabs() {
  if (!state.currentProject || !state.currentProject.id) {
    renderWordPressEmpty('프로젝트를 먼저 불러오면 워드프레스 HTML을 생성합니다.');
    renderInstagramEmpty('프로젝트를 먼저 불러오면 릴스 자산을 표시합니다.');
    return;
  }
  renderWordPressTab();
  renderInstagramReelsTab();
}

function projectBlocks() {
  const parsed = state.currentProject?.parsed_result_json || {};
  if (typeof parsed === 'string') {
    try { return JSON.parse(parsed); } catch (err) { return {}; }
  }
  return parsed;
}

function firstLine(text) {
  return String(text || '').split('\n').map(v => v.trim()).find(Boolean) || '';
}

function plainText(text) {
  return String(text || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

function renderWordPressEmpty(message) {
  if (byId('wpStatus')) byId('wpStatus').textContent = message;
  if (byId('wpPreview')) byId('wpPreview').innerHTML = `<p class="nb-mini-status">${escapeHtml(message)}</p>`;
}

async function renderWordPressTab() {
  const project = state.currentProject;
  const status = byId('wpStatus');
  if (!project || !project.id) {
    renderWordPressEmpty('프로젝트를 먼저 불러오면 워드프레스 HTML을 생성합니다.');
    return;
  }
  const title = byId('selectedTitle')?.value || firstLine(project.title) || '제목 없음';
  const body = byId('bodyText')?.value || '';
  const tags = byId('hashtags')?.value || '';
  const focus = String(byId('mainKeyword')?.value || title).split(',')[0].trim();
  const metaDescription = plainText(body).slice(0, 155);
  if (byId('wpTitle')) byId('wpTitle').value = title;
  if (byId('wpMetaDescription')) byId('wpMetaDescription').value = metaDescription;
  if (byId('wpFocusKeyword')) byId('wpFocusKeyword').value = focus;
  try {
    if (status) status.textContent = '워드프레스 HTML 변환 중입니다.';
    const res = await fetchStoryMakerJson('/api/copy-studio/resolve-assets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: project.id,
        project_key: project.project_key || project.title || null,
        channel: 'wordpress',
        title,
        content: body,
        meta: { tags }
      })
    });
    const html = res.data?.rendered_html || '';
    state.wordpress.renderedHtml = html;
    if (byId('wpBodyHtml')) byId('wpBodyHtml').value = html;
    if (byId('wpPreview')) byId('wpPreview').innerHTML = html || '<p class="nb-mini-status">변환할 본문이 없습니다.</p>';
    const missing = res.data?.missing_tokens || [];
    if (status) status.textContent = missing.length ? `연결되지 않은 이미지 토큰 ${missing.length}개가 있습니다.` : '워드프레스 HTML 변환 완료';
  } catch (error) {
    if (status) status.textContent = `워드프레스 변환 실패: ${error.message}`;
  }
}

function instagramMetaFromProject() {
  const blocks = projectBlocks();
  const caption = byId('igCaption')?.value || blocks.INSTAGRAM_POST || '';
  const hashtags = byId('igHashtags')?.value || blocks.INSTAGRAM_HASHTAGS || byId('hashtags')?.value || '';
  return { caption, hashtags };
}

function renderInstagramEmpty(message) {
  if (byId('igStatus')) byId('igStatus').textContent = message;
  if (byId('igMedia')) byId('igMedia').innerHTML = `<div class="nb-empty">${escapeHtml(message)}</div>`;
}

async function renderInstagramReelsTab() {
  const project = state.currentProject;
  const status = byId('igStatus');
  if (!project || !project.id) {
    renderInstagramEmpty('프로젝트를 먼저 불러오면 릴스 자산을 표시합니다.');
    return;
  }
  try {
    if (status) status.textContent = '릴스 자산을 불러오는 중입니다.';
    const meta = instagramMetaFromProject();
    const res = await fetchStoryMakerJson('/api/copy-studio/resolve-assets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: project.id,
        project_key: project.project_key || project.title || null,
        channel: 'instagram_reels',
        content: '',
        meta
      })
    });
    const payload = res.data?.channel_payload || {};
    if (!payload.video_url && state.assets && (state.assets.videos || []).length) {
      const video = state.assets.videos[0] || {};
      const thumbnail = (state.assets.thumbnails || [])[0] || {};
      payload.video_url = video.url || video.preview_url || video.public_url || '';
      payload.video_filename = video.name || video.stored_filename || video.original_filename || '';
      payload.thumbnail_url = thumbnail.url || thumbnail.preview_url || thumbnail.public_url || '';
      payload.thumbnail_filename = thumbnail.name || thumbnail.stored_filename || thumbnail.original_filename || '';
    }
    state.instagramReels.payload = payload;
    if (byId('igCaption')) byId('igCaption').value = payload.caption || meta.caption || '';
    if (byId('igHashtags')) byId('igHashtags').value = payload.hashtags || meta.hashtags || '';
    if (byId('igCopyText')) byId('igCopyText').value = payload.copy_text || [payload.caption || meta.caption, payload.hashtags || meta.hashtags].filter(Boolean).join('\n\n');
    renderInstagramMedia(payload);
    if (status) status.textContent = payload.video_url ? '릴스 패키지 준비 완료' : '연결된 릴스 영상이 없습니다.';
  } catch (error) {
    if (status) status.textContent = `릴스 자산 로드 실패: ${error.message}`;
  }
}

function renderInstagramMedia(payload) {
  const box = byId('igMedia');
  if (!box) return;
  if (!payload || !payload.video_url) {
    box.innerHTML = '<div class="nb-empty">연결된 릴스 영상이 없습니다.</div>';
    return;
  }
  const thumb = payload.thumbnail_url
    ? `<img src="${escapeHtml(payload.thumbnail_url)}" alt="${escapeHtml(payload.thumbnail_filename || '릴스 썸네일')}" loading="lazy">`
    : '<div class="nb-empty">연결된 썸네일이 없습니다.</div>';
  box.innerHTML = `
    <div class="nb-reels-card">
      <video src="${escapeHtml(payload.video_url)}" controls muted preload="metadata"></video>
      <div class="nb-reels-thumb">${thumb}</div>
      <p class="nb-mini-status">영상: ${escapeHtml(payload.video_filename || '-')} / 썸네일: ${escapeHtml(payload.thumbnail_filename || '-')}</p>
    </div>
  `;
}

function syncInstagramCopyText() {
  const text = [byId('igCaption')?.value, byId('igHashtags')?.value].filter(Boolean).join('\n\n');
  if (byId('igCopyText')) byId('igCopyText').value = text;
}

function copyWordPressHtml() {
  copyText(byId('wpBodyHtml')?.value || '', '워드프레스 HTML 복사 완료');
}

function copyInstagramReelsText() {
  syncInstagramCopyText();
  const text = byId('igCopyText')?.value || '';
  copyText(text, '릴스 복사용 텍스트 복사 완료');
}

function copyRecommendedTitles() {
  copyText(state.titles.map((v, i) => `${i + 1}. ${v}`).join('\n'), '추천 제목 복사 완료');
}

function copySelectedTitle() {
  copyText(byId('selectedTitle').value, '제목 복사 완료');
}

function copyBody() {
  copyText(byId('bodyText').value, '본문 복사 완료');
}

function copyHashtags() {
  copyText(byId('hashtags').value, '해시태그 복사 완료');
}

function copyImageGuide() {
  const text = state.imageGuides.map(item => `[${item.key}]\n역할: ${item.role}\nALT: ${item.alt}\n위치: ${item.caption}`).join('\n\n');
  copyText(text, '이미지 가이드 복사 완료');
}

function copyAll() {
  const text = `${byId('selectedTitle').value}\n\n${byId('bodyText').value}\n\n${byId('hashtags').value}`;
  copyText(text, '전체 복사 완료');
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

['selectedTitle', 'bodyText', 'hashtags'].forEach(id => {
  window.addEventListener('DOMContentLoaded', () => {
    const el = byId(id);
    if (el) el.addEventListener('input', renderPreview);
  });
});

['igCaption', 'igHashtags'].forEach(id => {
  window.addEventListener('DOMContentLoaded', () => {
    const el = byId(id);
    if (el) el.addEventListener('input', syncInstagramCopyText);
  });
});

window.addEventListener('DOMContentLoaded', () => {
  generateDemoDraft();
  loadProjectOptions();
});
