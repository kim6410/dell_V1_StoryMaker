// ==UserScript==
// @name         StoryMaker V1 ONLY - Isolated Gemini Worker
// @namespace    storymaker-v1-only-isolated
// @version      1.4.29-v1-windows.1
// @updateURL    https://app.mystorymaker.net/v1/storymaker-gemini-worker-v1.user.js
// @downloadURL  https://app.mystorymaker.net/v1/storymaker-gemini-worker-v1.user.js
// @match        https://gemini.google.com/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      app.mystorymaker.net
// ==/UserScript==

(function () {
    'use strict';

    const BACKEND_URL = 'https://app.mystorymaker.net';
    const V1_MEDIA_URL = 'https://app.mystorymaker.net';
    const POLL_MS = 1200;
    const WORKER_VERSION = '1.4.29-v1-windows.1-current-response-only';
    const SINGLETON_KEY = '__STORYMAKER_GEMINI_WORKER_V1_SINGLETON__';
    const SENT_JOBS_KEY = 'storymaker_gemini_v1_sent_job_ids';
    const HANDLED_JOBS_KEY = 'storymaker_gemini_v1_handled_job_ids';
    const JOB_LOCK_KEY_PREFIX = 'storymaker_gemini_v1_job_lock_';
    const JOB_LOCK_TTL_MS = 30 * 1000;
    const POLL_LEADER_KEY = 'storymaker_gemini_v1_poll_leader';
    const POLL_LEADER_TTL_MS = 5000;
    const POLL_TAB_ID = (crypto?.randomUUID?.() || ('tab-' + Date.now() + '-' + Math.random().toString(16).slice(2)));
    const THUMBNAIL_RESET_JOB_KEY = 'storymaker_thumbnail_reset_job_id';

    // Gemini 한 대화창에 결과가 너무 많이 쌓이면 느려지므로,
    // 지정 횟수 이상 처리 후 새 대화창으로 이동한다.
    const MAX_JOBS_PER_CHAT = 1;
    const CHAT_JOB_COUNT_KEY = 'storymaker_gemini_v1_jobs_in_current_chat';

    const previousWorker = window[SINGLETON_KEY];
    if (previousWorker?.timerId) {
        clearInterval(previousWorker.timerId);
        previousWorker.stopped = true;
        console.warn('[StoryMaker Gemini V1] 이전 worker interval 정리');
    }

    const workerState = {
        version: WORKER_VERSION,
        startedAt: Date.now(),
        timerId: null,
        stopped: false
    };
    window[SINGLETON_KEY] = workerState;

    function tryAcquirePollLeadership() {
        const now = Date.now();
        try {
            const current = JSON.parse(localStorage.getItem(POLL_LEADER_KEY) || 'null');
            if (current && current.tab_id !== POLL_TAB_ID && Number(current.expires_at || 0) > now) {
                return false;
            }
            const next = { tab_id: POLL_TAB_ID, expires_at: now + POLL_LEADER_TTL_MS, version: WORKER_VERSION };
            localStorage.setItem(POLL_LEADER_KEY, JSON.stringify(next));
            const verified = JSON.parse(localStorage.getItem(POLL_LEADER_KEY) || 'null');
            return verified?.tab_id === POLL_TAB_ID;
        } catch (error) {
            console.warn(workerTag(), 'poll leader lock fallback:', error);
            return true;
        }
    }

    function releasePollLeadership() {
        try {
            const current = JSON.parse(localStorage.getItem(POLL_LEADER_KEY) || 'null');
            if (current?.tab_id === POLL_TAB_ID) {
                localStorage.removeItem(POLL_LEADER_KEY);
            }
        } catch (error) {}
    }

    window.addEventListener('pagehide', releasePollLeadership);
    window.addEventListener('beforeunload', releasePollLeadership);

    let running = false;
    const processingJobs = new Set();
    let lastHandledJobId = localStorage.getItem('storymaker_v1_last_gemini_job_id') || '';

    const originalLog = console.log;
    const originalError = console.error;
    const originalWarn = console.warn;

    function logToServer(type, args) {
        const msg = args.map(arg => {
            if (arg && typeof arg === 'object') {
                try { return JSON.stringify(arg); } catch (e) { return String(arg); }
            }
            return String(arg);
        }).join(' ');

        if (type === 'error') originalError('[GEMINI-WORKER]', msg);
        else if (type === 'warn') originalWarn('[GEMINI-WORKER]', msg);
        else originalLog('[GEMINI-WORKER]', msg);

        GM_xmlhttpRequest({
            method: 'POST',
            url: BACKEND_URL + '/v1-api/test/worker-log',
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify({ message: `[${type.toUpperCase()}] ${msg}` }),
            onload: () => {},
            onerror: () => {}
        });
    }

    console.log = (...args) => logToServer('log', args);
    console.error = (...args) => logToServer('error', args);
    console.warn = (...args) => logToServer('warn', args);

    function workerTag() {
        return '[StoryMaker Gemini ' + WORKER_VERSION + ']';
    }

    function healthLog(stage, data = {}) {
        console.log(workerTag(), '[HEALTH]', stage, data);
    }

    console.log(workerTag(), 'polling worker start');

    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function request(method, url, data) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method,
                url,
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                data: data ? JSON.stringify(data) : undefined,
                onload: res => {
                    let parsed = {};
                    try {
                        parsed = JSON.parse(res.responseText || '{}');
                    } catch (e) {
                        if (res.status >= 200 && res.status < 300) reject(e);
                    }
                    if (res.status < 200 || res.status >= 300) {
                        const message = parsed?.detail || parsed?.message || parsed?.error || `HTTP ${res.status}`;
                        reject(new Error(message));
                        return;
                    }
                    resolve(parsed);
                },
                onerror: reject
            });
        });
    }

    function normalizeImageUrl(url) {
        if (!url) return '';
        if (url.startsWith('http://') || url.startsWith('https://')) return url;
        let cleanPath = url;
        if (cleanPath.startsWith('/home/bourne/StoryMaker_1/output_results')) {
            cleanPath = cleanPath.replace('/home/bourne/StoryMaker_1/output_results', '/data/output_results');
        }
        if (cleanPath.startsWith('/data/output_results')) {
            return V1_MEDIA_URL + cleanPath;
        }
        return BACKEND_URL + '/' + cleanPath.replace(/^\//, '');
    }

    function fetchImageAsFile(url, filename) {
        const targetUrl = normalizeImageUrl(url);
        console.log('[StoryMaker Gemini 1.3.7] 이미지 다운로드 시도:', targetUrl);
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: targetUrl,
                responseType: 'blob',
                onload: res => {
                    if (res.status === 200) {
                        const blob = res.response;
                        const mimeType = blob.type || 'image/jpeg';
                        resolve(new File([blob], filename, { type: mimeType }));
                    } else {
                        reject(new Error('이미지 다운로드 실패: ' + res.status));
                    }
                },
                onerror: reject
            });
        });
    }

    function queryAllDeep(selector) {
        const found = [];
        const visited = new Set();
        const visit = root => {
            if (!root || visited.has(root)) return;
            visited.add(root);
            try {
                found.push(...root.querySelectorAll(selector));
                for (const el of root.querySelectorAll('*')) {
                    if (el.shadowRoot) visit(el.shadowRoot);
                }
                for (const iframe of root.querySelectorAll('iframe')) {
                    try {
                        if (iframe.contentDocument) visit(iframe.contentDocument);
                    } catch (e) {}
                }
            } catch (e) {}
        };
        visit(document);
        return [...new Set(found)];
    }

    function getFileInput() {
        const inputs = queryAllDeep('input[type="file"]');
        if (!inputs.length) return null;
        return inputs.find(i => (i.accept || '').toLowerCase().includes('image') || (i.accept || '').includes('*')) || inputs[0];
    }

    function getUploadButton() {
        // 3. getUploadButton()의 탐색 대상을 button뿐 아니라 아래까지 확장해 주세요.
        // button, [role="button"], [aria-label], div[aria-label], span[aria-label], mat-icon
        const candidates = queryAllDeep('button, [role="button"], [aria-label], div[aria-label], span[aria-label], mat-icon');

        // 4. aria-label에 "업로드 및 도구"가 포함된 요소를 최우선으로 찾고, closest('button, [role="button"]')가 있으면 그것을 클릭 대상으로 사용해 주세요.
        const exactAriaMatch = candidates.find(el => {
            const aria = el.getAttribute('aria-label') || '';
            return isVisible(el) && aria.includes('업로드 및 도구');
        });

        if (exactAriaMatch) {
            const clickTarget = exactAriaMatch.closest('button, [role="button"]') || exactAriaMatch;
            // 6. 기존 upload_button_found_exact_upload_tool 로그는 유지해 주세요.
            healthLog('upload_button_found_exact_upload_tool', {
                text: (clickTarget.innerText || '').trim().slice(0, 60),
                aria: clickTarget.getAttribute('aria-label') || '',
                title: clickTarget.getAttribute('title') || ''
            });
            return clickTarget;
        }

        const selectors = [
            'button[aria-label*="파일"]',
            'button[aria-label*="첨부"]',
            'button[aria-label*="이미지"]',
            'button[aria-label*="Upload"]',
            'button[aria-label*="upload"]',
            'button[aria-label*="Attach"]',
            'button[aria-label*="attach"]',
            'button[title*="파일"]',
            'button[title*="첨부"]',
            'button[title*="이미지"]',
            'button[title*="Upload"]',
            'button[title*="Attach"]'
        ];

        for (const selector of selectors) {
            const btn = queryAllDeep(selector).find(isEnabledButton);
            if (btn) {
                healthLog('upload_button_found_by_selector', {
                    selector,
                    text: (btn.innerText || '').trim().slice(0, 60),
                    aria: btn.getAttribute('aria-label') || '',
                    title: btn.getAttribute('title') || ''
                });
                return btn;
            }
        }

        const iconButton = queryAllDeep('button mat-icon, mat-icon')
            .map(icon => {
                const text = (icon.textContent || '').trim().toLowerCase();
                return ['add', 'add_photo_alternate', 'attach_file', 'upload', 'image', 'photo_library', 'add_circle'].includes(text)
                    ? icon.closest('button')
                    : null;
            })
            .find(isEnabledButton);

        if (iconButton) {
            healthLog('upload_button_found_by_icon', {
                text: (iconButton.innerText || '').trim().slice(0, 60),
                aria: iconButton.getAttribute('aria-label') || '',
                title: iconButton.getAttribute('title') || ''
            });
            return iconButton;
        }

        // 5. upload_button_candidates_debug 로그에는 tag, role, aria-label, text, visible 정보를 sample로 남겨 주세요.
        healthLog('upload_button_candidates_debug', {
            count: candidates.length,
            sample: candidates.slice(0, 30).map((el, idx) => {
                return {
                    idx,
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || '',
                    'aria-label': el.getAttribute('aria-label') || '',
                    text: (el.innerText || el.textContent || '').trim().slice(0, 40),
                    visible: isVisible(el)
                };
            })
        });

        const visibleButtons = candidates.filter(isEnabledButton);

        // 6. 기존 exactUploadTool 변수명과 upload_button_found_exact_upload_tool 로그는 유지해 주세요.
        const exactUploadTool = visibleButtons.find(btn => {
            const label = [
                btn.getAttribute('aria-label'),
                btn.getAttribute('title'),
                btn.innerText
            ].filter(Boolean).join(' ').toLowerCase();

            return (
                label.includes('업로드 및 도구') ||
                label.includes('upload and tools') ||
                label.includes('add files') ||
                label.includes('attach')
            );
        });

        if (exactUploadTool) {
            healthLog('upload_button_found_exact_upload_tool', {
                text: (exactUploadTool.innerText || '').trim().slice(0, 60),
                aria: exactUploadTool.getAttribute('aria-label') || '',
                title: exactUploadTool.getAttribute('title') || ''
            });
            return exactUploadTool;
        }

        const fallback = visibleButtons.find(btn => {
            const rect = btn.getBoundingClientRect();
            const label = [
                btn.getAttribute('aria-label'),
                btn.getAttribute('title'),
                btn.innerText
            ].filter(Boolean).join(' ').toLowerCase();

            if (label.includes('설정')) return false;
            if (label.includes('마이크')) return false;
            if (label.includes('복사')) return false;
            if (label.includes('수정')) return false;
            if (label.includes('다운로드')) return false;

            return rect.left < window.innerWidth * 0.65 && rect.top > window.innerHeight * 0.70;
        }) || null;

        if (fallback) {
            healthLog('upload_button_found_by_fallback', {
                text: (fallback.innerText || '').trim().slice(0, 60),
                aria: fallback.getAttribute('aria-label') || '',
                title: fallback.getAttribute('title') || ''
            });
        }

        return fallback;
    }

    async function waitForFileInputAfterMenu() {
        console.log(workerTag(), '메뉴 클릭 후 file input 대기 시작');
        for (let i = 0; i < 30; i++) {
            const inputs = queryAllDeep('input[type="file"]');
            healthLog('file_input_poll', {
                try: i,
                count: inputs.length,
                inputs: inputs.map(x => ({
                    accept: x.accept,
                    multiple: x.multiple,
                    disabled: x.disabled,
                    display: window.getComputedStyle(x).display
                }))
            });

            const input = getFileInput();
            if (input) {
                healthLog('file_input_found_after_menu', { accept: input.accept || '', multiple: !!input.multiple });
                return input;
            }
            await delay(500);
        }
        healthLog('file_input_missing_after_menu');
        return null;
    }

    async function openGeminiUploadPicker() {
        // 1. openGeminiUploadPicker() 시작 부분에서 waitForPromptBox(15000)를 먼저 호출해 입력창 렌더링을 보장해 주세요.
        const box = await waitForPromptBox(15000);
        // 2. promptBox 확인 로그 upload_prompt_box_before_button 를 추가해 주세요.
        healthLog('upload_prompt_box_before_button', {
            found: !!box,
            tag: box ? box.tagName : null,
            id: box ? box.id : null,
            className: box ? box.className : null
        });

        const existing = getFileInput();
        if (existing) {
            healthLog('file_input_found_existing', { accept: existing.accept || '', multiple: !!existing.multiple });
            return existing;
        }

        // 7. 업로드 버튼을 못 찾으면 즉시 실패하지 말고 1초 간격으로 최대 15초 재시도하게 해 주세요.
        let btn = null;
        for (let attempt = 1; attempt <= 15; attempt++) {
            btn = getUploadButton();
            if (btn) break;
            if (attempt < 15) {
                await delay(1000);
            }
        }

        if (!btn) {
            healthLog('upload_button_missing');
            console.warn(workerTag(), '첨부 버튼 없음');
            return null;
        }

        healthLog('upload_button_found', {
            text: (btn.innerText || '').trim().slice(0, 80),
            aria: btn.getAttribute('aria-label') || '',
            title: btn.getAttribute('title') || ''
        });

        btn.click();
        healthLog('upload_button_clicked');
        console.log(workerTag(), '첨부 버튼 클릭 완료');

        for (let i = 0; i < 60; i++) {
            const input = getFileInput();
            if (input) {
                healthLog('file_input_found', { accept: input.accept || '', multiple: !!input.multiple });
                return input;
            }

            const candidates = queryAllDeep('button, [role="menuitem"], [role="option"], [role="button"], div, span')
                .filter(isVisible)
                .map((el, idx) => {
                    const text = [
                        el.getAttribute('aria-label'),
                        el.getAttribute('title'),
                        el.innerText,
                        el.textContent
                    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();

                    return { el, idx, text, lower: text.toLowerCase() };
                })
                .filter(x => x.text.length > 0 && x.text.length < 120);

            if (i === 1 || i === 2 || i === 8 || i === 20) {
                healthLog('upload_menu_candidates', {
                    count: candidates.length,
                    sample: candidates.slice(0, 30).map(x => x.text)
                });
            }

            const fileUploadMenu = candidates.find(x => {
                const t = x.text.trim();
                return (
                    t === '파일 업로드' ||
                    t.startsWith('파일 업로드') ||
                    t === 'Upload files' ||
                    t === 'Upload file'
                );
            });

            if (fileUploadMenu) {
                healthLog('upload_menu_file_upload_clicked', {
                    text: fileUploadMenu.text.slice(0, 100)
                });
                fileUploadMenu.el.click();
                return await waitForFileInputAfterMenu();
            }

            const strongMenu = candidates.find(x => {
                const t = x.lower;
                return (
                    t.includes('upload file') ||
                    t.includes('upload files') ||
                    t.includes('choose file') ||
                    t.includes('파일 업로드') ||
                    t.includes('파일 선택')
                );
            });

            if (strongMenu) {
                healthLog('upload_menu_clicked', { text: strongMenu.text.slice(0, 100) });
                strongMenu.el.click();
                return await waitForFileInputAfterMenu();
            }

            await delay(500);
        }

        healthLog('file_input_missing_after_menu');
        return null;
    }

    function collectUploadPreviewElements() {
        const selectors = [
            'g-file-upload-preview',
            '[class*="preview"]',
            'mat-chip',
            'mat-chip-row',
            'attachment-chip',
            '[class*="thumbnail"]',
            'img[src^="blob:"]',
            'img[src^="data:image"]'
        ];
        return [...new Set(selectors.flatMap(selector => queryAllDeep(selector)))].filter(isVisible);
    }

    async function waitForUploadPreviews(expectedCount) {
        console.log('[StoryMaker Gemini 1.3.7] 업로드 프리뷰 대기:', expectedCount);
        for (let i = 0; i < 45; i++) {
            await delay(1000);
            const previews = collectUploadPreviewElements();
            const blobImages = queryAllDeep('img').filter(img => ((img.currentSrc || img.src || '').startsWith('blob:')) && isVisible(img));
            const count = Math.max(previews.length, blobImages.length);
            console.log('[StoryMaker Gemini 1.3.7] 프리뷰 감지:', count, 'previews:', previews.length, 'blobImages:', blobImages.length);
            if (count >= expectedCount) return true;
        }
        return false;
    }

    function cleanThumbnailPrompt(promptText) {
        return String(promptText || '').split('\n').filter(line => {
            return !line.includes('/data/output_results') && !line.includes('/home/bourne');
        }).join('\n').trim();
    }

    function dispatchUploadDropEvents(files, dt) {
        const targets = [
            getPromptBox(),
            queryAllDeep('rich-textarea')[0],
            queryAllDeep('[contenteditable="true"]')[0],
            document.body
        ].filter(Boolean);

        for (const target of [...new Set(targets)]) {
            for (const type of ['dragenter', 'dragover', 'drop']) {
                try {
                    const ev = new DragEvent(type, {
                        bubbles: true,
                        cancelable: true,
                        dataTransfer: dt
                    });
                    target.dispatchEvent(ev);
                } catch (e) {
                    const ev = new Event(type, { bubbles: true, cancelable: true });
                    try { Object.defineProperty(ev, 'dataTransfer', { value: dt }); } catch (_) {}
                    target.dispatchEvent(ev);
                }
            }
        }
        console.log('[StoryMaker Gemini 1.3.7] drag/drop 이벤트 주입 완료:', files.length);
    }

    async function uploadByDropFirst(files) {
        if (!files || !files.length) return false;

        const dt = new DataTransfer();
        files.forEach(file => dt.items.add(file));

        const targets = [
            getPromptBox(),
            queryAllDeep('rich-textarea')[0],
            queryAllDeep('[contenteditable="true"]')[0],
            document.body
        ].filter(Boolean);

        const uniqueTargets = [...new Set(targets)];

        healthLog('drop_upload_attempt', { files: files.length, targets: uniqueTargets.length });

        dispatchUploadDropEvents(files, dt);

        console.log('[StoryMaker Gemini V1] drag/drop 이벤트 주입 완료, 프리뷰 대기 시작 (최대 8초)');

        for (let i = 0; i < 8; i++) {
            await delay(1000);
            const previews = collectUploadPreviewElements();
            const blobImages = queryAllDeep('img').filter(img => ((img.currentSrc || img.src || '').startsWith('blob:')) && isVisible(img));
            const count = Math.max(previews.length, blobImages.length);
            console.log('[StoryMaker Gemini V1] Drop 프리뷰 감지:', count, 'expected:', files.length);
            if (count >= files.length) {
                await delay(3000);
                healthLog('drop_upload_settle_wait_done', { ms: 3000 });
                return true;
            }
        }
        return false;
    }

    async function uploadImagesToGemini(imageUrls) {
        if (!imageUrls || !imageUrls.length) return false;
        const urls = imageUrls.slice(0, 3);
        console.log('[StoryMaker Gemini 1.3.7] 썸네일 이미지 첨부 시작:', urls.length);
        const files = await Promise.all(urls.map((url, idx) => {
            const ext = (url.split('.').pop() || 'jpg').split('?')[0] || 'jpg';
            return fetchImageAsFile(url, 'storymaker_thumb_' + (idx + 1) + '.' + ext);
        }));

        // 1. 이미지 파일 다운로드 후, 먼저 drag/drop 업로드 시도
        const dropSuccess = await uploadByDropFirst(files);
        if (dropSuccess) {
            console.log('[StoryMaker Gemini 1.3.7] drag/drop 업로드 성공');
            return true;
        }

        console.log('[StoryMaker Gemini 1.3.7] drag/drop 업로드 실패, 기존 Picker 방식 Fallback 실행');

        // 4. false일 때만 기존 openGeminiUploadPicker() 방식으로 fallback 실행
        const fileInput = await openGeminiUploadPicker();
        if (!fileInput) {
            console.warn('[StoryMaker Gemini 1.3.7] file input 없음');
            return false;
        }
        try { fileInput.multiple = true; } catch (e) {}
        const dt = new DataTransfer();
        files.forEach(file => dt.items.add(file));
        fileInput.files = dt.files;
        fileInput.dispatchEvent(new Event('input', { bubbles: true }));
        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
        dispatchUploadDropEvents(files, dt);
        console.log('[StoryMaker Gemini 1.3.7] file input 주입 완료:', fileInput.files.length);
        return await waitForUploadPreviews(files.length);
    }

    function getImageFingerprint(img) {
        const src = String(img.currentSrc || img.src || '').trim();
        const alt = String(img.alt || '').trim();
        const width = Number(img.naturalWidth || img.width || 0);
        const height = Number(img.naturalHeight || img.height || 0);
        return [src, alt, width, height].join('|');
    }

    function snapshotExistingGeminiImages() {
        return new Set(queryAllDeep('img').map(getImageFingerprint).filter(Boolean));
    }

    function findLatestAssistantResponseContainer() {
        const selectors = [
            'message-content',
            'div.model-response-text',
            'div.response-container-content',
            '[data-message-author-role="assistant"]',
            '[data-role="assistant"]',
            'model-response',
            '.response-container',
            '[class*="model-response"]',
            '[class*="response-container"]',
            '[class*="conversation-turn"]'
        ];
        const seen = new Set();
        const nodes = [];
        for (const selector of selectors) {
            for (const el of queryAllDeep(selector)) {
                if (!seen.has(el) && isVisible(el)) {
                    seen.add(el);
                    nodes.push(el);
                }
            }
        }
        return nodes.length ? nodes[nodes.length - 1] : null;
    }

    function imageHasAncestorText(img, pattern) {
        let el = img;
        for (let i = 0; el && i < 6; i++, el = el.parentElement) {
            const text = [el.tagName, el.getAttribute('role'), el.getAttribute('aria-label'), el.getAttribute('class'), el.getAttribute('data-testid')]
                .join(' ')
                .toLowerCase();
            if (pattern.test(text)) return true;
        }
        return false;
    }

    function hasGeneratedImageAncestor(img) {
        let el = img;
        for (let i = 0; el && i < 6; i++, el = el.parentElement) {
            const text = [el.tagName, el.getAttribute('class'), el.getAttribute('data-testid')]
                .join(' ')
                .toLowerCase();
            if (/single-image|generated-image|luminous-layout|generated-images/.test(text)) return true;
        }
        return false;
    }

    function isNearComposerUploadPreview(img) {
        let el = img;
        for (let i = 0; el && i < 8; i++, el = el.parentElement) {
            const text = [el.tagName, el.getAttribute('role'), el.getAttribute('aria-label'), el.getAttribute('class'), el.getAttribute('data-testid')]
                .join(' ')
                .toLowerCase();
            if (/preview-image-button|g-file-upload-preview/.test(text)) return true;
            if (/rich-textarea|ql-editor|composer|contenteditable|input/.test(text) && /attachment|upload|preview|file/.test(text)) return true;
            if (/attachment-container/.test(text) && !/generated-images/.test(text) && imageHasAncestorText(el, /rich-textarea|ql-editor|composer|contenteditable|input/)) return true;
        }
        return false;
    }

    function isExcludedGeneratedImage(img, beforeSnapshot = null) {
        const src = String(img.currentSrc || img.src || '').trim();
        const alt = String(img.alt || img.getAttribute('aria-label') || '').toLowerCase();
        const className = String(img.className || '').toLowerCase();
        const width = Number(img.naturalWidth || img.getBoundingClientRect().width || 0);
        const height = Number(img.naturalHeight || img.getBoundingClientRect().height || 0);
        const combined = [src, alt, className].join(' ').toLowerCase();
        if (!src || src.startsWith('data:image/svg') || src.includes('image/svg+xml')) return true;
        if (beforeSnapshot && beforeSnapshot.has(getImageFingerprint(img))) return true;
        if (width < 300 || height < 500) return true;
        if (/gemini_sparkle|logo|avatar|favicon|icon/.test(combined)) return true;
        if (imageHasAncestorText(img, /sparkle-image-container|xap-count-badge-container|header|nav|aside|footer|avatar|logo|icon/)) return true;
        if (isNearComposerUploadPreview(img)) return true;
        return false;
    }

    function scoreGeneratedImageCandidate(img, assistantContainer, beforeSnapshot = null) {
        const src = String(img.currentSrc || img.src || '').trim();
        const width = Number(img.naturalWidth || img.getBoundingClientRect().width || 0);
        const height = Number(img.naturalHeight || img.getBoundingClientRect().height || 0);
        const ratio = width > 0 ? height / width : 0;
        let score = 0;
        const reasons = [];
        const inAssistant = !!(assistantContainer && assistantContainer.contains(img));
        const isNew = !beforeSnapshot || !beforeSnapshot.has(getImageFingerprint(img));
        const generatedParent = hasGeneratedImageAncestor(img);
        if (inAssistant) { score += 120; reasons.push('assistant'); }
        if (generatedParent) { score += 90; reasons.push('generated_parent'); }
        if (isNew) { score += 120; reasons.push('new'); }
        if (inAssistant && isNew && src.startsWith('blob:')) { score += 80; reasons.push('new_assistant_blob'); }
        if (width >= 500 && height >= 800) { score += 30; reasons.push('large'); }
        if (ratio >= 1.5) { score += 20; reasons.push('vertical'); }
        const ratioDelta = Math.abs(ratio - (16 / 9));
        if (ratioDelta <= 0.12) { score += 50; reasons.push('near_9_16'); }
        else if (ratioDelta <= 0.28) { score += 35; reasons.push('close_9_16'); }
        if (isNearComposerUploadPreview(img)) { score -= 200; reasons.push('upload_preview'); }
        if (/gemini_sparkle|logo|avatar|favicon|icon|svg/.test([src, img.alt || '', img.className || ''].join(' ').toLowerCase())) { score -= 300; reasons.push('ui_asset'); }
        if (width < 300 || height < 500) { score -= 200; reasons.push('too_small'); }
        return { src, width, height, ratio, score, reasons };
    }

    function collectGeneratedImages(beforeSnapshot = null) {
        const assistantContainer = findLatestAssistantResponseContainer();
        const scopedImgs = assistantContainer ? [...assistantContainer.querySelectorAll('img')] : [];
        const fallbackImgs = queryAllDeep('img');
        const allImgs = [...new Set([...scopedImgs, ...fallbackImgs])];
        const candidates = [];

        for (const img of allImgs) {
            const src = String(img.currentSrc || img.src || '').trim();
            if (!src || isExcludedGeneratedImage(img, beforeSnapshot)) continue;
            const candidate = scoreGeneratedImageCandidate(img, assistantContainer, beforeSnapshot);
            if (candidate.score >= 100) candidates.push(candidate);
        }

        candidates.sort((a, b) => b.score - a.score || (b.width * b.height) - (a.width * a.height));
        if (!candidates.length) {
            console.log('[StoryMaker Gemini V1] 최종 썸네일 후보 없음. 전체 img 개수:', allImgs.length);
            return [];
        }
        console.log('[StoryMaker Gemini V1] 최종 썸네일 후보 선택:', JSON.stringify({
            count: candidates.length,
            selected: { w: candidates[0].width, h: candidates[0].height, score: candidates[0].score, reasons: candidates[0].reasons }
        }));
        return [candidates[0]];
    }

    function collectGeneratedImageUrls(beforeSnapshot = null) {
        const images = collectGeneratedImages(beforeSnapshot);
        const urls = images.map(item => item.src).filter(Boolean);
        return [...new Set(urls)].slice(0, 1);
    }

    function blobToDataUrl(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ''));
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    function convertImgToDataUrlViaCanvas(url) {
        try {
            const imgEl = queryAllDeep('img').find(img => (img.currentSrc || img.src) === url);
            if (!imgEl) return '';

            const canvas = document.createElement('canvas');
            const w = imgEl.naturalWidth || imgEl.width || 200;
            const h = imgEl.naturalHeight || imgEl.height || 200;
            canvas.width = w;
            canvas.height = h;

            const ctx = canvas.getContext('2d');
            if (!ctx) return '';
            
            ctx.drawImage(imgEl, 0, 0, w, h);
            const dataUrl = canvas.toDataURL('image/png');
            if (dataUrl && dataUrl.length > 1000) {
                healthLog('thumbnail_canvas_dataurl_convert_done', { url: url.slice(0, 80), length: dataUrl.length });
                return dataUrl;
            }
            return '';
        } catch (e) {
            console.warn('[StoryMaker Gemini V1] Canvas 변환 실패:', e);
            return '';
        }
    }

    function pageContextImageToDataUrl(url, timeoutMs = 10000) {
        return new Promise((resolve) => {
            const requestId = 'storymaker_shadow_bridge_' + Date.now() + '_' + Math.random().toString(36).slice(2);

            function cleanup() {
                window.removeEventListener('STORYMAKER_IMAGE_DATAURL_RESULT', onResult);
                const script = document.getElementById(requestId);
                if (script) script.remove();
            }

            const timer = setTimeout(() => {
                cleanup();
                healthLog('thumbnail_shadow_bridge_timeout', {
                    url: String(url || '').slice(0, 120)
                });
                resolve('');
            }, timeoutMs);

            function onResult(event) {
                const detail = event.detail || {};
                if (detail.requestId !== requestId) return;

                clearTimeout(timer);
                cleanup();

                if (detail.ok && detail.dataUrl && detail.dataUrl.length > 1000) {
                    healthLog('thumbnail_shadow_bridge_done', {
                        length: detail.dataUrl.length,
                        width: detail.width || 0,
                        height: detail.height || 0,
                        foundCount: detail.foundCount || 0
                    });
                    resolve(detail.dataUrl);
                } else {
                    healthLog('thumbnail_shadow_bridge_failed', {
                        message: detail.message || 'empty',
                        foundCount: detail.foundCount || 0
                    });
                    resolve('');
                }
            }

            window.addEventListener('STORYMAKER_IMAGE_DATAURL_RESULT', onResult);

            const script = document.createElement('script');
            script.id = requestId;
            script.textContent = `
                (function () {
                    const requestId = ${JSON.stringify(requestId)};
                    const targetUrl = ${JSON.stringify(url)};

                    function reply(payload) {
                        window.dispatchEvent(new CustomEvent('STORYMAKER_IMAGE_DATAURL_RESULT', {
                            detail: Object.assign({ requestId }, payload)
                        }));
                    }

                    function isVisible(el) {
                        try {
                            const style = window.getComputedStyle(el);
                            const rect = el.getBoundingClientRect();
                            return style.display !== 'none'
                                && style.visibility !== 'hidden'
                                && rect.width > 0
                                && rect.height > 0;
                        } catch (e) {
                            return false;
                        }
                    }

                    function queryAllDeep(root, selector, out, visited) {
                        if (!root || visited.has(root)) return;
                        visited.add(root);

                        try {
                            if (root.querySelectorAll) {
                                out.push(...root.querySelectorAll(selector));

                                for (const el of root.querySelectorAll('*')) {
                                    if (el.shadowRoot) {
                                        queryAllDeep(el.shadowRoot, selector, out, visited);
                                    }
                                }
                            }
                        } catch (e) {}
                    }

                    function waitImageReady(img, timeoutMs) {
                        return new Promise(resolve => {
                            const started = Date.now();

                            function check() {
                                const rect = img.getBoundingClientRect();
                                const w = img.naturalWidth || rect.width || 0;
                                const h = img.naturalHeight || rect.height || 0;

                                if (img.complete && w > 100 && h > 100) {
                                    resolve(true);
                                    return;
                                }

                                if (Date.now() - started > timeoutMs) {
                                    resolve(false);
                                    return;
                                }

                                setTimeout(check, 250);
                            }

                            check();
                        });
                    }

                    (async function run() {
                        try {
                            const imgs = [];
                            queryAllDeep(document, 'img', imgs, new Set());

                            const uniqueImgs = Array.from(new Set(imgs));
                            const candidates = uniqueImgs.filter(img => {
                                const src = img.currentSrc || img.src || '';
                                if (!src) return false;
                                if (!isVisible(img)) return false;
                                return src === targetUrl;
                            });

                            let img = candidates[0];

                            if (!img) {
                                const largeImgs = uniqueImgs
                                    .filter(isVisible)
                                    .map((x, idx) => {
                                        const rect = x.getBoundingClientRect();
                                        const w = x.naturalWidth || rect.width || 0;
                                        const h = x.naturalHeight || rect.height || 0;
                                        const src = x.currentSrc || x.src || '';
                                        const ratio = w > 0 ? h / w : 0;
                                        return { img: x, idx, w, h, area: w * h, ratio, src };
                                    })
                                    .filter(x => x.src && x.w > 200 && x.h > 200)
                                    .sort((a, b) => {
                                        const ap = a.ratio > 1.2 ? 1 : 0;
                                        const bp = b.ratio > 1.2 ? 1 : 0;
                                        if (ap !== bp) return bp - ap;
                                        return b.area - a.area;
                                    });

                                img = largeImgs[0] ? largeImgs[0].img : null;
                            }

                            if (!img) {
                                reply({
                                    ok: false,
                                    message: 'image not found in shadow dom',
                                    foundCount: uniqueImgs.length
                                });
                                return;
                            }

                            const ready = await waitImageReady(img, 8000);
                            if (!ready) {
                                reply({
                                    ok: false,
                                    message: 'image not ready',
                                    foundCount: uniqueImgs.length
                                });
                                return;
                            }

                            const rect = img.getBoundingClientRect();
                            const w = Math.round(img.naturalWidth || rect.width || 0);
                            const h = Math.round(img.naturalHeight || rect.height || 0);

                            if (w < 100 || h < 100) {
                                reply({
                                    ok: false,
                                    message: 'image too small',
                                    width: w,
                                    height: h,
                                    foundCount: uniqueImgs.length
                                });
                                return;
                            }

                            const canvas = document.createElement('canvas');
                            canvas.width = w;
                            canvas.height = h;

                            const ctx = canvas.getContext('2d');
                            if (!ctx) {
                                reply({
                                    ok: false,
                                    message: 'canvas context missing'
                                });
                                return;
                            }

                            ctx.drawImage(img, 0, 0, w, h);

                            const dataUrl = canvas.toDataURL('image/png');

                            if (!dataUrl || dataUrl.length < 1000) {
                                reply({
                                    ok: false,
                                    message: 'dataUrl too short',
                                    length: dataUrl ? dataUrl.length : 0
                                });
                                return;
                            }

                            reply({
                                ok: true,
                                dataUrl,
                                length: dataUrl.length,
                                width: w,
                                height: h,
                                foundCount: uniqueImgs.length
                            });
                        } catch (e) {
                            reply({
                                ok: false,
                                message: e && e.message ? e.message : String(e)
                            });
                        }
                    })();
                })();
            `;
            document.documentElement.appendChild(script);
        });
    }

    async function imageUrlToDataUrl(url) {
        if (!url) return '';
        if (url.startsWith('data:image/')) return url;

        try {
            const res = await fetch(url);
            if (!res.ok) throw new Error('Fetch status not ok');
            const blob = await res.blob();
            if (!String(blob.type || '').startsWith('image/')) throw new Error('Blob type not image');
            const dataUrl = await blobToDataUrl(blob);
            if (dataUrl && dataUrl.length > 1000) return dataUrl;
        } catch (e) {
            console.warn('[StoryMaker Gemini V1] 생성 이미지 fetch 변환 실패:', url, e);
        }

        const canvasDataUrl = convertImgToDataUrlViaCanvas(url);
        if (canvasDataUrl && canvasDataUrl.length > 1000) return canvasDataUrl;

        return await pageContextImageToDataUrl(url);
    }

    function debugDumpGeneratedImageDom() {
        console.log('[StoryMaker Gemini V1] thumbnail_dom_debug_start');

        try {
            // 1. 마지막 Assistant Response 영역 찾기
            const responseContainers = [
                ...document.querySelectorAll('message-content'),
                ...document.querySelectorAll('.model-response-text'),
                ...document.querySelectorAll('[class*="model-response"]'),
                ...document.querySelectorAll('[class*="response-container"]')
            ].filter(isVisible);

            const lastResponse = responseContainers[responseContainers.length - 1] || null;
            
            if (lastResponse) {
                console.log('[StoryMaker Gemini V1] 마지막 Assistant Response 발견:', {
                    tagName: lastResponse.tagName,
                    className: lastResponse.className,
                    childNodesCount: lastResponse.childNodes.length,
                    outerHTML_slice: lastResponse.outerHTML.slice(0, 3000)
                });
            } else {
                console.log('[StoryMaker Gemini V1] 마지막 Assistant Response를 찾지 못했습니다.');
            }

            // 2. 전체 img 태그 분석 (queryAllDeep 이용)
            const allImgs = queryAllDeep('img');
            console.log('[StoryMaker Gemini V1] 전체 img 개수:', allImgs.length);
            
            allImgs.forEach((img, idx) => {
                const rect = img.getBoundingClientRect();
                console.log('[StoryMaker Gemini V1] img_info', {
                    index: idx,
                    src: img.src || '',
                    currentSrc: img.currentSrc || '',
                    complete: img.complete,
                    naturalWidth: img.naturalWidth || 0,
                    naturalHeight: img.naturalHeight || 0,
                    width: img.width || 0,
                    height: img.height || 0,
                    clientWidth: img.clientWidth || 0,
                    clientHeight: img.clientHeight || 0,
                    loading: img.loading || '',
                    decoding: img.decoding || '',
                    alt: img.getAttribute('alt') || '',
                    className: img.className || '',
                    parentTag: img.parentElement ? img.parentElement.tagName : 'none',
                    parentClass: img.parentElement ? img.parentElement.className : '',
                    isVisible: isVisible(img),
                    rect: { top: rect.top, left: rect.left, width: rect.width, height: rect.height }
                });
            });

            // 3. picture 태그 분석
            const allPictures = queryAllDeep('picture');
            console.log('[StoryMaker Gemini V1] 전체 picture 개수:', allPictures.length);
            allPictures.forEach((pic, idx) => {
                console.log('[StoryMaker Gemini V1] picture_info', {
                    index: idx,
                    outerHTML_slice: pic.outerHTML.slice(0, 500)
                });
            });

            // 4. source 태그 분석
            const allSources = queryAllDeep('source');
            console.log('[StoryMaker Gemini V1] 전체 source 개수:', allSources.length);
            allSources.forEach((src, idx) => {
                console.log('[StoryMaker Gemini V1] source_info', {
                    index: idx,
                    srcset: src.getAttribute('srcset') || '',
                    type: src.getAttribute('type') || '',
                    media: src.getAttribute('media') || '',
                    parentTag: src.parentElement ? src.parentElement.tagName : 'none'
                });
            });

            // 5. canvas 태그 분석
            const allCanvases = queryAllDeep('canvas');
            console.log('[StoryMaker Gemini V1] 전체 canvas 개수:', allCanvases.length);
            allCanvases.forEach((can, idx) => {
                console.log('[StoryMaker Gemini V1] canvas_info', {
                    index: idx,
                    width: can.width,
                    height: can.height,
                    clientWidth: can.clientWidth,
                    clientHeight: can.clientHeight
                });
            });

            // 6. SVG 태그 분석
            const allSvgs = queryAllDeep('svg');
            console.log('[StoryMaker Gemini V1] 전체 svg 개수:', allSvgs.length);

            // 7. ShadowRoot 내부 이미지 분석
            let shadowRootCount = 0;
            let shadowImgCount = 0;
            const visitShadows = root => {
                if (!root) return;
                try {
                    for (const el of root.querySelectorAll('*')) {
                        if (el.shadowRoot) {
                            shadowRootCount++;
                            const shadowImgs = el.shadowRoot.querySelectorAll('img');
                            shadowImgCount += shadowImgs.length;
                            visitShadows(el.shadowRoot);
                        }
                    }
                } catch (e) {}
            };
            visitShadows(document);
            console.log('[StoryMaker Gemini V1] ShadowRoot 분석:', {
                shadowRootFound: shadowRootCount > 0,
                shadowRootCount,
                shadowImgCount
            });

            // 8. background-image 가 있는 엘리먼트 분석 (상위 20개)
            const allElements = queryAllDeep('*');
            const bgImages = [];
            for (const el of allElements) {
                try {
                    const bg = el.style.backgroundImage || window.getComputedStyle(el).backgroundImage;
                    if (bg && bg !== 'none' && bg.startsWith('url(')) {
                        bgImages.push({
                            tagName: el.tagName,
                            className: el.className,
                            backgroundImage: bg.slice(0, 150)
                        });
                        if (bgImages.length >= 20) break;
                    }
                } catch (e) {}
            }
            console.log('[StoryMaker Gemini V1] background-image 엘리먼트 (상위 20개):', bgImages);

            // 9. role="img" 또는 aria-label 이 있는 엘리먼트 분석
            const ariaImgElements = [];
            for (const el of allElements) {
                try {
                    const role = el.getAttribute('role');
                    const ariaLabel = el.getAttribute('aria-label');
                    if (role === 'img' || ariaLabel) {
                        ariaImgElements.push({
                            tagName: el.tagName,
                            className: el.className,
                            role: role || '',
                            ariaLabel: ariaLabel || ''
                        });
                        if (ariaImgElements.length >= 30) break;
                    }
                } catch (e) {}
            }
            console.log('[StoryMaker Gemini V1] role=img 또는 aria-label 엘리먼트 (상위 30개):', ariaImgElements);

            // 10. 업로드 프리뷰 이미지 분석
            const uploadPreviews = collectUploadPreviewElements();
            console.log('[StoryMaker Gemini V1] 업로드 프리뷰 이미지 개수:', uploadPreviews.length);
            uploadPreviews.forEach((el, idx) => {
                if (el.tagName.toLowerCase() === 'img') {
                    console.log('[StoryMaker Gemini V1] upload_preview_img', {
                        index: idx,
                        src: el.src || '',
                        currentSrc: el.currentSrc || ''
                    });
                } else {
                    const imgs = el.querySelectorAll('img');
                    imgs.forEach((img, imgIdx) => {
                        console.log('[StoryMaker Gemini V1] upload_preview_sub_img', {
                            index: `${idx}_${imgIdx}`,
                            src: img.src || '',
                            currentSrc: img.currentSrc || ''
                        });
                    });
                }
            });

            // 11. 현재 collectGeneratedImages() 후보 분석
            const candidates = collectGeneratedImages();
            console.log('[StoryMaker Gemini V1] 현재 collectGeneratedImages() 수집 결과 개수:', candidates.length);
            candidates.forEach((c, idx) => {
                console.log('[StoryMaker Gemini V1] collect_candidate', {
                    index: idx,
                    src: c.src.slice(0, 100),
                    width: c.width,
                    height: c.height,
                    area: c.area
                });
            });

            // 12. 생성 이미지 후보 개별 상세 로그 (요구사항 5번)
            allImgs.forEach((img, idx) => {
                const src = img.currentSrc || img.src || '';
                const isData = src.startsWith('data:image/');
                const isBlob = src.startsWith('blob:');
                const isGoogle = src.includes('googleusercontent.com') || src.includes('gemini');
                const hasValidSrc = isData || isBlob || isGoogle;
                
                const w = img.naturalWidth || img.getBoundingClientRect().width || 0;
                const h = img.naturalHeight || img.getBoundingClientRect().height || 0;
                const hasValidSize = w > 200 && h > 200;

                if (hasValidSrc && hasValidSize) {
                    const rect = img.getBoundingClientRect();
                    console.log('[StoryMaker Gemini V1] generated_candidate', {
                        index: idx,
                        currentSrc: img.currentSrc || '',
                        src: img.src || '',
                        naturalWidth: img.naturalWidth || 0,
                        naturalHeight: img.naturalHeight || 0,
                        complete: img.complete,
                        parentTag: img.parentElement ? img.parentElement.tagName : 'none',
                        parentClass: img.parentElement ? img.parentElement.className : '',
                        isVisible: isVisible(img),
                        rect: { top: rect.top, left: rect.left, width: rect.width, height: rect.height }
                    });
                }
            });

            console.log('[StoryMaker Gemini V1] thumbnail_dom_debug_summary', {
                totalImgs: allImgs.length,
                totalPictures: allPictures.length,
                totalSources: allSources.length,
                totalCanvases: allCanvases.length,
                lastResponseFound: !!lastResponse,
                candidatesCount: candidates.length
            });

        } catch (err) {
            console.error('[StoryMaker Gemini V1] debugDumpGeneratedImageDom 중 에러 발생:', err);
        }

        console.log('[StoryMaker Gemini V1] thumbnail_dom_debug_finish');
    }

    function gmImageUrlToDataUrl(url) {
        return new Promise((resolve) => {
            if (!url || String(url).startsWith('data:image/')) {
                resolve(url || '');
                return;
            }

            try {
                GM_xmlhttpRequest({
                    method: 'GET',
                    url,
                    responseType: 'blob',
                    onload: (res) => {
                        try {
                            if (res.status < 200 || res.status >= 300 || !res.response) {
                                healthLog('thumbnail_gm_download_failed', { status: res.status, url: String(url).slice(0, 120) });
                                resolve('');
                                return;
                            }
                            const blob = res.response;
                            const reader = new FileReader();
                            reader.onload = () => {
                                const value = String(reader.result || '');
                                healthLog('thumbnail_gm_dataurl_done', { length: value.length, type: blob.type || '' });
                                resolve(value.startsWith('data:image/') ? value : '');
                            };
                            reader.onerror = () => resolve('');
                            reader.readAsDataURL(blob);
                        } catch (e) {
                            resolve('');
                        }
                    },
                    onerror: () => resolve(''),
                    ontimeout: () => resolve(''),
                    timeout: 20000
                });
            } catch (e) {
                resolve('');
            }
        });
    }

    async function collectGeneratedImageDataUrls(beforeSnapshot = null) {
        debugDumpGeneratedImageDom();
        const urls = collectGeneratedImageUrls(beforeSnapshot);
        if (urls.length !== 1) return [];
        let dataUrl = await gmImageUrlToDataUrl(urls[0]);
        if (!dataUrl || dataUrl.length <= 1000) {
            dataUrl = await imageUrlToDataUrl(urls[0]);
        }
        return dataUrl && dataUrl.length > 1000 ? [dataUrl] : [];
    }

    function collectGeneratedImageKeys(beforeSnapshot = null) {
        return collectGeneratedImages(beforeSnapshot).map(item => [item.src, item.width, item.height, item.score].join('#'));
    }

    async function waitForGeneratedImagesStable(minCount = 1, stableSeconds = 3, timeoutSeconds = 120, beforeSnapshot = null) {
        console.log('[StoryMaker Gemini V1] 최종 생성 이미지 안정화 대기 시작:', minCount);
        let lastKey = '';
        let stable = 0;

        for (let i = 0; i < timeoutSeconds; i++) {
            await delay(1000);
            const urls = collectGeneratedImageUrls(beforeSnapshot);
            const key = collectGeneratedImageKeys(beforeSnapshot).join('|');
            stable = urls.length >= minCount && key && key === lastKey ? stable + 1 : 0;
            lastKey = key;
            console.log('[StoryMaker Gemini V1] 최종 생성 이미지 감지:', urls.length, 'stable:', stable, '/', stableSeconds);
            if (urls.length >= minCount && stable >= stableSeconds) return urls;
        }
        return collectGeneratedImageUrls(beforeSnapshot);
    }

    async function saveThumbnailUrls(jobId, projectTitle, resultText, beforeSnapshot = null, sourceJobId = '') {
        healthLog('thumbnail_result_save_start', { jobId });
        const imageUrls = collectGeneratedImageUrls(beforeSnapshot);
        if (imageUrls.length !== 1) {
            healthLog('thumbnail_generated_images_missing', { jobId, count: imageUrls.length });
            console.log('[StoryMaker Gemini V1] 최종 생성 이미지 URL 없음');
            return null;
        }
        healthLog('thumbnail_generated_images_found', { count: imageUrls.length });

        const imageDataUrls = await collectGeneratedImageDataUrls(beforeSnapshot);
        if (imageDataUrls.length !== 1) {
            healthLog('thumbnail_dataurl_convert_failed', { jobId, count: imageDataUrls.length });
            console.log('[StoryMaker Gemini V1] 최종 생성 이미지 dataURL 변환 실패');
            return null;
        }
        healthLog('thumbnail_dataurls_collected', { count: imageDataUrls.length });

        try {
            const res = await request('POST', BACKEND_URL + '/v1-api/test/thumbnail-result', {
                job_id: jobId,
                project_title: projectTitle || '새 프로젝트',
                image_urls: imageUrls,
                image_data_urls: imageDataUrls,
                final_image_data_url: imageDataUrls[0],
                selected_image_index: 0,
                selected_image_count: 1,
                source_job_id: sourceJobId || '',
                result_text: resultText || '',
                source: 'gemini-worker-thumbnail-final-only'
            });
            healthLog('thumbnail_result_save_done', { jobId });
            return res;
        } catch (e) {
            healthLog('thumbnail_result_save_failed', { jobId, message: e?.message || String(e) });
            throw e;
        }
    }

    function getChatJobCount() {
        const raw = sessionStorage.getItem(CHAT_JOB_COUNT_KEY) || '0';
        const n = parseInt(raw, 10);
        return Number.isFinite(n) ? n : 0;
    }

    function setChatJobCount(n) {
        sessionStorage.setItem(CHAT_JOB_COUNT_KEY, String(Math.max(0, n || 0)));
    }

    function readJobIdSet(storageKey) {
        try {
            const raw = localStorage.getItem(storageKey) || '[]';
            const values = JSON.parse(raw);
            return new Set(Array.isArray(values) ? values.filter(Boolean) : []);
        } catch (e) {
            return new Set();
        }
    }

    function rememberJobId(storageKey, jobId) {
        if (!jobId) return;
        const values = [...readJobIdSet(storageKey), jobId].slice(-100);
        localStorage.setItem(storageKey, JSON.stringify([...new Set(values)]));
    }

    function hasJobId(storageKey, jobId) {
        return !!jobId && readJobIdSet(storageKey).has(jobId);
    }

    function markJobSent(jobId) {
        rememberJobId(SENT_JOBS_KEY, jobId);
        localStorage.setItem('storymaker_last_gemini_sent_job_id', jobId);
    }

    function markJobHandled(jobId) {
        lastHandledJobId = jobId;
        localStorage.setItem('storymaker_v1_last_gemini_job_id', jobId);
        rememberJobId(HANDLED_JOBS_KEY, jobId);
    }

    function acquireJobLock(jobId) {
        if (!jobId) return false;

        const key = JOB_LOCK_KEY_PREFIX + jobId;
        const now = Date.now();

        try {
            const raw = localStorage.getItem(key);
            if (raw) {
                const data = JSON.parse(raw);
                if (data && data.expiresAt && data.expiresAt > now && data.version === WORKER_VERSION) {
                    healthLog('job_lock_exists', {
                        jobId,
                        owner: data.owner || '',
                        expiresAt: data.expiresAt,
                        version: data.version || ''
                    });
                    return false;
                }
                if (data && data.expiresAt && data.expiresAt > now && data.version !== WORKER_VERSION) {
                    healthLog('job_lock_stale_version_takeover', {
                        jobId,
                        previousOwner: data.owner || '',
                        previousVersion: data.version || '',
                        currentVersion: WORKER_VERSION
                    });
                }
            }

            const lock = {
                owner: workerState.startedAt + '_' + Math.random().toString(36).slice(2),
                version: WORKER_VERSION,
                createdAt: now,
                expiresAt: now + JOB_LOCK_TTL_MS
            };

            localStorage.setItem(key, JSON.stringify(lock));

            const check = JSON.parse(localStorage.getItem(key) || '{}');
            const ok = check.owner === lock.owner;

            healthLog('job_lock_acquire', { jobId, ok });

            return ok;
        } catch (e) {
            healthLog('job_lock_error', { jobId, message: e?.message || String(e) });
            return false;
        }
    }

    function releaseJobLock(jobId) {
        if (!jobId) return;
        try {
            localStorage.removeItem(JOB_LOCK_KEY_PREFIX + jobId);
            healthLog('job_lock_release', { jobId });
        } catch (e) {}
    }

    // eslint-disable-next-line no-unused-vars
    function openFreshGeminiChat(reason) {
        console.log('[StoryMaker Gemini V1] 새 Gemini 대화창으로 이동:', reason || '');
        setChatJobCount(0);

        const freshUrl = 'https://gemini.google.com/app?storymaker_new_chat=' + Date.now();
        window.location.href = freshUrl;
    }

    function isVisible(el) {
        if (!el) return false;

        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();

        return style.display !== 'none'
            && style.visibility !== 'hidden'
            && rect.width > 0
            && rect.height > 0;
    }

    function cleanStoryMakerResult(rawText) {
        let text = String(rawText || '').trim();

        text = text.replace(/^아래는[\s\S]*?\n+/i, '');
        text = text.replace(/^물론입니다[\s\S]*?\n+/i, '');
        text = text.replace(/^네[\s\S]*?\n+/i, '');
        text = text.replace(/^편집\s*/gm, '');
        text = text.replace(/^복사\s*/gm, '');

        text = text.replace(/^```(?:content|text|markdown)?\s*/i, '');
        text = text.replace(/```\s*$/i, '');

        const firstBlock = text.search(/\[BLOCK:[A-Z0-9_]+\]/);

        if (firstBlock > 0) {
            text = text.slice(firstBlock).trim();
        }

        // StoryMaker v3.2부터 플레이스/구글 블록은 정식 결과물입니다.
        // 예전처럼 CAROUSEL_7 이후 블록을 잘라내지 않습니다.
        if (text.includes('[BLOCK:WORDPRESS_SEO]')) {
            const wpIndex = text.indexOf('[BLOCK:WORDPRESS_SEO]');
            if (wpIndex > 0) {
                text = text.slice(0, wpIndex).trim();
            }
        }

        return text.trim();
    }

    function getPromptBox() {
        const candidates = [
            ...queryAllDeep('rich-textarea div[contenteditable="true"]'),
            ...queryAllDeep('div.ql-editor[contenteditable="true"]'),
            ...queryAllDeep('div[aria-label*="프롬프트"]'),
            ...queryAllDeep('div[aria-label*="Enter a prompt"]'),
            ...queryAllDeep('[aria-label*="메시지"]'),
            ...queryAllDeep('[aria-label*="Gemini에게"]'),
            ...queryAllDeep('[data-placeholder*="Gemini"]'),
            ...queryAllDeep('div[contenteditable="true"][role="textbox"]'),
            ...queryAllDeep('div[role="textbox"]'),
            ...queryAllDeep('rich-textarea textarea'),
            ...queryAllDeep('rich-textarea [contenteditable="true"]'),
            ...queryAllDeep('[contenteditable="true"]'),
            ...queryAllDeep('textarea')
        ].filter(Boolean);

        return [...new Set(candidates)].find(isVisible) || null;
    }

    async function waitForPromptBox(timeoutMs = 10000) {
        const started = Date.now();
        while (Date.now() - started < timeoutMs) {
            const box = getPromptBox();
            if (box) return box;
            await delay(500);
        }
        return null;
    }

    function injectText(el, text) {
        if (!el) {
            console.error('[StoryMaker Gemini V1] 입력창 없음');
            return false;
        }

        el.focus();
        el.click?.();

        const value = String(text || '');
        const richTextarea = el.closest?.('rich-textarea') || el;
        const editTarget = el.isContentEditable ? el : (richTextarea.querySelector?.('[contenteditable="true"]') || el);
        editTarget.focus?.();

        try {
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            document.execCommand('insertText', false, value);
        } catch (e) {}

        if (editTarget.tagName === 'TEXTAREA' || editTarget.tagName === 'INPUT') {
            editTarget.value = value;
        }

        for (const target of [editTarget, richTextarea, el, document.body].filter(Boolean)) {
            target.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, cancelable: true, inputType: 'insertText', data: value }));
            target.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: value }));
            target.dispatchEvent(new Event('change', { bubbles: true }));
        }

        console.log('[StoryMaker Gemini V1] 프롬프트 주입 완료');
        return true;
    }

    function isEnabledButton(btn) {
        return btn
            && isVisible(btn)
            && !btn.disabled
            && btn.getAttribute('aria-disabled') !== 'true';
    }

    function getSendButton() {
        const explicitSelectors = [
            'button[aria-label*="Submit"]',
            'button[aria-label*="submit"]',
            'button[aria-label*="send"]',
            'button[aria-label*="Send"]',
            'button[aria-label*="보내기"]',
            'button[aria-label*="전송"]',
            'button[data-testid*="send"]',
            'button[data-testid*="submit"]',
            'button[title*="Submit"]',
            'button[title*="submit"]',
            'button[title*="send"]',
            'button[title*="Send"]',
            'button[title*="보내기"]',
            'button[title*="전송"]'
        ];

        for (const selector of explicitSelectors) {
            const btn = queryAllDeep(selector).find(isEnabledButton);
            if (btn) return btn;
        }

        const iconButton = queryAllDeep('button mat-icon, mat-icon')
            .map(icon => {
                const text = (icon.textContent || '').trim();
                return (text === 'send' || text === 'arrow_upward') ? icon.closest('button') : null;
            })
            .find(isEnabledButton);
        if (iconButton) return iconButton;

        const promptBox = getPromptBox();
        const promptScope = promptBox?.closest('form, rich-textarea, [role="form"], [class*="input"], [class*="prompt"]');
        if (promptScope) {
            const scopedButton = [...promptScope.querySelectorAll('button')].reverse().find(isEnabledButton);
            if (scopedButton) return scopedButton;
        }

        return queryAllDeep('button')
            .filter(isEnabledButton)
            .find(btn => btn.querySelector('svg')) || null;
    }

    async function waitForSendButton(timeoutMs = 10000) {
        const started = Date.now();
        while (Date.now() - started < timeoutMs) {
            const btn = getSendButton();
            if (isEnabledButton(btn)) return btn;
            await delay(400);
        }
        return null;
    }

    function logVisibleButtons() {
        const buttons = queryAllDeep('button').map((btn, idx) => ({
            idx,
            aria: btn.getAttribute('aria-label') || '',
            title: btn.getAttribute('title') || '',
            text: (btn.innerText || '').trim().slice(0, 80),
            disabled: btn.disabled,
            ariaDisabled: btn.getAttribute('aria-disabled') || '',
            visible: isVisible(btn),
            className: String(btn.className || '')
        }));
        console.log('[StoryMaker Gemini V1] visible buttons:', buttons);
    }

    function dispatchSendKey(el, init) {
        const event = new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            bubbles: true,
            cancelable: true,
            ...init
        });
        return el.dispatchEvent(event);
    }

    async function fallbackSendByKeyboard() {
        const box = getPromptBox() || document.activeElement || document.body;
        box.focus?.();
        const attempts = [
            {},
            { ctrlKey: true },
            { metaKey: true }
        ];

        for (const init of attempts) {
            dispatchSendKey(box, init);
            await delay(500);
        }

        console.warn('[StoryMaker Gemini V1] 전송 버튼 fallback 키보드 이벤트 시도 완료');
        return true;
    }

    async function clickSendButton() {
        const btn = await waitForSendButton(10000);

        if (!btn) {
            logVisibleButtons();
            console.error('[StoryMaker Gemini V1] 전송 버튼 없음');
            return fallbackSendByKeyboard();
        }

        const beforeBox = getPromptBox();
        const beforeText = String(beforeBox?.innerText || beforeBox?.textContent || beforeBox?.value || '').trim();
        btn.click();
        await delay(900);

        let afterBox = getPromptBox();
        let afterText = String(afterBox?.innerText || afterBox?.textContent || afterBox?.value || '').trim();
        if (beforeText && afterText) {
            healthLog('send_button_click_not_consumed', {
                beforeLength: beforeText.length,
                afterLength: afterText.length,
                tag: afterBox?.tagName || '',
                className: String(afterBox?.className || '').slice(0, 120)
            });
            await fallbackSendByKeyboard();
            await delay(900);
            afterBox = getPromptBox();
            afterText = String(afterBox?.innerText || afterBox?.textContent || afterBox?.value || '').trim();
        }

        const sent = !beforeText || !afterText;
        healthLog(sent ? 'send_verified' : 'send_verification_failed', {
            beforeLength: beforeText.length,
            afterLength: afterText.length
        });
        console.log('[StoryMaker Gemini V1] 전송 버튼 클릭 완료');
        return sent;
    }

    function textHash(text) {
        const value = String(text || '');
        let hash = 2166136261;
        for (let i = 0; i < value.length; i++) {
            hash ^= value.charCodeAt(i);
            hash = Math.imul(hash, 16777619);
        }
        return (hash >>> 0).toString(16);
    }

    function assistantText(node) {
        return String(node?.innerText || node?.textContent || '').trim();
    }

    function collectAssistantResponseNodes() {
        const raw = [
            ...document.querySelectorAll('message-content'),
            ...document.querySelectorAll('.model-response-text'),
            ...document.querySelectorAll('div.response-container-content'),
            ...document.querySelectorAll('[class*="model-response"]'),
            ...document.querySelectorAll('[class*="response-container"]')
        ].filter(isVisible);
        const unique = [];
        const seen = new Set();
        for (const node of raw) {
            if (!node || seen.has(node)) continue;
            const text = assistantText(node);
            if (!text) continue;
            seen.add(node);
            unique.push(node);
        }
        const deepest = unique.filter((node) => !unique.some((other) => other !== node && node.contains(other)));
        deepest.sort((a, b) => {
            if (a === b) return 0;
            return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
        });
        return deepest;
    }

    function snapshotAssistantResponses() {
        return collectAssistantResponseNodes().map((node, index) => {
            const text = assistantText(node);
            return { node, index, length: text.length, hash: textHash(text), text };
        });
    }

    function getLastAssistantText() {
        const candidates = collectAssistantResponseNodes();
        if (candidates.length) {
            return assistantText(candidates[candidates.length - 1]);
        }
        const bodyText = document.body.innerText || '';
        const firstBlock = bodyText.lastIndexOf('[BLOCK:');
        return firstBlock >= 0 ? bodyText.slice(firstBlock).trim() : '';
    }

    function findCurrentJobResponse(baselineSnapshot) {
        const baseline = Array.isArray(baselineSnapshot) ? baselineSnapshot : [];
        const candidates = snapshotAssistantResponses();
        for (let i = candidates.length - 1; i >= 0; i--) {
            const current = candidates[i];
            const previous = baseline.find((item) => item.node === current.node);
            if (!previous) {
                return { ...current, reason: 'new_node' };
            }
            if (previous.hash !== current.hash && current.length > previous.length) {
                return { ...current, previousLength: previous.length, reason: 'changed_node' };
            }
        }
        return null;
    }

    async function waitForAnswerComplete(baselineSnapshot = []) {
        console.log('[StoryMaker Gemini 1.4.29] 현재 작업 응답 완료 감지 시작');

        let selectedNode = null;
        let selectedReason = '';
        let lastText = '';
        let stableCount = 0;

        for (let i = 0; i < 120; i++) {
            await delay(1000);

            const candidate = selectedNode
                ? (() => {
                    const text = assistantText(selectedNode);
                    return text ? { node: selectedNode, text, length: text.length, hash: textHash(text), reason: selectedReason } : null;
                })()
                : findCurrentJobResponse(baselineSnapshot);

            if (!candidate) {
                console.log('[StoryMaker Gemini 1.4.29] 현재 작업 새 응답 노드 대기 중');
                continue;
            }

            if (!selectedNode) {
                selectedNode = candidate.node;
                selectedReason = candidate.reason;
                healthLog('current_assistant_response_selected', {
                    reason: selectedReason,
                    responseLength: candidate.length,
                    responseHash: candidate.hash
                });
            }

            const text = candidate.text;
            const len = text.length;
            console.log('[StoryMaker Gemini 1.4.29] current answer length:', len, 'stable:', stableCount, 'reason:', selectedReason);

            if (len > 100 && text === lastText) {
                stableCount++;
            } else {
                stableCount = 0;
            }
            lastText = text;

            if (stableCount >= 3 && text.includes('[BLOCK:PODCAST_80]')) {
                console.log('[StoryMaker Gemini 1.4.29] 현재 작업 응답 완료 (PODCAST_80 감지)');
                return text;
            }

            if (stableCount >= 6) {
                console.log('[StoryMaker Gemini 1.4.29] 현재 작업 응답 완료 (선택 노드 안정화)');
                return text;
            }
        }

        throw new Error('현재 작업의 새 Gemini 응답을 확인하지 못했습니다. 과거 응답 저장을 차단했습니다.');
    }

    async function claimJob(jobId, status = 'claimed', error = '') {
        try {
            const res = await request('POST', BACKEND_URL + '/v1-api/test/trigger-ack', {
                job_id: jobId,
                status,
                worker_id: 'tampermonkey-gemini-worker-' + WORKER_VERSION,
                error: error || null
            });
            if (!res?.ok) {
                console.warn('[StoryMaker Gemini V1] ack 거부:', res?.message || '');
                return false;
            }
            return true;
        } catch (e) {
            console.warn('[StoryMaker Gemini V1] ack 실패, 계속 진행:', e);
            return false;
        }
    }

    async function reportErrorToBackend(jobId, projectTitle, errMsg) {
        try {
            await request('POST', BACKEND_URL + '/v1-api/test/result-package', {
                job_id: jobId,
                project_title: projectTitle || '새 프로젝트',
                source: 'tampermonkey-gemini-worker-error',
                result_text: "[ERROR] " + errMsg,
                result_raw: "[ERROR] " + errMsg,
                result_clean: "[ERROR] " + errMsg,
                result_json: { error: errMsg }
            });
            console.log('[StoryMaker Gemini V1] 에러 보고 완료:', errMsg);
        } catch (e) {
            console.error('[StoryMaker Gemini V1] 에러 보고 실패:', e);
        }
    }

    async function runJob(status) {
        const jobId =
            status?.data?.job_id ||
            status?.job_id ||
            '';

        const projectTitle =
            status?.data?.project_title ||
            status?.project_title ||
            '새 프로젝트';

        const jobStatus =
            status?.data?.status ||
            status?.status ||
            '';

        const action =
            status?.data?.action ||
            status?.action ||
            '';

        if (!jobId) return;

        const isMobileThumbnailPendingJob = action === 'GENERATE_GEMINI_THUMBNAIL' && String(jobId || '').endsWith('_mobile') && jobStatus === 'pending';
        if (jobId === lastHandledJobId && !isMobileThumbnailPendingJob) return;
        if (processingJobs.has(jobId)) return;
        if (hasJobId(SENT_JOBS_KEY, jobId) && !isMobileThumbnailPendingJob) return;
        if (hasJobId(HANDLED_JOBS_KEY, jobId) && !isMobileThumbnailPendingJob) return;

        if (jobId.startsWith('storymaker_e2e_')) return;

        if (jobStatus !== 'pending') return;
        if (!['GENERATE_GEMINI', 'GENERATE_GEMINI_THUMBNAIL'].includes(action)) return;

        console.log('[StoryMaker Gemini V1] 새 pending job 감지:', jobId);
        if (!acquireJobLock(jobId)) return;
        processingJobs.add(jobId);

        let isResetting = false;
        let promptSentConfirmed = false;
        let imageSnapshotBeforePrompt = null;
        try {
            if (action === 'GENERATE_GEMINI_THUMBNAIL') {
                const resetJobId = localStorage.getItem(THUMBNAIL_RESET_JOB_KEY);
                if (resetJobId !== jobId) {
                    isResetting = true;
                    localStorage.setItem(THUMBNAIL_RESET_JOB_KEY, jobId);
                    healthLog('thumbnail_reset_before_upload', { jobId });
                    releaseJobLock(jobId);
                    healthLog('gemini_reset_after_thumbnail_job_created', { jobId });
                    openFreshGeminiChat('thumbnail requires fresh chat');
                    return;
                }
                healthLog('thumbnail_reset_confirmed_continue', { jobId });
            }

            const promptUrl = (String(jobId || '').startsWith('mob-') || String(jobId || '').endsWith('_mobile'))
                ? BACKEND_URL + '/v1-api/test/job-prompt/' + encodeURIComponent(jobId)
                : BACKEND_URL + '/v1-api/test/latest-prompt';
            const latest = await request('GET', promptUrl);

            let prompt =
                latest?.prompt ||
                latest?.data?.prompt ||
                '';

            if (!prompt) {
                throw new Error('prompt 비어 있음');
            }

            if (action === 'GENERATE_GEMINI_THUMBNAIL') {
                prompt = cleanThumbnailPrompt(prompt);

                const hasInstagramPost = prompt.includes('[인스타그램 게시글 참고 문안]');
                let postText = '';
                if (hasInstagramPost) {
                    const postSection = prompt.split('[인스타그램 게시글 참고 문안]')[1] || '';
                    postText = (postSection.split('[디자인 지시]')[0] || '').trim();
                }
                const isPostFound = hasInstagramPost && postText.length > 10;

                const bizLine = (prompt.match(/상호:\s*(.*)/) || [])[1] || '';
                const isBizFound = bizLine.trim().length > 0;

                const phoneLine = (prompt.match(/전화번호:\s*(.*)/) || [])[1] || '';
                const isPhoneFound = phoneLine.trim().length > 0;

                const keywordsLine = (prompt.match(/키워드:\s*(.*)/) || [])[1] || '';
                const isKeywordsFound = keywordsLine.trim().length > 0;

                if (!isPostFound) {
                    healthLog('thumbnail_prompt_instagram_post_missing');
                } else {
                    healthLog('thumbnail_prompt_instagram_post_found');
                }

                if (!isBizFound) {
                    healthLog('thumbnail_prompt_business_info_missing');
                } else {
                    healthLog('thumbnail_prompt_business_info_found');
                }

                if (!isPhoneFound) {
                    healthLog('thumbnail_prompt_phone_missing');
                } else {
                    healthLog('thumbnail_prompt_phone_found');
                }

                if (!isKeywordsFound) {
                    healthLog('thumbnail_prompt_keywords_missing');
                } else {
                    healthLog('thumbnail_prompt_keywords_found');
                }

                healthLog('thumbnail_prompt_final_length', { length: prompt.length });

                if (!prompt || prompt.length < 100) {
                    healthLog('thumbnail_prompt_too_short', { length: prompt ? prompt.length : 0, prompt });
                    throw new Error('썸네일 프롬프트가 너무 짧습니다 (100자 미만).');
                }
            }

            if (action === 'GENERATE_GEMINI') {
                // prompt_builder.py에서 생성한 통합 프롬프트를 그대로 사용합니다.
                // Worker에서는 블록 목록을 추가하거나 제외하지 않습니다.
            }

            if (!(await claimJob(jobId, 'claimed'))) {
                return;
            }

            if (action === 'GENERATE_GEMINI_THUMBNAIL') {
                const imageUrls = status?.data?.image_urls || status?.image_urls || [];
                try {
                    healthLog('thumbnail_upload_start', { count: imageUrls.length });
                    const uploadOk = await uploadImagesToGemini(imageUrls);

                    healthLog('thumbnail_upload_result', {
                        ok: uploadOk,
                        count: imageUrls.length
                    });

                    console.log(workerTag(), '썸네일 이미지 첨부 결과:', uploadOk);

                    if (!uploadOk) {
                        throw new Error('Gemini 이미지 3장 Preview 확인 실패 - 프롬프트 입력 중단');
                    }
                    if (!(await claimJob(jobId, 'uploaded'))) {
                        throw new Error('썸네일 업로드 상태 기록에 실패했습니다.');
                    }
                    imageSnapshotBeforePrompt = snapshotExistingGeminiImages();
                    healthLog('thumbnail_image_snapshot_before_prompt', { count: imageSnapshotBeforePrompt.size });
                } catch (uploadErr) {
                    healthLog('thumbnail_upload_failed', {
                        message: uploadErr?.message || String(uploadErr)
                    });
                    console.warn(workerTag(), '썸네일 이미지 첨부 실패:', uploadErr);
                    throw uploadErr;
                }
            }

            // 3. 현재 이미지 preview가 포함된 composer/root 영역을 찾음
            let box = null;
            if (action === 'GENERATE_GEMINI_THUMBNAIL') {
                const previews = collectUploadPreviewElements();
                let composer = null;
                for (const preview of previews) {
                    let parent = preview.parentElement;
                    while (parent && parent !== document.body) {
                        const input = parent.querySelector('div[contenteditable="true"], rich-textarea, textarea');
                        if (input) {
                            composer = parent;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                    if (composer) break;
                }

                if (composer) {
                    // 4. 그 영역 안에서 contenteditable 또는 textarea 입력창을 찾음
                    box = composer.querySelector('div[contenteditable="true"], rich-textarea [contenteditable="true"], textarea');
                    if (box) {
                        healthLog('prompt_box_in_attachment_composer_found', {
                            tag: box.tagName,
                            className: box.className
                        });
                        box.focus();
                        await delay(1000);
                    }
                }
            }

            if (!box) {
                box = await waitForPromptBox();
            }

            if (!box) {
                console.error('[StoryMaker Gemini V1] 입력창 없음 - job claim 없이 중단');
                openFreshGeminiChat('prompt box not found');
                return;
            }

            if (action === 'GENERATE_GEMINI_THUMBNAIL') {
                healthLog('thumbnail_prompt_preview', {
                    length: prompt.length,
                    head: prompt.slice(0, 100),
                    tail: prompt.slice(-100)
                });
            }

            healthLog('prompt_inject_after_upload_ready');

            if (!injectText(box, prompt)) {
                throw new Error('프롬프트 주입에 실패했습니다.');
            }
            await delay(350);
            let injectedText = String(box?.innerText || box?.textContent || box?.value || '').trim();
            if (injectedText.length < Math.min(40, String(prompt || '').trim().length)) {
                healthLog('prompt_injection_not_persisted_retry', {
                    expectedLength: String(prompt || '').length,
                    actualLength: injectedText.length,
                    tag: box?.tagName || '',
                    className: String(box?.className || '').slice(0, 120)
                });
                const retryBox = await waitForPromptBox(5000);
                if (!retryBox || !injectText(retryBox, prompt)) {
                    throw new Error('프롬프트가 Gemini 입력창에 유지되지 않았습니다.');
                }
                box = retryBox;
                await delay(350);
                injectedText = String(box?.innerText || box?.textContent || box?.value || '').trim();
            }
            if (!injectedText) {
                throw new Error('프롬프트 입력 확인에 실패했습니다.');
            }
            healthLog('prompt_injection_verified', { length: injectedText.length });

            await delay(1000);

            healthLog('send_after_upload_and_prompt');

            const previousAssistantSnapshot = snapshotAssistantResponses();
            healthLog('assistant_baseline_captured', {
                jobId,
                count: previousAssistantSnapshot.length,
                hashes: previousAssistantSnapshot.map((item) => item.hash).slice(-8)
            });

            if (!(await clickSendButton())) {
                throw new Error('전송 버튼 클릭에 실패했습니다.');
            }

            if (action === 'GENERATE_GEMINI_THUMBNAIL') {
                await delay(900);
                let remainingText = String(box?.innerText || box?.textContent || box?.value || '').trim();
                if (remainingText.length > 20) {
                    healthLog('thumbnail_send_not_confirmed_keyboard_retry', {
                        jobId,
                        remainingLength: remainingText.length
                    });
                    box.focus();
                    await fallbackSendByKeyboard();
                    await delay(1200);
                    remainingText = String(box?.innerText || box?.textContent || box?.value || '').trim();
                }
                if (remainingText.length > 20) {
                    healthLog('thumbnail_prompt_send_unconfirmed', {
                        jobId,
                        remainingLength: remainingText.length
                    });
                    throw new Error('PC Gemini에서 썸네일 프롬프트 전송이 확인되지 않았습니다.');
                }
                if (!(await claimJob(jobId, 'prompt_sent'))) {
                    throw new Error('썸네일 프롬프트 전송 상태 기록에 실패했습니다.');
                }
                promptSentConfirmed = true;
                healthLog('thumbnail_prompt_send_confirmed', { jobId });
            } else {
                await claimJob(jobId, 'sent');
            }
            markJobSent(jobId);

            let rawResultText = '';
            if (action === 'GENERATE_GEMINI_THUMBNAIL') {
                const finalUrls = await waitForGeneratedImagesStable(1, 3, 120, imageSnapshotBeforePrompt);
                if (finalUrls.length !== 1) {
                    throw new Error('Gemini 최종 생성 이미지를 확인하지 못했습니다. 원본 업로드 이미지는 저장하지 않습니다.');
                }
                rawResultText = getLastAssistantText();
            } else {
                rawResultText = await waitForAnswerComplete(previousAssistantSnapshot);
            }
            console.log('[StoryMaker Gemini V1] rawResultText.length:', rawResultText.length);

            const resultText = cleanStoryMakerResult(rawResultText);
            console.log('[StoryMaker Gemini V1] resultText.length:', resultText.length);

            if (!resultText && action !== 'GENERATE_GEMINI_THUMBNAIL') {
                throw new Error('수집된 결과 텍스트가 비어 있습니다.');
            }

            console.log('[StoryMaker Gemini V1] result-package POST 요청 중...');
            const saveRes = action === 'GENERATE_GEMINI_THUMBNAIL'
                ? { ok: true, skipped: 'thumbnail-result-only' }
                : await request('POST', BACKEND_URL + '/v1-api/test/result-package', {
                job_id: jobId,
                project_title: projectTitle,
                source: 'tampermonkey-gemini-worker-1.3.9',
                result_text: resultText,
                result_raw: rawResultText,
                result_clean: resultText,
                result_json: {}
            });

            console.log('[StoryMaker Gemini V1] result-package 저장 완료:', saveRes);
            if (action === 'GENERATE_GEMINI_THUMBNAIL') {
                const thumbnailSaveRes = await saveThumbnailUrls(
                    jobId,
                    projectTitle,
                    rawResultText,
                    imageSnapshotBeforePrompt,
                    status?.data?.source_job_id || status?.source_job_id || ''
                );
                if (!thumbnailSaveRes) {
                    throw new Error('Gemini 최종 생성 이미지를 확인하지 못했습니다. 원본 업로드 이미지는 저장하지 않습니다.');
                }
            }

            markJobHandled(jobId);

            const nextCount = getChatJobCount() + 1;
            setChatJobCount(nextCount);
            console.log('[StoryMaker Gemini V1] 현재 Gemini 대화창 처리 횟수:', nextCount, '/', MAX_JOBS_PER_CHAT);

            if (nextCount >= MAX_JOBS_PER_CHAT) {
                await delay(1200);
                openFreshGeminiChat('max jobs per chat reached after save');
            }
        } catch (err) {
            const errMsg = err.message || String(err);
            console.error('[StoryMaker Gemini V1] runJob 중 오류 발생:', errMsg);
            if (action === 'GENERATE_GEMINI_THUMBNAIL' && !promptSentConfirmed) {
                const retryQueued = await claimJob(jobId, 'retry_pending', errMsg);
                healthLog('thumbnail_prompt_retry_queued', {
                    jobId,
                    ok: retryQueued,
                    error: errMsg
                });
                if (!retryQueued) {
                    await reportErrorToBackend(jobId, projectTitle, errMsg);
                }
            } else {
                await reportErrorToBackend(jobId, projectTitle, errMsg);
            }
        } finally {
            if (action === 'GENERATE_GEMINI_THUMBNAIL' && !isResetting) {
                localStorage.removeItem(THUMBNAIL_RESET_JOB_KEY);
            }
            releaseJobLock(jobId);
            processingJobs.delete(jobId);
        }
    }

    async function workerLoop() {
        if (workerState.stopped || window[SINGLETON_KEY] !== workerState) return;
        if (!tryAcquirePollLeadership()) return;
        if (running) return;

        try {
            running = true;

            const status = await request('GET', BACKEND_URL + '/v1-api/test/trigger-status');

            const jobId =
                status?.data?.job_id ||
                status?.job_id ||
                '';

            const jobStatus =
                status?.data?.status ||
                status?.status ||
                '';

            const action =
                status?.data?.action ||
                status?.action ||
                '';

            if (!jobId) return;

            const isMobileThumbnailPendingJob = action === 'GENERATE_GEMINI_THUMBNAIL' && String(jobId || '').endsWith('_mobile') && jobStatus === 'pending';
            if (jobId === lastHandledJobId && !isMobileThumbnailPendingJob) return;
            if (processingJobs.has(jobId)) return;
            if (hasJobId(SENT_JOBS_KEY, jobId) && !isMobileThumbnailPendingJob) return;
            if (hasJobId(HANDLED_JOBS_KEY, jobId) && !isMobileThumbnailPendingJob) return;

            // 버튼 클릭으로 생성된 신규 pending job만 실행한다.
            if (jobStatus !== 'pending') return;

            // Gemini 전용 워커이므로 ChatGPT action은 실행하지 않는다.
            if (!['GENERATE_GEMINI', 'GENERATE_GEMINI_THUMBNAIL'].includes(action)) return;

            // 한 대화창에 결과가 5회 이상 쌓였으면,
            // 이번 job은 claim하지 않고 새 Gemini 대화창으로 먼저 이동한다.
            if (getChatJobCount() >= MAX_JOBS_PER_CHAT) {
                openFreshGeminiChat('max jobs per chat reached before next job');
                return;
            }

            await runJob(status);

        } catch (err) {
            console.error('[StoryMaker Gemini V1] loop 실패:', err);
        } finally {
            running = false;
        }
    }

    workerState.timerId = setInterval(workerLoop, POLL_MS);

    setTimeout(workerLoop, 1500);
})();

