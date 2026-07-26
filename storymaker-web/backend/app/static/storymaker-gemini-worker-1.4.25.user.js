// ==UserScript==
// @name         StoryMaker Legacy Gemini Worker 1.4.25 - BLOCKED IN V1
// @namespace    storymaker-v1-isolated
// @version      0.0.1-blocked
// @description  V1 격리 환경에서는 이 구버전 운영 Worker를 사용할 수 없습니다.
// @match        https://gemini.google.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(function () {
    'use strict';
    console.error('[StoryMaker V1] 구버전 운영 Gemini Worker는 차단되었습니다. V1 전용 Worker를 설치하세요: /v1/storymaker-gemini-worker-v1.user.js');
    alert('StoryMaker V1에서는 이 구버전 운영 Worker를 사용할 수 없습니다. V1 전용 Worker를 설치해 주세요.');
})();
