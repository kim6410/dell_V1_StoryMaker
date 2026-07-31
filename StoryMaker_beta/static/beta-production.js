(() => {
  'use strict';

  const betaUi = {
    form: document.getElementById('beta-create-form'),
    businessName: document.getElementById('beta-business-name'),
    businessProfileSelect: document.getElementById('beta-business-profile-select'),
    businessRegion: document.getElementById('beta-business-region'),
    businessRegionAlias: document.getElementById('beta-business-region-alias'),
    businessService: document.getElementById('beta-business-service'),
    businessIndustryKey: document.getElementById('beta-business-industry-key'),
    businessPhone: document.getElementById('beta-business-phone'),
    topic: document.getElementById('beta-topic'),
    images: document.getElementById('beta-images'),
    videos: document.getElementById('beta-videos'),
    status: document.getElementById('beta-status'),
    statusBox: document.getElementById('beta-production-status'),
    progressBar: document.getElementById('beta-progress-bar'),
    gemini: document.getElementById('beta-gemini'),
    geminiRetry: document.getElementById('beta-gemini-retry'),
    aiProviderBrowser: document.getElementById('beta-ai-provider-browser'),
    aiProviderApi: document.getElementById('beta-ai-provider-api'),
    channelResults: document.getElementById('beta-channel-results'),
    preview: document.getElementById('beta-preview'),
    audio: document.getElementById('beta-audio'),
    slotTabs: document.getElementById('beta-slot-tabs'),
    slots: document.getElementById('beta-slots'),
    content: document.getElementById('beta-content'),
    jobId: document.getElementById('beta-job-id'),
    checkJob: document.getElementById('beta-check-job'),
    checkGemini: document.getElementById('beta-check-gemini'),
    supertonic: document.getElementById('beta-supertonic'),
    checkAssets: document.getElementById('beta-check-assets'),
    debug: document.getElementById('beta-debug'),
    renderHandoff: document.getElementById('beta-render-handoff'),
    prepareBrowser: document.getElementById('beta-prepare-browser'),
    openBrowser: document.getElementById('beta-open-browser'),
    browserLink: document.getElementById('beta-browser-link'),
    shortformIntegrated: document.getElementById('beta-shortform-integrated'),
    shortformStatus: document.getElementById('beta-shortform-integrated-status'),
    promptEditOpen: document.getElementById('beta-prompt-edit-open'),
    promptSendOpen: document.getElementById('beta-prompt-send-open'),
    promptModal: document.getElementById('beta-prompt-modal'),
    promptModalTitle: document.getElementById('beta-prompt-modal-title'),
    promptEditor: document.getElementById('beta-prompt-editor'),
    promptMeta: document.getElementById('beta-prompt-meta'),
    promptMessage: document.getElementById('beta-prompt-message'),
    promptSave: document.getElementById('beta-prompt-save'),
    promptCopy: document.getElementById('beta-prompt-copy'),
    promptModalX: document.getElementById('beta-prompt-modal-x'),
    promptModalClose: document.getElementById('beta-prompt-modal-close'),
    newWork: document.getElementById('beta-new-work')
  };

  let betaCurrentJobId = sessionStorage.getItem('storymaker_beta_current_job') || '';
  let betaSelectedBusinessProfile = null;
  let betaPromptAnimation = null;
  let betaAiCompletionState = false;
  let betaGeminiWatchTimer = null;
  let betaGeminiLockedUntil = 0;
  let betaAutoAiDelayTimer = null;
  let betaAutoAiCountdownTimer = null;
  let betaAutoAiCountdown = 0;
  let betaVideoRendering = false;
  const BETA_GEMINI_LOCK_MS = 60000;
  const BETA_AUTO_AI_IDLE_MS = 5000;
  const BETA_AUTO_AI_COUNTDOWN_SECONDS = 10;
  const BETA_AI_PROVIDER_STORAGE_KEY = 'storymaker_beta_ai_provider';

  function betaGetAiProvider() {
    // Firefox/Tampermonkey 브라우저 Worker 전송은 임시 중지한다.
    return 'api';
  }

  function betaSetAiProvider(_provider) {
    const safeProvider = 'api';
    if (betaUi.aiProviderBrowser) {
      betaUi.aiProviderBrowser.checked = false;
      betaUi.aiProviderBrowser.disabled = true;
    }
    if (betaUi.aiProviderApi) betaUi.aiProviderApi.checked = true;
    localStorage.setItem(BETA_AI_PROVIDER_STORAGE_KEY, safeProvider);
  }

  function betaInitAiProvider() {
    betaSetAiProvider('api');
    betaUi.aiProviderApi?.addEventListener('change', () => betaSetAiProvider('api'));
  }

  function betaSetStatus(message, progress = 0) {
    betaUi.status.textContent = String(message || '').replaceAll('Gemini', 'AI');
    if (betaUi.progressBar) {
      betaUi.progressBar.style.width = `${Math.max(0, Math.min(100, progress))}%`;
      betaUi.progressBar.classList.toggle('complete', progress >= 100);
    }
    if (betaUi.statusBox) betaUi.statusBox.classList.toggle('idle', progress <= 0 || progress >= 100);
  }


  function betaStopPromptAnimation() {
    if (betaPromptAnimation) clearInterval(betaPromptAnimation);
    betaPromptAnimation = null;
  }

  async function betaStartPromptAnimation() {
    betaStopPromptAnimation();
    betaAiCompletionState = false;
    if (!betaCurrentJobId) return;
    try {
      const data = await betaRequest(`/beta-api/gemini-worker/prompt/${encodeURIComponent(betaCurrentJobId)}`);
      const lines = String(data.prompt || '')
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      if (!lines.length) return;
      let index = 0;
      const interval = 150; // 150ms 간격으로 한줄씩
      betaSetStatus(`AI 프롬프트 전송 시작 · ${lines[index]}`, 19);
      
      betaPromptAnimation = setInterval(() => {
        index += 1;
        if (index >= lines.length) {
          betaStopPromptAnimation();
          if (betaAiCompletionState) {
            betaSetStatus('AI 원고 생성이 완료되었습니다. 채널별 결과를 확인하세요.', 100);
          }
          return;
        }
        
        // 프롬프트 애니메이션 진행률 20~99%
        const progress = Math.min(99, 19 + Math.round((index / lines.length) * 80));
        
        if (betaAiCompletionState) {
          // AI가 먼저 완료되었어도 프롬프트 애니메이션을 끝까지 보여줌
          betaSetStatus(`[AI 응답 완료] 프롬프트 확인 중 · ${lines[index]}`, 100);
        } else {
          // AI 생성 중에는 번쩍이는 프로그레스 바와 함께 보여줌
          betaSetStatus(`AI 프롬프트 전송 중 · ${lines[index]}`, progress);
        }
      }, interval);
    } catch (_) {
      betaStopPromptAnimation();
    }
  }

  async function betaRequest(url, options = {}) {
    const response = await fetch(url, { cache: 'no-store', ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    return data;
  }

  function betaEscapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function betaPlainToRichHtml(value, key = '') {
    const lines = String(value || '').replace(/\r\n?/g, '\n').split('\n');
    let previousBlank = true;
    return lines.map((raw) => {
      const line = raw.trim();
      if (!line) { previousBlank = true; return ''; }
      const safe = betaEscapeHtml(line).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      if (/^[-_=·•─━]{3,}$/.test(line)) { previousBlank = true; return '<hr>'; }
      if (['본문', '블로그 본문', '추천 제목 5개', '추천 제목', '해시태그', '상담 안내'].includes(line)) {
        previousBlank = false;
        return `${['본문', '블로그 본문'].includes(line) ? '<hr>' : ''}<h2>${safe}</h2>`;
      }
      if (/^(여자|남자)\s*:/.test(line) && /^PODCAST_/.test(key)) {
        previousBlank = false;
        return `<p class="rich-dialogue">${safe.replace(/^([^:]+:)/, '<strong>$1</strong>')}</p>`;
      }
      const heading = previousBlank && line.length <= 42 && !/[.!?。]$/.test(line) && !/^[-•#]/.test(line) && !/^PODCAST_/.test(key);
      previousBlank = false;
      return heading ? `<h3>${safe}</h3>` : `<p>${safe}</p>`;
    }).join('');
  }

  function betaChannelHtml(item, key) {
    return String(item?.html || '').trim() || betaPlainToRichHtml(item?.content || '', key);
  }

  function betaCleanMarkdownLine(line) {
    return String(line || '')
      .trim()
      .replace(/^#{1,6}\s+/, '')
      .replace(/^[-*+]\s+/, '')
      .replace(/^>\s+/, '')
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/__(.+?)__/g, '$1')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\[(.+?)\]\((.+?)\)/g, '$1')
      .replace(/\s*=+\s*$/g, '')
      .trim();
  }

  function betaWrapKoreanLine(line, maxLength = 24) {
    const source = betaCleanMarkdownLine(line);
    if (source.length <= maxLength) return source;
    const words = source.split(/\s+/).filter(Boolean);
    const rows = [];
    let current = '';
    words.forEach((word) => {
      if (!current) {
        current = word;
        return;
      }
      if ((current + ' ' + word).length <= maxLength) {
        current += ' ' + word;
      } else {
        rows.push(current);
        current = word;
      }
    });
    if (current) rows.push(current);
    return rows.join('\n');
  }

  function betaWrappedCopyHtml(line, maxLength = 24) {
    return betaWrapKoreanLine(line, maxLength)
      .split('\n')
      .map((row) => betaEscapeHtml(row))
      .join('<br>');
  }

  function betaBlogCopyHtml(item) {
    const rawLines = String(item?.content || '').replace(/\r\n?/g, '\n').split('\n');
    let previousBlank = true;
    let titleUsed = false;
    const html = rawLines.map((raw) => {
      const originalLine = raw.trim();
      const line = betaCleanMarkdownLine(originalLine);
      if (!line) {
        previousBlank = true;
        return '<p style="margin:0 0 18px 0;"><br></p>';
      }
      if (/^BETA\s+SHORTFORM\s+STUDIO$/i.test(line)) return '';
      if (/^[-_=·•─━]{3,}$/.test(originalLine)) {
        previousBlank = true;
        return '<hr style="border:0;border-top:1px solid #d8dde6;margin:28px 0 24px 0;width:100%;">';
      }
      const isHashTag = /^#/.test(originalLine) && !/^#{1,6}\s+/.test(originalLine);
      const isNumberTitle = /^\d+\./.test(line);
      const isMarkdownHeading = /^#{1,6}\s+/.test(originalLine);
      const isMainTitle = !titleUsed && !isNumberTitle && !isMarkdownHeading && line.length <= 48 && !/[.!?。]$/.test(line);
      const isSubTitle = isMarkdownHeading || (!isMainTitle && previousBlank && line.length <= 34 && !/[.!?。]$/.test(line) && !isHashTag && !isNumberTitle);
      previousBlank = false;
      if (isNumberTitle) {
        return `<p style="margin:0 0 8px 0;font-size:15px;line-height:1.7;color:#222;">${betaEscapeHtml(line)}</p>`;
      }
      if (isMainTitle) {
        titleUsed = true;
        return `<h2 style="margin:26px 0 18px 0;font-size:24px;line-height:1.45;color:#111;font-weight:800;">${betaWrappedCopyHtml(line, 24)}</h2>`;
      }
      if (isSubTitle) {
        return `<hr style="border:0;border-top:1px solid #d8dde6;margin:30px 0 22px 0;width:100%;"><h3 style="margin:0 0 16px 0;font-size:21px;line-height:1.5;color:#111;font-weight:800;">${betaWrappedCopyHtml(line, 24)}</h3>`;
      }
      return `<p style="margin:0 0 14px 0;font-size:16px;line-height:1.9;color:#222;">${betaWrappedCopyHtml(line, 24)}</p>`;
    }).join('');
    return html;
  }

  function betaNaverCopyHtml(item, key) {
    const channelHtml = key === 'BLOG' ? betaBlogCopyHtml(item) : betaChannelHtml(item, key);
    return `<!doctype html><html><head><meta charset="utf-8"></head><body><article style="font-family:Arial,'Malgun Gothic',sans-serif;font-size:16px;line-height:1.9;color:#222;background:#fff;max-width:720px;">${channelHtml}</article></body></html>`;
  }

  function betaPlainTextFromHtml(html) {
    const box = document.createElement('div');
    box.innerHTML = html;
    return (box.innerText || box.textContent || '').replace(/\n{3,}/g, '\n\n').trim();
  }

  async function betaCopyChannelForNaver(item, key, button) {
    const html = betaNaverCopyHtml(item, key);
    const text = betaPlainTextFromHtml(html) || String(item?.content || '').trim();
    if (!text) throw new Error('복사할 내용이 없습니다.');
    if (navigator.clipboard && window.ClipboardItem) {
      const payload = new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([text], { type: 'text/plain' })
      });
      await navigator.clipboard.write([payload]);
    } else if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', 'readonly');
      area.style.position = 'fixed';
      area.style.left = '-9999px';
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
    if (button) {
      const original = button.textContent;
      button.textContent = '복사 완료';
      button.disabled = true;
      window.setTimeout(() => {
        button.textContent = original || '복사';
        button.disabled = false;
      }, 1400);
    }
    betaSetStatus(`${item?.label || key} 내용을 네이버 붙여넣기 형식으로 복사했습니다.`, 100);
  }


  function betaShowChannel(channels, order, index) {
    const key = order[index];
    const item = channels[key];
    if (!item) return;
    betaUi.slotTabs.querySelectorAll('.slot-tab').forEach((button, buttonIndex) => {
      button.classList.toggle('active', buttonIndex === index);
    });
    betaUi.slots.innerHTML = `
      <h3>${betaEscapeHtml(item.label || key)}</h3>
      <div class="slot-meta" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end;">
        <button type="button" class="slot-copy-button" style="border:1px solid #42d9c8;background:#0b3b36;color:#e9fffb;border-radius:999px;padding:8px 14px;font-weight:800;cursor:pointer;min-width:118px;">복사</button>
      </div>
      <div class="slot-script rich-channel-content">${betaChannelHtml(item, key)}</div>`;
    const copyButton = betaUi.slots.querySelector('.slot-copy-button');
    if (copyButton) {
      copyButton.addEventListener('click', async () => {
        try {
          await betaCopyChannelForNaver(item, key, copyButton);
        } catch (error) {
          betaSetStatus(`복사 실패: ${error.message}`);
        }
      });
    }
  }

  function betaConnectShortform(job) {
    const content = job?.content || {};
    const channels = content.channels || {};
    const ready = Boolean(betaCurrentJobId && (content.podcast_50 || channels.PODCAST_50?.content));
    if (!betaUi.shortformIntegrated) return;
    betaUi.shortformIntegrated.hidden = !ready;
    if (!ready) return;
    if (betaUi.shortformStatus) betaUi.shortformStatus.textContent = '업체정보·블로그 제목·팟캐스트50·업로드 미디어를 연결했습니다.';
    if (window.StoryMakerBetaInlineShortform?.loadJob) {
      window.StoryMakerBetaInlineShortform.loadJob(betaCurrentJobId).catch((error) => {
        if (betaUi.shortformStatus) betaUi.shortformStatus.textContent = `숏폼 연결 실패: ${error.message}`;
      });
    }
  }

  function betaShowContent(job) {
    const content = job.content || {};
    const channels = content.channels || {};
    const order = Array.isArray(content.channel_order) ? content.channel_order : [];
    const readyForRender = order.length === 8 && Boolean(content.podcast_50 || channels.PODCAST_50?.content);
    betaConnectShortform(job);
    if (betaUi.renderHandoff) betaUi.renderHandoff.hidden = !readyForRender;
    const podcastButton = document.getElementById('mp3');
    if (podcastButton) podcastButton.disabled = !readyForRender;
    if (readyForRender && betaCurrentJobId && window.StoryMakerBetaBrowserRenderer) {
      window.StoryMakerBetaBrowserRenderer.prime(betaCurrentJobId);
    }
    if (order.length === 8) {
      betaUi.slotTabs.innerHTML = order.map((key, index) => {
        const item = channels[key] || {};
        return `<button type="button" class="slot-tab${index === 0 ? ' active' : ''}" data-channel-index="${index}">${betaEscapeHtml(item.label || key)}</button>`;
      }).join('');
      betaUi.slotTabs.querySelectorAll('.slot-tab').forEach((button) => {
        button.addEventListener('click', () => betaShowChannel(channels, order, Number(button.dataset.channelIndex || 0)));
      });
      betaShowChannel(channels, order, 0);
    } else {
      betaUi.slotTabs.innerHTML = '<button type="button" class="slot-tab active" disabled>채널 대기</button>';
      betaUi.slots.innerHTML = '<div class="slot-empty">AI SNS 8채널 결과가 아직 저장되지 않았습니다.</div>';
    }
    betaUi.content.textContent = `제목
${content.title || ''}

설명
${content.description || ''}

팟캐스트 80초 기본 대본
${content.podcast_80 || content.podcast_script || content.script || ''}\r\n\r\n썸네일 프롬프트\r\n${content.thumbnail_prompt || '아직 생성되지 않음'}`;
    betaUi.content.hidden = order.length !== 8;
  }

  function betaSetActionButtonLabel(button, step, text) {
    if (!button) return;
    button.innerHTML = `<span class="beta-step-circle">${step}</span>${text}`;
  }

  function betaInputsReady() {
    return Boolean(betaUi.topic?.value.trim() && betaUi.images?.files?.length);
  }

  function betaRefreshActionGlow() {
    if (betaUi.gemini) {
      betaUi.gemini.classList.toggle('beta-action-breathe', !betaUi.gemini.disabled && betaInputsReady());
    }
    if (betaUi.geminiRetry) {
      betaUi.geminiRetry.classList.toggle('beta-action-breathe', !betaUi.geminiRetry.disabled);
    }
  }

  function betaCancelAutoAiGeneration() {
    if (betaAutoAiDelayTimer) window.clearTimeout(betaAutoAiDelayTimer);
    if (betaAutoAiCountdownTimer) window.clearInterval(betaAutoAiCountdownTimer);
    betaAutoAiDelayTimer = null;
    betaAutoAiCountdownTimer = null;
    betaAutoAiCountdown = 0;
    betaSetActionButtonLabel(betaUi.geminiRetry, 4, 'AI원고 생성');
  }

  function betaScheduleAutoAiGeneration() {
    betaCancelAutoAiGeneration();
    const scheduledJobId = betaCurrentJobId;
    if (!scheduledJobId || !betaUi.geminiRetry || betaUi.geminiRetry.disabled) return;
    betaAutoAiDelayTimer = window.setTimeout(() => {
      betaAutoAiDelayTimer = null;
      if (scheduledJobId !== betaCurrentJobId || betaUi.geminiRetry.disabled) return;
      betaAutoAiCountdown = BETA_AUTO_AI_COUNTDOWN_SECONDS;
      betaSetActionButtonLabel(betaUi.geminiRetry, 4, `AI원고 생성 · 자동 ${betaAutoAiCountdown}초`);
      betaSetStatus(`AI원고 생성을 누르지 않아 ${betaAutoAiCountdown}초 후 자동으로 시작합니다.`, 15);
      betaAutoAiCountdownTimer = window.setInterval(() => {
        if (scheduledJobId !== betaCurrentJobId || betaUi.geminiRetry.disabled) {
          betaCancelAutoAiGeneration();
          return;
        }
        betaAutoAiCountdown -= 1;
        if (betaAutoAiCountdown <= 0) {
          betaCancelAutoAiGeneration();
          betaSetStatus('AI원고 생성을 자동으로 시작합니다.', 18);
          betaGenerateGemini();
          return;
        }
        betaSetActionButtonLabel(betaUi.geminiRetry, 4, `AI원고 생성 · 자동 ${betaAutoAiCountdown}초`);
        betaSetStatus(`AI원고 생성을 누르지 않아 ${betaAutoAiCountdown}초 후 자동으로 시작합니다.`, 15);
      }, 1000);
    }, BETA_AUTO_AI_IDLE_MS);
  }

  function betaApplyVideoRenderingLock(rendering, message = '') {
    betaVideoRendering = Boolean(rendering);
    if (betaUi.gemini) {
      betaUi.gemini.disabled = betaVideoRendering || betaUi.gemini.dataset.workflowDisabled === '1';
      betaUi.gemini.title = betaVideoRendering ? '영상 생성 중에는 프롬프트를 다시 생성할 수 없습니다.' : '';
    }
    if (betaUi.geminiRetry) {
      betaUi.geminiRetry.disabled = betaVideoRendering || betaUi.geminiRetry.dataset.workflowDisabled === '1';
      betaUi.geminiRetry.title = betaVideoRendering ? '영상 생성 중에는 AI 원고를 다시 생성할 수 없습니다.' : '';
    }
    if (betaUi.newWork) {
      betaUi.newWork.disabled = betaVideoRendering;
      betaUi.newWork.title = betaVideoRendering ? '영상 생성이 끝난 뒤 새 작업을 시작할 수 있습니다.' : '현재 작업 캐시를 지우고 새 작업 시작';
    }
    if (message && betaUi.shortformStatus) betaUi.shortformStatus.textContent = message;
    betaRefreshActionGlow();
  }

  function betaSetGeminiButtons({ promptDisabled = false, aiDisabled = true } = {}) {
    if (betaUi.gemini) betaUi.gemini.dataset.workflowDisabled = promptDisabled ? '1' : '0';
    if (betaUi.geminiRetry) {
      betaUi.geminiRetry.hidden = false;
      betaUi.geminiRetry.dataset.workflowDisabled = aiDisabled ? '1' : '0';
    }
    betaApplyVideoRenderingLock(betaVideoRendering);
  }

  function betaClearWorkCache(storage) {
    const prefixes = [
      'storymaker_beta_', 'storymaker_thumbnail_', 'storymaker_auto_',
      'storymaker_podcast_', 'storymaker_shortform_'
    ];
    const exactKeys = ['storymaker_current_job', 'storymaker_current_job_id'];
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index) || '';
      if (exactKeys.includes(key) || prefixes.some((prefix) => key.startsWith(prefix))) storage.removeItem(key);
    }
  }

  function betaStartNewWork() {
    if (betaVideoRendering) {
      betaSetStatus('영상 생성 중에는 새 작업을 시작할 수 없습니다. 영상 생성이 끝난 뒤 다시 눌러주세요.');
      return;
    }
    if (!window.confirm('현재 화면의 작업 내용과 Beta 제작 캐시를 모두 지우고 새 작업을 시작할까요?')) return;
    betaCancelAutoAiGeneration();
    betaStopPromptAnimation();
    if (betaGeminiWatchTimer) window.clearInterval(betaGeminiWatchTimer);
    betaGeminiWatchTimer = null;
    betaClearWorkCache(sessionStorage);
    betaClearWorkCache(localStorage);
    location.reload();
  }

  function betaUnlockAiAfterTimeout() {
    betaGeminiLockedUntil = Date.now() + BETA_GEMINI_LOCK_MS;
    window.setTimeout(() => {
      if (Date.now() < betaGeminiLockedUntil) return;
      if (betaUi.geminiRetry) betaUi.geminiRetry.disabled = false;
      betaSetStatus('AI 응답이 지연되고 있습니다. 기존 작업은 계속 확인 중이며, 필요하면 AI원고 생성을 다시 누르세요.', 40);
      betaStartBackgroundGeminiWatch();
    }, BETA_GEMINI_LOCK_MS + 50);
  }

  function betaStartBackgroundGeminiWatch() {
    if (betaGeminiWatchTimer || !betaCurrentJobId) return;
    betaGeminiWatchTimer = window.setInterval(async () => {
      try {
        const status = await betaRequest(`/beta-api/gemini-worker/status?job_id=${encodeURIComponent(betaCurrentJobId)}`);
        const worker = status.data || {};
        if (worker.status === 'completed') {
          window.clearInterval(betaGeminiWatchTimer);
          betaGeminiWatchTimer = null;
          await betaCompleteGeminiUi();
        }
      } catch (_) {}
    }, 3000);
  }

  async function betaCreateJob(event) {
    event.preventDefault();
    const topicText = String(betaUi.topic?.value || '').trim();
    if (topicText.length <= 20) {
      const warningMessage = `기초 콘텐츠가 ${topicText.length}자입니다. 내용을 20자보다 길게 작성해 주세요.`;
      betaSetStatus(warningMessage, 0);
      window.alert(warningMessage);
      betaUi.topic?.focus({ preventScroll: true });
      betaUi.topic?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    if (!betaUi.images.files.length) {
      betaSetStatus('이미지를 한 장 이상 선택하세요.');
      return;
    }
    const allSelectedVideos = Array.from(betaUi.videos?.files || []);
    const selectedVideos = allSelectedVideos.slice(0, 3);
    if (allSelectedVideos.length > 3) {
      betaSetStatus(`동영상은 최대 3개까지 사용됩니다. 선택한 ${allSelectedVideos.length}개 중 앞의 3개만 적용했습니다.`);
    }
    const body = new FormData();
    body.append('business_name', betaUi.businessName.value.trim());
    body.append('business_region', betaUi.businessRegion.value.trim());
    body.append('business_region_alias', betaUi.businessRegionAlias?.value.trim() || '');
    body.append('business_service', betaUi.businessService.value.trim());
    body.append('business_industry_key', betaUi.businessIndustryKey?.value.trim() || '');
    body.append('business_phone', betaUi.businessPhone.value.trim());
    body.append('business_keywords', JSON.stringify(betaSelectedBusinessProfile?.keywords || []));
    body.append('business_default_tones', JSON.stringify(betaSelectedBusinessProfile?.default_tones || []));
    body.append('business_persona_text', String(betaSelectedBusinessProfile?.content || '').trim());
    body.append('business_blog_content_length', String(betaSelectedBusinessProfile?.blog_content_length || 1500));
    body.append('topic', betaUi.topic.value.trim());
    for (const file of betaUi.images.files) body.append('images', file);
    for (const file of selectedVideos) body.append('videos', file);
    betaSetGeminiButtons({ promptDisabled: true, aiDisabled: true });
    betaSetStatus('작업 공간과 AI 프롬프트를 준비하는 중...', 8);
    try {
      const data = await betaRequest('/beta-api/jobs', { method: 'POST', body });
      betaCurrentJobId = data.job.beta_job_id;
      sessionStorage.setItem('storymaker_beta_current_job', betaCurrentJobId);
      betaUi.jobId.textContent = betaCurrentJobId;
      if (window.StoryMakerBetaBrowserRenderer) {
        window.StoryMakerBetaBrowserRenderer.prime(betaCurrentJobId);
      }
      betaShowContent(data.job);
      await betaRequest(`/beta-api/gemini-worker/jobs/${encodeURIComponent(betaCurrentJobId)}/prepare`, { method: 'POST' });
      betaSetStatus('프롬프트 준비 완료. ④ AI원고 생성을 눌러주세요.', 15);
      betaSetGeminiButtons({ promptDisabled: true, aiDisabled: false });
      betaScheduleAutoAiGeneration();
    } catch (error) {
      betaSetStatus(`프롬프트 생성 실패: ${error.message}`);
      betaSetGeminiButtons({ promptDisabled: false, aiDisabled: true });
    }
  }

  async function betaInspect(label) {
    if (!betaCurrentJobId) return;
    try {
      const data = await betaRequest(`/beta-api/steps/jobs/${encodeURIComponent(betaCurrentJobId)}/inspect`);
      betaUi.debug.textContent = `${label}\n${JSON.stringify(data.checks, null, 2)}`;
    } catch (error) {
      betaUi.debug.textContent = `${label} 실패\n${error.message}`;
    }
  }

  async function betaCreateSupertonicVoice(settings = {}) {
    if (!betaCurrentJobId) return;
    if (betaUi.prepareBrowser) betaUi.prepareBrowser.disabled = true;
    betaSetStatus('Beta 전용 Supertonic 7790에서 실제 음성을 생성하는 중...', 35);
    try {
      const data = await betaRequest(`/beta-api/steps/jobs/${encodeURIComponent(betaCurrentJobId)}/supertonic`, { method: 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(settings || {}) });
      betaUi.audio.src = `/beta-api/jobs/${encodeURIComponent(betaCurrentJobId)}/file/audio?t=${Date.now()}`;
      betaUi.audio.hidden = false;
      if (betaUi.debug) betaUi.debug.textContent = `Supertonic 생성 성공\n${JSON.stringify(data, null, 2)}`;
      if (window.StoryMakerBetaBrowserRenderer) {
        window.StoryMakerBetaBrowserRenderer.setJob(betaCurrentJobId);
        await window.StoryMakerBetaBrowserRenderer.loadJob();
      }
      betaSetStatus('Beta Supertonic 음성 준비 완료. 팟캐스트를 생성합니다.', 45);
      return true;
    } catch (error) {
      if (betaUi.debug) betaUi.debug.textContent = `Supertonic 생성 실패\n${error.message}`;
      betaSetStatus(`Supertonic 실패: ${error.message}`);
      if (betaUi.prepareBrowser) betaUi.prepareBrowser.disabled = false;
      throw error;
    }
  }

  window.StoryMakerBetaPrepareVoice = betaCreateSupertonicVoice;

  async function betaQueueThumbnail() {
    // Firefox/Tampermonkey 썸네일 송수신은 임시 중지한다.
    return false;
  }
  window.StoryMakerBetaQueueThumbnail = betaQueueThumbnail;


  async function betaCompleteGeminiUi() {
    betaAiCompletionState = true;
    const data = await betaRequest(`/beta-api/jobs/${encodeURIComponent(betaCurrentJobId)}`);
    betaShowContent(data.job);
    if (!betaPromptAnimation) {
      betaSetStatus('AI 원고 생성이 완료되었습니다. 채널별 결과를 확인하세요.', 100);
    }
    betaGeminiLockedUntil = 0;
    betaSetGeminiButtons({ promptDisabled: false, aiDisabled: true });
    requestAnimationFrame(() => {
      betaUi.channelResults?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      betaUi.channelResults?.focus({ preventScroll: true });
    });
  }

  async function betaRetryGemini() {
    return betaGenerateGemini();
  }

  async function betaWaitForGemini() {
    const startedAt = Date.now();
    let sentAt = 0;
    while (Date.now() - startedAt < BETA_GEMINI_LOCK_MS) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const status = await betaRequest(`/beta-api/gemini-worker/status?job_id=${encodeURIComponent(betaCurrentJobId)}`);
      const worker = status.data || {};
      const workerStatus = worker.status || '대기 중';
      if (workerStatus === 'sent' && !sentAt) {
        sentAt = Date.now();
      }
      const progress = workerStatus === 'sent' ? 42 : workerStatus === 'claimed' ? 30 : workerStatus === 'pending' ? 22 : 18;
      if (!betaPromptAnimation) {
        const statusLabel = worker.worker_id === 'backend-gemini-api' ? 'AI API 상태' : 'AI 웹 Worker 상태';
        betaSetStatus(`${statusLabel}: ${workerStatus}`, progress);
      }
      if (workerStatus === 'error') {
        betaStopPromptAnimation();
        betaGeminiLockedUntil = 0;
        betaSetGeminiButtons({ promptDisabled: true, aiDisabled: false });
        throw new Error(worker.error || 'AI Worker 처리 실패');
      }
      if (workerStatus === 'completed') {
        await betaCompleteGeminiUi();
        return true;
      }
    }
    betaStopPromptAnimation();
    betaSetGeminiButtons({ promptDisabled: true, aiDisabled: false });
    betaStartBackgroundGeminiWatch();
    return false;
  }

  async function betaGenerateGemini() {
    betaCancelAutoAiGeneration();
    if (!betaCurrentJobId || !betaUi.geminiRetry) return;
    if (Date.now() < betaGeminiLockedUntil) return;
    const provider = betaGetAiProvider();
    betaSetGeminiButtons({ promptDisabled: true, aiDisabled: true });
    betaUnlockAiAfterTimeout();
    betaSetStatus(provider === 'api' ? 'Beta AI API에서 원고를 생성하는 중...' : '준비된 프롬프트를 브라우저 Gemini 전송 창구에 등록하는 중...', 18);
    try {
      const endpoint = provider === 'api' ? 'api' : 'queue';
      await betaRequest(`/beta-api/gemini-worker/jobs/${encodeURIComponent(betaCurrentJobId)}/${endpoint}`, { method: 'POST' });
      await betaStartPromptAnimation();
      await betaWaitForGemini();
    } catch (error) {
      betaGeminiLockedUntil = 0;
      betaSetStatus(`AI 원고 생성 실패: ${error.message}`);
      betaSetGeminiButtons({ promptDisabled: true, aiDisabled: false });
    }
  }

  async function betaRenderJob() {
    if (!betaCurrentJobId) return;
    const body = new FormData();
    body.append('music_volume', betaUi.musicVolume.value || '0.16');
    betaUi.render.disabled = true;
    betaSetStatus('오프라인 한국어 음성 생성 중...', 25);
    try {
      const data = await betaRequest(`/beta-api/jobs/${encodeURIComponent(betaCurrentJobId)}/render`, { method: 'POST', body });
      betaUi.preview.src = `${data.video_url}?t=${Date.now()}`;
      betaUi.preview.hidden = false;
      betaUi.audio.src = `/beta-api/jobs/${encodeURIComponent(betaCurrentJobId)}/file/audio?t=${Date.now()}`;
      betaUi.audio.hidden = false;
      betaShowContent(data.job);
      betaSetStatus(`PODCAST_80 기반 팟캐스트 MP3와 최종 MP4 생성 완료 · ${data.job.duration_seconds || 0}초`, 100);
    } catch (error) {
      betaSetStatus(`MP4 제작 실패: ${error.message}`);
      betaUi.render.disabled = false;
    }
  }

  let betaPromptMode = 'edit';

  function betaClosePromptModal() {
    if (betaUi.promptModal) betaUi.promptModal.hidden = true;
  }

  async function betaOpenPromptModal(mode) {
    betaPromptMode = mode === 'send' ? 'send' : 'edit';
    if (!betaUi.promptModal || !betaUi.promptEditor) return;
    betaUi.promptModal.hidden = false;
    betaUi.promptMessage.textContent = '불러오는 중...';
    betaUi.promptEditor.value = '';
    betaUi.promptEditor.readOnly = betaPromptMode === 'send';
    betaUi.promptSave.hidden = betaPromptMode === 'send';
    betaUi.promptCopy.hidden = betaPromptMode !== 'send';
    betaUi.promptModalTitle.textContent = betaPromptMode === 'send' ? '전송 프롬프트' : '프롬프트 편집';
    try {
      if (betaPromptMode === 'send') {
        if (!betaCurrentJobId) throw new Error('먼저 ③ 프롬프트 생성을 실행해 주세요.');
        const data = await betaRequest(`/beta-api/gemini-worker/prompt/${encodeURIComponent(betaCurrentJobId)}`);
        betaUi.promptEditor.value = String(data.prompt || '');
        betaUi.promptMeta.textContent = `현재 작업 ${betaCurrentJobId} · ${betaUi.promptEditor.value.length.toLocaleString()}자 · 읽기 전용`;
      } else {
        const industryKey = String(betaUi.businessIndustryKey?.value || '').trim();
        const query = new URLSearchParams({ industry_key: industryKey });
        const data = await betaRequest(`/beta-api/gemini/admin/prompt?${query.toString()}`);
        betaUi.promptEditor.value = String(data.prompt || '');
        betaUi.promptMeta.textContent = `${data.prompt_key || '프롬프트'} v${data.version || '-'} · 업종 ${industryKey || '기본'} · ${betaUi.promptEditor.value.length.toLocaleString()}자`;
      }
      betaUi.promptMessage.textContent = '';
      betaUi.promptEditor.focus();
    } catch (error) {
      betaUi.promptMessage.textContent = error.message;
    }
  }

  async function betaSavePromptTemplate() {
    const prompt = String(betaUi.promptEditor?.value || '').trim();
    betaUi.promptSave.disabled = true;
    betaUi.promptMessage.textContent = '저장 중...';
    try {
      const industryKey = String(betaUi.businessIndustryKey?.value || '').trim();
      const query = new URLSearchParams({ industry_key: industryKey });
      const data = await betaRequest(`/beta-api/gemini/admin/prompt?${query.toString()}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      betaUi.promptMessage.textContent = `저장 완료 · ${data.prompt_key || '프롬프트'} v${data.version || '-'} · 다음 생성부터 적용`;
      betaUi.promptMeta.textContent = `${data.prompt_key || '프롬프트'} v${data.version || '-'} · 업종 ${industryKey || '기본'} · ${prompt.length.toLocaleString()}자`;
    } catch (error) {
      betaUi.promptMessage.textContent = `저장 실패: ${error.message}`;
    } finally {
      betaUi.promptSave.disabled = false;
    }
  }

  async function betaCopySendPrompt() {
    const value = String(betaUi.promptEditor?.value || '');
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      betaUi.promptMessage.textContent = '전송 프롬프트를 복사했습니다.';
    } catch (_) {
      betaUi.promptEditor.select();
      document.execCommand('copy');
      betaUi.promptMessage.textContent = '전송 프롬프트를 복사했습니다.';
    }
  }

  function betaEnablePromptAdminTools(role) {
    const isAdmin = String(role || '').toLowerCase() === 'admin';
    if (betaUi.promptEditOpen) betaUi.promptEditOpen.hidden = !isAdmin;
    if (betaUi.promptSendOpen) betaUi.promptSendOpen.hidden = !isAdmin;
  }

  betaUi.newWork?.addEventListener('click', betaStartNewWork);
  betaUi.promptEditOpen?.addEventListener('click', () => betaOpenPromptModal('edit'));
  betaUi.promptSendOpen?.addEventListener('click', () => betaOpenPromptModal('send'));
  betaUi.promptSave?.addEventListener('click', betaSavePromptTemplate);
  betaUi.promptCopy?.addEventListener('click', betaCopySendPrompt);
  betaUi.promptModalX?.addEventListener('click', betaClosePromptModal);
  betaUi.promptModalClose?.addEventListener('click', betaClosePromptModal);
  betaUi.promptModal?.addEventListener('pointerdown', (event) => {
    if (event.target === betaUi.promptModal) betaClosePromptModal();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && betaUi.promptModal && !betaUi.promptModal.hidden) betaClosePromptModal();
  });

  window.addEventListener('storymaker:shortform-render-state', (event) => {
    const rendering = Boolean(event.detail?.rendering);
    betaApplyVideoRenderingLock(rendering, rendering ? '영상 생성 중 · 상단 생성 버튼과 새 작업을 잠갔습니다.' : '영상 생성 완료 · 상단 버튼 잠금을 해제했습니다.');
  });
  betaApplyVideoRenderingLock(betaVideoRendering);

  betaInitAiProvider();
  betaUi.form.addEventListener('submit', betaCreateJob);
  if (betaUi.geminiRetry) betaUi.geminiRetry.addEventListener('click', () => {
    betaCancelAutoAiGeneration();
    betaRetryGemini();
  });
  betaUi.topic?.addEventListener('input', betaRefreshActionGlow);
  betaUi.images?.addEventListener('change', betaRefreshActionGlow);
  betaUi.videos?.addEventListener('change', () => {
    const count = Number(betaUi.videos?.files?.length || 0);
    if (count > 3) {
      betaSetStatus(`동영상은 최대 3개까지 사용됩니다. 선택한 ${count}개 중 앞의 3개만 적용했습니다.`);
    }
    betaRefreshActionGlow();
  });
  betaRefreshActionGlow();
  if (betaUi.prepareBrowser) betaUi.prepareBrowser.addEventListener('click', betaCreateSupertonicVoice);
  async function betaRestoreCurrentJob() {
    if (!betaCurrentJobId) return;
    betaUi.jobId.textContent = betaCurrentJobId;
    betaSetGeminiButtons({ promptDisabled: false, aiDisabled: true });
    try {
      const data = await betaRequest(`/beta-api/jobs/${encodeURIComponent(betaCurrentJobId)}`);
      betaShowContent(data.job);
      const order = Array.isArray(data.job?.content?.channel_order) ? data.job.content.channel_order : [];
      if (order.length === 8) {
        betaSetStatus('저장된 AI SNS 8채널을 불러왔습니다.', 100);
        betaSetGeminiButtons({ promptDisabled: false, aiDisabled: true });
      } else {
        await betaRequest(`/beta-api/gemini-worker/jobs/${encodeURIComponent(betaCurrentJobId)}/prepare`, { method: 'POST' });
        betaSetStatus('현재 작업의 프롬프트가 준비되었습니다. ④ AI원고 생성을 눌러주세요.', 15);
        betaSetGeminiButtons({ promptDisabled: true, aiDisabled: false });
        betaScheduleAutoAiGeneration();
      }
    } catch (error) {
      betaSetStatus(`현재 작업 불러오기 실패: ${error.message}`);
    }
  }

  window.addEventListener('message', (event) => {
    if (event.origin !== location.origin || !event.data) return;
    if (event.data.type === 'storymaker-beta-shortform-ready') {
      if (betaUi.shortformStatus) betaUi.shortformStatus.textContent = '현재 작업 데이터와 사용자 기본 설정 연결 완료';
    }
    if (event.data.type === 'storymaker-beta-shortform-error') {
      if (betaUi.shortformStatus) betaUi.shortformStatus.textContent = `숏폼 연결 확인 필요 · ${event.data.error || '알 수 없는 오류'}`;
    }
  });

  window.addEventListener('storymaker-beta-renderer-ready', () => {
    if (betaCurrentJobId && window.StoryMakerBetaBrowserRenderer) {
      window.StoryMakerBetaBrowserRenderer.prime(betaCurrentJobId);
    }
  });

  betaRestoreCurrentJob();

  function applyV1BusinessProfile(profile, { force = false } = {}) {
    if (!profile) return;
    betaSelectedBusinessProfile = profile;
    const pairs = [
      [betaUi.businessName, profile.name],
      [betaUi.businessRegion, profile.region],
      [betaUi.businessRegionAlias, profile.region_alias],
      [betaUi.businessService, profile.service],
      [betaUi.businessIndustryKey, profile.industry_key],
      [betaUi.businessPhone, profile.phone],
    ];
    for (const [input, value] of pairs) {
      if (!input) continue;
      const nextValue = String(value || '').trim();
      if (force || !input.value.trim()) input.value = nextValue;
    }
  }

  async function fillFromV1Profile() {
    try {
      const response = await fetch('/v1-api/beta/profile', { cache: 'no-store', credentials: 'include' });
      const data = await response.json();
      betaEnablePromptAdminTools(data?.role);
      const profile = data?.profile;
      const profiles = Array.isArray(data?.profiles) ? data.profiles.filter(item => item?.name) : [];
      if (!response.ok || !profile) return;

      applyV1BusinessProfile(profile);

      if (profiles.length > 1 && betaUi.businessProfileSelect) {
        betaUi.businessProfileSelect.innerHTML = profiles.map(item => {
          const selected = String(item.id) === String(profile.id) ? ' selected' : '';
          const label = item.is_default ? `★ ${item.name}` : item.name;
          return `<option value="${String(item.id).replace(/"/g, '&quot;')}"${selected}>${label.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</option>`;
        }).join('');
        betaUi.businessProfileSelect.hidden = false;
        betaUi.businessName.hidden = true;
        betaUi.businessProfileSelect.addEventListener('change', () => {
          const selectedProfile = profiles.find(item => String(item.id) === betaUi.businessProfileSelect.value);
          if (!selectedProfile) return;
          applyV1BusinessProfile(selectedProfile, { force: true });
          betaUi.status.textContent = `${selectedProfile.name} 업체 정보로 변경했습니다.`;
        });
      }

      betaUi.status.textContent = profiles.length > 1
        ? '등록된 업체를 선택해 현재 제작 업체를 변경할 수 있습니다.'
        : '업체정보를 불러왔습니다. 수정 후 반영 가능!';
    } catch (_) {
      // V1 로그인이 없거나 연결되지 않으면 기존 수동 입력을 유지합니다.
    }
  }

  fillFromV1Profile();
})();
