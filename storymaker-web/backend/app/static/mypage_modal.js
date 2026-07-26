// StoryMaker MyPage Modal UI helper
// 기준 원칙:
// - 마이페이지 데이터 로딩은 app_auth.js의 showMyPageModal()만 담당한다.
// - 이 파일은 모달 UI 열기/닫기와 마이페이지 내부 로그아웃 버튼만 담당한다.
// - showMyPageModal(), handleLogout() 같은 인증 핵심 함수는 절대 덮어쓰지 않는다.
(function () {
  'use strict';

  function modal() {
    return document.getElementById('mypage-modal');
  }

  function openMyPageModalUi() {
    const el = modal();
    if (!el) return;
    el.classList.add('is-open');
    el.style.setProperty('display', 'flex', 'important');
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-modal', 'true');
    el.setAttribute('aria-hidden', 'false');
    document.body.classList.add('mypage-modal-open');
  }

  function closeMyPageModal() {
    const el = modal();
    if (el) {
      el.classList.remove('is-open');
      el.style.setProperty('display', 'none', 'important');
      el.setAttribute('aria-hidden', 'true');
    }
    document.body.classList.remove('mypage-modal-open');

    try {
      const url = new URL(window.location.href);
      const action = url.searchParams.get('action');
      const isMyPageRoute = action === 'mypage' || url.pathname.includes('/mypage') || url.hash.toLowerCase().includes('mypage');
      if (isMyPageRoute) {
        url.searchParams.delete('action');
        url.hash = '';
        const cleanUrl = url.pathname + (url.search ? url.search : '');
        window.history.replaceState(null, '', cleanUrl || '/storymaker');
      }
    } catch (e) {}
  }

  function logoutFromMyPage() {
    showSessionExitConfirm();
  }

  function showSessionExitConfirm() {
    let confirmBox = document.getElementById('mypage-session-exit-confirm');
    if (!confirmBox) {
      confirmBox = document.createElement('div');
      confirmBox.id = 'mypage-session-exit-confirm';
      confirmBox.innerHTML = '<div class="mypage-session-exit-card"><div class="mypage-session-exit-title">로그아웃 하시겠습니까?</div><div class="mypage-session-exit-desc">현재 StoryMaker 작업 세션을 종료합니다.</div><div class="mypage-session-exit-actions"><button type="button" id="mypage-session-exit-cancel">취소</button><button type="button" id="mypage-session-exit-yes">예</button></div></div>';
      document.body.appendChild(confirmBox);
    }
    confirmBox.style.display = 'flex';

    const cancelBtn = document.getElementById('mypage-session-exit-cancel');
    const yesBtn = document.getElementById('mypage-session-exit-yes');
    if (cancelBtn && cancelBtn.dataset.bound !== '1') {
      cancelBtn.dataset.bound = '1';
      cancelBtn.addEventListener('click', function () {
        confirmBox.style.display = 'none';
      });
    }
    if (yesBtn && yesBtn.dataset.bound !== '1') {
      yesBtn.dataset.bound = '1';
      yesBtn.addEventListener('click', function () {
        confirmBox.style.display = 'none';
        if (typeof window.handleLogout === 'function') window.handleLogout();
      });
    }
  }

  function installMyPageCloseEvents() {
    const el = modal();
    if (!el || el.dataset.closeReady === '1') return;
    el.dataset.closeReady = '1';

    const exitBtn = document.getElementById('mypage-session-exit-btn');
    if (exitBtn && exitBtn.dataset.bound !== '1') {
      exitBtn.dataset.bound = '1';
      exitBtn.addEventListener('click', logoutFromMyPage);
    }

    el.addEventListener('click', function (event) {
      if (event.target === el) closeMyPageModal();
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && el.classList.contains('is-open')) {
        closeMyPageModal();
      }
    });
  }

  function initMyPageModal() {
    installMyPageCloseEvents();
    window.openMyPageModalUi = openMyPageModalUi;
    window.closeMyPageModal = closeMyPageModal;
    window.returnFromMyPage = closeMyPageModal;
    window.logoutFromMyPage = logoutFromMyPage;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMyPageModal);
  } else {
    initMyPageModal();
  }
  window.addEventListener('load', initMyPageModal);
})();
