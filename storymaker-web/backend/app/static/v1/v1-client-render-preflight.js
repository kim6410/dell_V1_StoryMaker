(() => {
  'use strict';

  const KEY = '__STORYMAKER_V1_CLIENT_RENDER_PREFLIGHT__';
  if (window[KEY]?.started) return;

  const state = {
    started: true,
    checkedAt: new Date().toISOString(),
    secureContext: window.isSecureContext === true,
    crossOriginIsolated: window.crossOriginIsolated === true,
    webAssembly: typeof WebAssembly === 'object',
    wasmThreads: typeof SharedArrayBuffer === 'function' && window.crossOriginIsolated === true,
    webgpuApi: !!navigator.gpu,
    webgpuAdapter: false,
    webcodecsApi: typeof VideoEncoder === 'function' && typeof VideoFrame === 'function',
    h264Supported: false,
    avcConfig: null,
    browserPrimaryReady: false,
    fallbackOrder: ['macmini', 'dell'],
    reasons: [],
  };

  window[KEY] = state;
  window.__STORYMAKER_V1_CLIENT_CAPS__ = state;

  function publish() {
    state.browserPrimaryReady = Boolean(
      state.secureContext &&
      state.webAssembly &&
      state.webcodecsApi &&
      state.h264Supported
    );

    state.reasons = [];
    if (!state.secureContext) state.reasons.push('HTTPS 또는 localhost 보안 컨텍스트가 아닙니다.');
    if (!state.webAssembly) state.reasons.push('WebAssembly를 지원하지 않습니다.');
    if (!state.webcodecsApi) state.reasons.push('WebCodecs VideoEncoder를 지원하지 않습니다.');
    if (state.webcodecsApi && !state.h264Supported) state.reasons.push('브라우저 H.264 인코더를 사용할 수 없습니다.');
    if (!state.webgpuApi) state.reasons.push('WebGPU 미지원: Canvas/WebCodecs 경로를 사용합니다.');
    if (state.webgpuApi && !state.webgpuAdapter) state.reasons.push('WebGPU 어댑터를 얻지 못했습니다.');
    if (!state.wasmThreads) state.reasons.push('WASM 멀티스레드 미사용: 단일 스레드 경로를 사용합니다.');

    document.documentElement.dataset.v1ClientRenderReady = state.browserPrimaryReady ? 'true' : 'false';
    document.documentElement.dataset.v1RenderFallback = 'macmini,dell';

    window.dispatchEvent(new CustomEvent('storymaker:v1-client-render-capabilities', {
      detail: { ...state, reasons: [...state.reasons] },
    }));

    console.info('[StoryMaker V1] client render preflight', state);
  }

  async function check() {
    if (state.webgpuApi) {
      try {
        state.webgpuAdapter = !!(await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' }));
      } catch (error) {
        state.webgpuAdapter = false;
        console.warn('[StoryMaker V1] WebGPU adapter check failed', error);
      }
    }

    if (state.webcodecsApi && typeof VideoEncoder.isConfigSupported === 'function') {
      const candidates = [
        { codec: 'avc1.42001f', width: 1080, height: 1920, bitrate: 6_000_000, framerate: 24, avc: { format: 'avc' } },
        { codec: 'avc1.4d401f', width: 1080, height: 1920, bitrate: 6_000_000, framerate: 24, avc: { format: 'avc' } },
        { codec: 'avc1.42001e', width: 720, height: 1280, bitrate: 3_000_000, framerate: 24, avc: { format: 'avc' } },
      ];

      for (const config of candidates) {
        try {
          const result = await VideoEncoder.isConfigSupported(config);
          if (result?.supported) {
            state.h264Supported = true;
            state.avcConfig = result.config || config;
            break;
          }
        } catch (_) {
          // 다음 H.264 설정을 검사합니다.
        }
      }
    }

    publish();
    return state;
  }

  state.ready = check();
})();
