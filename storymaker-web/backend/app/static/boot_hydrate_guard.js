// StoryMaker boot hydrate guard
// 로그인 복구 직후 DB에서 불러온 프로젝트/업체/전화번호가 showHomeScreen 초기화로 지워지는 것을 막는다.
(function(){
  'use strict';

  function hasToken(){
    return !!String(localStorage.getItem('storymaker_token') || '').trim();
  }

  function isStorymakerPath(){
    return String(location.pathname || '').indexOf('/storymaker') >= 0;
  }

  function refreshPersona(){
    try {
      if (typeof window.syncProfileSummary === 'function') window.syncProfileSummary();
      if (typeof window.syncStoryMakerPersonaFromDb === 'function') window.syncStoryMakerPersonaFromDb(true);
    } catch(e) {}
  }

  function protectHomeReset(){
    if (typeof window.showHomeScreen !== 'function' || window.showHomeScreen.bootGuard === true) return;
    var original = window.showHomeScreen;
    var wrapped = function(){
      if (hasToken() && isStorymakerPath() && window.storymakerBootHydrated) {
        try {
          var adminModal = document.getElementById('admin-modal');
          if (adminModal) adminModal.style.display = 'none';
          if (typeof window.toggleInputCard === 'function') window.toggleInputCard(true);
          if (typeof window.initializeWorkspaceAccordions === 'function') window.initializeWorkspaceAccordions();
          refreshPersona();
        } catch(e) {}
        return;
      }
      return original.apply(this, arguments);
    };
    wrapped.bootGuard = true;
    window.showHomeScreen = wrapped;
  }

  function fixMyPageOpen(){
    window.storymakerOpenMyPageNow = async function(){
      if (typeof window.showMyPageModal === 'function') {
        return await window.showMyPageModal();
      }
      var modal = document.getElementById('mypage-modal');
      if (modal) {
        modal.style.setProperty('display', 'flex', 'important');
        modal.setAttribute('aria-hidden', 'false');
      }
      return true;
    };
  }

  function boot(){
    protectHomeReset();
    fixMyPageOpen();
    setTimeout(function(){ protectHomeReset(); fixMyPageOpen(); refreshPersona(); }, 300);
    setTimeout(function(){ protectHomeReset(); fixMyPageOpen(); refreshPersona(); }, 1200);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  window.addEventListener('load', boot);
})();
