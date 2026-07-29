(() => {
  'use strict';

  if (window.__STORYMAKER_LIMIT_REQUEST_BRIDGE__) return;
  window.__STORYMAKER_LIMIT_REQUEST_BRIDGE__ = true;

  function openRequestModal(prefill = {}) {
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      const featureRequests = window.StoryMakerV1FeatureRequests;
      if (featureRequests?.newRequest) {
        window.clearInterval(timer);
        featureRequests.newRequest({
          title: String(prefill.title || '무료 제작 한도 관련 요청'),
          content: String(prefill.content || '월간 무료 제작 한도와 추가 이용에 관해 문의드립니다.'),
        });
        return;
      }
      if (attempts >= 30) {
        window.clearInterval(timer);
        window.alert('요청사항 작성 화면을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
      }
    }, 100);
  }

  window.addEventListener('message', (event) => {
    if (event.origin !== window.location.origin) return;
    if (event.data?.type !== 'storymaker:open-feature-request') return;
    openRequestModal(event.data.prefill || {});
  });
})();
