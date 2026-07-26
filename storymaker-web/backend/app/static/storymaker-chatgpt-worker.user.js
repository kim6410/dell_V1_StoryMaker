// ==UserScript==
// @name         StoryMaker Gemini Worker 1.3.1 Retired
// @namespace    http://tampermonkey.net/
// @version      1.3.1-retired
// @match        https://gemini.google.com/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// ==/UserScript==

(function () {
    'use strict';

    console.warn('[StoryMaker Gemini 1.3.1] retired worker disabled. Install the current storymaker-gemini-worker.user.js.');
    return;

    const BACKEND_URL = 'http://localhost:8090';
    const POLL_MS = 2000;
    const WORKER_VERSION = '1.3.1';
    const SINGLETON_KEY = '__STORYMAKER_GEMINI_WORKER_SINGLETON__';
    const SENT_JOBS_KEY = 'storymaker_gemini_sent_job_ids';
    const HANDLED_JOBS_KEY = 'storymaker_gemini_handled_job_ids';

    // Gemini 한 대화창에 결과가 너무 많이 쌓이면 느려지므로,
    // 지정 횟수 이상 처리 후 새 대화창으로 이동한다.
    const MAX_JOBS_PER_CHAT = 5;
    const CHAT_JOB_COUNT_KEY = 'storymaker_gemini_jobs_in_current_chat';

    const previousWorker = window[SINGLETON_KEY];
    if (previousWorker?.timerId) {
        clearInterval(previousWorker.timerId);
        previousWorker.stopped = true;
        console.warn('[StoryMaker Gemini 1.3.1] 이전 worker interval 정리');
    }

    const workerState = {
        version: WORKER_VERSION,
        startedAt: Date.now(),
        timerId: null,
        stopped: false
    };
    window[SINGLETON_KEY] = workerState;

    let running = false;
    const processingJobs = new Set();
    let lastHandledJobId = localStorage.getItem('storymaker_last_gemini_job_id') || '';

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
            url: BACKEND_URL + '/api/test/worker-log',
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify({ message: `[${type.toUpperCase()}] ${msg}` }),
            onload: () => {},
            onerror: () => {}
        });
    }

    console.log = (...args) => logToServer('log', args);
    console.error = (...args) => logToServer('error', args);
    console.warn = (...args) => logToServer('warn', args);

    console.log('[StoryMaker Gemini 1.3.1] polling worker start');

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
                    try {
                        resolve(JSON.parse(res.responseText || '{}'));
                    } catch (e) {
                        reject(e);
                    }
                },
                onerror: reject
            });
        });
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
        localStorage.setItem('storymaker_last_gemini_job_id', jobId);
        rememberJobId(HANDLED_JOBS_KEY, jobId);
    }

    // eslint-disable-next-line no-unused-vars
    function openFreshGeminiChat(reason) {
        console.log('[StoryMaker Gemini 1.3.1] 새 Gemini 대화창으로 이동:', reason || '');
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

        const allowedLast = '[BLOCK:CAROUSEL_7]';
        const lastStart = text.indexOf(allowedLast);

        if (lastStart >= 0) {
            const bannedBlocks = [
                '[BLOCK:NAVER_PLACE_NEWS]',
                '[BLOCK:GOOGLE_BUSINESS_POST]',
                '[BLOCK:WORDPRESS_SEO]'
            ];

            let cutAt = -1;

            for (const b of bannedBlocks) {
                const idx = text.indexOf(b);
                if (idx > 0 && (cutAt === -1 || idx < cutAt)) {
                    cutAt = idx;
                }
            }

            if (cutAt > 0) {
                text = text.slice(0, cutAt).trim();
            }
        }

        return text.trim();
    }

    function getPromptBox() {
        const candidates = [
            document.querySelector('rich-textarea div[contenteditable="true"]'),
            document.querySelector('div.ql-editor[contenteditable="true"]'),
            document.querySelector('div[aria-label*="프롬프트"]'),
            document.querySelector('div[aria-label*="Enter a prompt"]'),
            document.querySelector('[aria-label*="메시지"]'),
            document.querySelector('[aria-label*="Gemini에게"]'),
            document.querySelector('[data-placeholder*="Gemini"]'),
            document.querySelector('div[contenteditable="true"][role="textbox"]'),
            document.querySelector('div[role="textbox"]'),
            document.querySelector('rich-textarea textarea'),
            document.querySelector('rich-textarea [contenteditable="true"]'),
            ...document.querySelectorAll('[contenteditable="true"]'),
            ...document.querySelectorAll('textarea')
        ].filter(Boolean);

        return candidates.find(isVisible) || null;
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
            console.error('[StoryMaker Gemini 1.3.1] 입력창 없음');
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

        console.log('[StoryMaker Gemini 1.3.1] 프롬프트 주입 완료');
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
            const btn = [...document.querySelectorAll(selector)].find(isEnabledButton);
            if (btn) return btn;
        }

        const iconButton = [...document.querySelectorAll('button mat-icon, mat-icon')]
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

        const svgButtons = [...document.querySelectorAll('button')]
            .filter(isEnabledButton)
            .filter(btn => btn.querySelector('svg'));
        const promptRect = getPromptBox()?.getBoundingClientRect?.();
        const candidates = svgButtons
            .map(btn => ({ btn, rect: btn.getBoundingClientRect() }))
            .filter(item => !promptRect || item.rect.left > promptRect.left + promptRect.width * 0.55)
            .filter(item => item.rect.top > window.innerHeight * 0.45)
            .sort((a, b) => (b.rect.right + b.rect.bottom) - (a.rect.right + a.rect.bottom));
        return candidates[0]?.btn || svgButtons[svgButtons.length - 1] || null;
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
        const buttons = [...document.querySelectorAll('button')].map((btn, idx) => ({
            idx,
            aria: btn.getAttribute('aria-label') || '',
            title: btn.getAttribute('title') || '',
            text: (btn.innerText || '').trim().slice(0, 80),
            disabled: btn.disabled,
            ariaDisabled: btn.getAttribute('aria-disabled') || '',
            visible: isVisible(btn),
            className: String(btn.className || '')
        }));
        console.log('[StoryMaker Gemini 1.3.1] visible buttons:', buttons);
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

        console.warn('[StoryMaker Gemini 1.3.1] 전송 버튼 fallback 키보드 이벤트 시도 완료');
        return true;
    }

    async function clickSendButton() {
        const btn = await waitForSendButton(10000);

        if (!btn) {
            logVisibleButtons();
            console.error('[StoryMaker Gemini 1.3.1] 전송 버튼 없음');
            return fallbackSendByKeyboard();
        }

        btn.click();
        await delay(1800);
        const box = getPromptBox();
        const remainingText = String((box && (box.innerText || box.value || box.textContent)) || '').trim();
        if (remainingText.length > 20) {
            console.warn('[StoryMaker Gemini 1.3.1] prompt still remains after click, delayed Enter fallback');
            await fallbackSendByKeyboard();
        }

        console.log('[StoryMaker Gemini 1.3.1] 전송 버튼 클릭 완료');
        return true;
    }

    function getLastAssistantText() {
        const candidates = [
            ...document.querySelectorAll('message-content'),
            ...document.querySelectorAll('.model-response-text'),
            ...document.querySelectorAll('[class*="model-response"]'),
            ...document.querySelectorAll('[class*="response-container"]')
        ].filter(isVisible);

        if (!candidates.length) {
            const bodyText = document.body.innerText || '';
            const firstBlock = bodyText.lastIndexOf('[BLOCK:');
            return firstBlock >= 0 ? bodyText.slice(firstBlock).trim() : '';
        }

        // 가장 긴 텍스트를 담은 요소를 우선해서 찾습니다.
        candidates.sort((a, b) => (b.innerText || '').length - (a.innerText || '').length);
        return (candidates[0].innerText || '').trim();
    }

    async function waitForAnswerComplete() {
        console.log('[StoryMaker Gemini 1.3.1] 응답 완료 감지 시작');

        let lastText = '';
        let stableCount = 0;
        let bestText = '';
        let zeroCountAfterText = 0;

        for (let i = 0; i < 90; i++) {
            await delay(1000);

            const text = getLastAssistantText();
            const len = text.length;

            if (len > bestText.length) {
                bestText = text;
            }

            console.log('[StoryMaker Gemini 1.3.1] answer length:', len, 'stable:', stableCount, 'best:', bestText.length);

            if (bestText.length > 100 && len === 0) {
                zeroCountAfterText++;
            } else {
                zeroCountAfterText = 0;
            }

            // 0자 상태가 4회 연속 관측되면 타임아웃 대신 이전에 구한 최적의 텍스트 반환
            if (zeroCountAfterText >= 4) {
                console.log('[StoryMaker Gemini 1.3.1] 응답 완료 감지 완료 (텍스트 소실 감지, 최적 텍스트 반환)');
                return bestText;
            }

            if (len > 100 && text === lastText) {
                stableCount++;
            } else {
                stableCount = 0;
            }

            lastText = text;

            if (stableCount >= 3 && text.includes('[BLOCK:CAROUSEL_7]')) {
                console.log('[StoryMaker Gemini 1.3.1] 응답 완료 감지 완료 (CAROUSEL_7 감지)');
                return text;
            }

            if (stableCount >= 6) {
                console.log('[StoryMaker Gemini 1.3.1] 응답 완료 감지 완료 (6초 텍스트 정지 감지)');
                return text;
            }
        }

        if (bestText.length > 100) {
            console.log('[StoryMaker Gemini 1.3.1] 응답 완료 감지 완료 (최대 대기 초과, 최적 텍스트 반환)');
            return bestText;
        }

        throw new Error('응답 완료 대기 timeout');
    }

    async function claimJob(jobId, status = 'claimed') {
        try {
            const res = await request('POST', BACKEND_URL + '/api/test/trigger-ack', {
                job_id: jobId,
                status,
                worker_id: 'tampermonkey-gemini-worker-1.3.1'
            });
            if (!res?.ok) {
                console.warn('[StoryMaker Gemini 1.3.1] ack 거부:', res?.message || '');
                return false;
            }
            return true;
        } catch (e) {
            console.warn('[StoryMaker Gemini 1.3.1] ack 실패, 계속 진행:', e);
            return false;
        }
    }

    async function reportErrorToBackend(jobId, projectTitle, errMsg) {
        try {
            await request('POST', BACKEND_URL + '/api/test/result-package', {
                job_id: jobId,
                project_title: projectTitle || '새 프로젝트',
                source: 'tampermonkey-gemini-worker-error',
                result_text: "[ERROR] " + errMsg,
                result_raw: "[ERROR] " + errMsg,
                result_clean: "[ERROR] " + errMsg,
                result_json: { error: errMsg }
            });
            console.log('[StoryMaker Gemini 1.3.1] 에러 보고 완료:', errMsg);
        } catch (e) {
            console.error('[StoryMaker Gemini 1.3.1] 에러 보고 실패:', e);
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

        if (jobId === lastHandledJobId) return;
        if (processingJobs.has(jobId)) return;
        if (hasJobId(SENT_JOBS_KEY, jobId)) return;
        if (hasJobId(HANDLED_JOBS_KEY, jobId)) return;

        if (jobId.startsWith('storymaker_e2e_')) return;

        if (jobStatus !== 'pending') return;
        if (action !== 'GENERATE_GEMINI') return;

        console.log('[StoryMaker Gemini 1.3.1] 새 pending job 감지:', jobId);
        processingJobs.add(jobId);

        try {
            const latest = await request('GET', BACKEND_URL + '/api/test/latest-prompt');

            let prompt =
                latest?.prompt ||
                latest?.data?.prompt ||
                '';

            if (!prompt) {
                throw new Error('prompt 비어 있음');
            }

            // prompt_builder.py에서 생성한 통합 프롬프트를 그대로 사용합니다.
            // Worker에서는 블록 목록을 추가하거나 제외하지 않습니다.

            const box = await waitForPromptBox();
            if (!box) {
                console.error('[StoryMaker Gemini 1.3.1] 입력창 없음 - job claim 없이 중단');
                openFreshGeminiChat('prompt box not found');
                return;
            }

            if (!(await claimJob(jobId))) {
                return;
            }

            if (!injectText(box, prompt)) {
                throw new Error('프롬프트 주입에 실패했습니다.');
            }

            if (!(await clickSendButton())) {
                throw new Error('전송 버튼 클릭에 실패했습니다.');
            }
            markJobSent(jobId);
            await claimJob(jobId, 'sent');

            const rawResultText = await waitForAnswerComplete();
            console.log('[StoryMaker Gemini 1.3.1] rawResultText.length:', rawResultText.length);

            const resultText = cleanStoryMakerResult(rawResultText);
            console.log('[StoryMaker Gemini 1.3.1] resultText.length:', resultText.length);

            if (!resultText) {
                throw new Error('수집된 결과 텍스트가 비어 있습니다.');
            }

            console.log('[StoryMaker Gemini 1.3.1] result-package POST 요청 중...');
            const saveRes = await request('POST', BACKEND_URL + '/api/test/result-package', {
                job_id: jobId,
                project_title: projectTitle,
                source: 'tampermonkey-gemini-worker-1.3.1',
                result_text: resultText,
                result_raw: rawResultText,
                result_clean: resultText,
                result_json: {}
            });

            console.log('[StoryMaker Gemini 1.3.1] result-package 저장 완료:', saveRes);

            markJobHandled(jobId);

            const nextCount = getChatJobCount() + 1;
            setChatJobCount(nextCount);
            console.log('[StoryMaker Gemini 1.3.1] 현재 Gemini 대화창 처리 횟수:', nextCount, '/', MAX_JOBS_PER_CHAT);

            if (nextCount >= MAX_JOBS_PER_CHAT) {
                await delay(1200);
                openFreshGeminiChat('max jobs per chat reached after save');
            }
        } catch (err) {
            const errMsg = err.message || String(err);
            console.error('[StoryMaker Gemini 1.3.1] runJob 중 오류 발생:', errMsg);
            await reportErrorToBackend(jobId, projectTitle, errMsg);
        } finally {
            processingJobs.delete(jobId);
        }
    }

    async function workerLoop() {
        if (workerState.stopped || window[SINGLETON_KEY] !== workerState) return;
        if (running) return;

        try {
            running = true;

            const status = await request('GET', BACKEND_URL + '/api/test/trigger-status');

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

            if (jobId === lastHandledJobId) return;
            if (processingJobs.has(jobId)) return;
            if (hasJobId(SENT_JOBS_KEY, jobId)) return;
            if (hasJobId(HANDLED_JOBS_KEY, jobId)) return;

            // 버튼 클릭으로 생성된 신규 pending job만 실행한다.
            if (jobStatus !== 'pending') return;

            // Gemini 전용 워커이므로 ChatGPT action은 실행하지 않는다.
            if (action !== 'GENERATE_GEMINI') return;

            // 한 대화창에 결과가 5회 이상 쌓였으면,
            // 이번 job은 claim하지 않고 새 Gemini 대화창으로 먼저 이동한다.
            if (getChatJobCount() >= MAX_JOBS_PER_CHAT) {
                openFreshGeminiChat('max jobs per chat reached before next job');
                return;
            }

            await runJob(status);

        } catch (err) {
            console.error('[StoryMaker Gemini 1.3.1] loop 실패:', err);
        } finally {
            running = false;
        }
    }

    workerState.timerId = setInterval(workerLoop, POLL_MS);

    setTimeout(workerLoop, 1500);
})();
