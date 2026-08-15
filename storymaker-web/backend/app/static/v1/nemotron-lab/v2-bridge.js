(() => {
  'use strict';

  const SOURCE = '/api/nemotron-lab/ui.js?v=20260715-model-picker-fix-1';
  let requestedOpen = new URLSearchParams(window.location.search).get('page') === 'aiLab2';
  let requestedClose = false;
  let loading = false;

  const stub = {
    __lab2Loader: true,
    open() {
      requestedOpen = true;
      load();
    },
    close() {
      requestedClose = true;
      load();
    },
  };

  function load() {
    if (loading || document.querySelector('script[data-lab2-native-source]')) return;
    loading = true;
    const script = document.createElement('script');
    script.src = SOURCE;
    script.async = true;
    script.dataset.lab2NativeSource = '1';
    script.onload = () => {
      loading = false;
      const api = window.StoryMakerNemotronLab;
      if (!api || api === stub || api.__lab2Loader) return;
      if (requestedClose) {
        requestedClose = false;
        api.close?.();
      } else if (requestedOpen) {
        requestedOpen = false;
        api.open?.();
      }
    };
    script.onerror = () => {
      loading = false;
      console.error('[AI 연구실 2] 원본 UI 모듈을 불러오지 못했습니다.');
    };
    document.head.appendChild(script);
  }

  window.StoryMakerNemotronLab = stub;
  load();
})();
