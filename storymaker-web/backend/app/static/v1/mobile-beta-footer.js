(() => {
  'use strict';

  const MOBILE_QUERY = window.matchMedia('(max-width: 767px)');
  const ROOT_CLASS = 'sm-mobile-beta-footer-active';
  const CLICKABLE = 'button,a,[role="button"],[role="menuitem"]';
  const BROWSER_AI_HIDDEN_ATTR = 'data-sm-mobile-browser-ai-hidden';
  const FOOTER_HIDDEN_ATTR = 'data-sm-mobile-footer';
  const MEMBER_MOVED_ATTR = 'data-sm-mobile-member-moved';
  const TOP_ACTIONS_ATTR = 'data-sm-mobile-top-actions';
  const PC_CONTINUE_HIDDEN_ATTR = 'data-sm-mobile-pc-continue-hidden';
  const PC_CONTINUE_CARD_ID = 'sm-mobile-pc-continue-card';

  let observer = null;
  let scheduled = false;
  let movedMemberButton = null;
  let memberPlaceholder = null;

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  const isVisible = (node) => {
    if (!(node instanceof HTMLElement)) return false;
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };

  function isMobileBetaScreen() {
    if (!MOBILE_QUERY.matches) return false;

    const url = new URL(location.href);
    const page = clean(url.searchParams.get('page'));
    if (page === 'betaProduction') return true;
    if (/\/v1\/beta\/production\/?$/i.test(url.pathname)) return true;

    return Array.from(document.querySelectorAll('h1,h2,h3,[role="heading"],button'))
      .some((node) => {
        if (!isVisible(node)) return false;
        const text = clean(node.textContent);
        return /딸깍\s*제작/.test(text) || text === '모바일 작업실';
      });
  }

  function exactButton(labels) {
    return Array.from(document.querySelectorAll(CLICKABLE))
      .find((node) => isVisible(node) && labels.includes(clean(node.textContent))) || null;
  }

  function commonFooter(home, create, archive) {
    let node = home.parentElement;
    for (let depth = 0; node && depth < 7; depth += 1, node = node.parentElement) {
      if (!node.contains(create) || !node.contains(archive)) continue;
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      const bottomArea = rect.bottom >= window.innerHeight - 140;
      const footerLike = style.position === 'fixed' || style.position === 'sticky' || bottomArea;
      if (footerLike) return node;
    }
    return null;
  }

  function findTopProfileButton() {
    const candidates = Array.from(document.querySelectorAll('button'))
      .filter((node) => {
        if (!isVisible(node)) return false;
        const text = clean(node.textContent);
        const label = clean(node.getAttribute('aria-label'));
        return text === '👤' || /마이페이지|계정/.test(label);
      });

    return candidates.find((button) => {
      let node = button.parentElement;
      for (let depth = 0; node && depth < 5; depth += 1, node = node.parentElement) {
        if (clean(node.textContent).includes('모바일 작업실')) return true;
      }
      return false;
    }) || null;
  }

  function findMemberButton() {
    return Array.from(document.querySelectorAll(CLICKABLE))
      .find((node) => {
        if (!isVisible(node) || node === movedMemberButton) return false;
        const text = clean(node.textContent);
        return text === '회원 관리' || text === '회원관리';
      }) || null;
  }

  function moveMemberButtonToTop() {
    if (movedMemberButton?.isConnected && movedMemberButton.hasAttribute(MEMBER_MOVED_ATTR)) return;

    const profileButton = findTopProfileButton();
    const memberButton = findMemberButton();
    if (!profileButton || !memberButton || !memberButton.parentNode || !profileButton.parentElement) return;

    memberPlaceholder = document.createComment('storymaker-mobile-member-original-position');
    memberButton.parentNode.insertBefore(memberPlaceholder, memberButton);

    const topActions = profileButton.parentElement;
    topActions.setAttribute(TOP_ACTIONS_ATTR, '1');
    memberButton.setAttribute(MEMBER_MOVED_ATTR, '1');
    topActions.insertBefore(memberButton, profileButton);
    movedMemberButton = memberButton;
  }

  function restoreMemberButton() {
    if (movedMemberButton) {
      movedMemberButton.removeAttribute(MEMBER_MOVED_ATTR);
      if (memberPlaceholder?.parentNode) {
        memberPlaceholder.parentNode.insertBefore(movedMemberButton, memberPlaceholder);
        memberPlaceholder.remove();
      }
    }

    document.querySelectorAll(`[${TOP_ACTIONS_ATTR}="1"]`)
      .forEach((node) => node.removeAttribute(TOP_ACTIONS_ATTR));

    movedMemberButton = null;
    memberPlaceholder = null;
  }

  function hideBrowserAiPanel() {
    if (!MOBILE_QUERY.matches) return;
    Array.from(document.querySelectorAll('div')).forEach((node) => {
      if (!(node instanceof HTMLElement) || !isVisible(node)) return;
      const title = Array.from(node.querySelectorAll('p')).find((item) => clean(item.textContent) === 'BROWSER AI');
      if (!title) return;
      const style = getComputedStyle(node);
      if (style.position !== 'fixed') return;
      node.setAttribute(BROWSER_AI_HIDDEN_ATTR, '1');
    });
  }

  function findProductionModule(markerPattern) {
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,[role="heading"],strong,p'))
      .filter((node) => node instanceof HTMLElement && isVisible(node))
      .filter((node) => markerPattern.test(clean(node.textContent)));

    for (const heading of headings) {
      let node = heading;
      for (let depth = 0; node && depth < 7; depth += 1, node = node.parentElement) {
        if (!(node instanceof HTMLElement)) continue;
        const text = clean(node.textContent);
        const rect = node.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) continue;
        if (text.length >= 12 && text.length <= 4000 && (node.tagName === 'SECTION' || node.tagName === 'ARTICLE' || depth >= 2)) {
          return node;
        }
      }
    }
    return null;
  }

  function hidePcOnlyProductionModules() {
    const patterns = [
      /^(03\s*)?팟캐스트(?:\s*생성)?/i,
      /^(04\s*)?(?:숏폼|릴스|쇼츠|MP4)(?:\s*생성|\s*제작|\s*미리보기)?/i,
      /^MP4\s*(?:생성|제작|미리보기|다운로드)/i,
    ];
    const hiddenModules = [];

    patterns.forEach((pattern) => {
      const module = findProductionModule(pattern);
      if (!module || module.hasAttribute(PC_CONTINUE_HIDDEN_ATTR)) return;
      module.setAttribute(PC_CONTINUE_HIDDEN_ATTR, '1');
      hiddenModules.push(module);
    });

    document.querySelectorAll('#v1-manual-podcast-panel, #v1-inline-manual-podcast-button')
      .forEach((node) => {
        if (node instanceof HTMLElement) node.setAttribute(PC_CONTINUE_HIDDEN_ATTR, '1');
      });

    let card = document.getElementById(PC_CONTINUE_CARD_ID);
    if (!card) {
      card = document.createElement('section');
      card.id = PC_CONTINUE_CARD_ID;
      card.setAttribute('aria-label', 'PC 후속 제작 안내');
      card.innerHTML = `
        <div class="sm-mobile-pc-continue-icon" aria-hidden="true">PC</div>
        <div class="sm-mobile-pc-continue-copy">
          <strong>글과 사진 저장이 완료되었습니다</strong>
          <p>팟캐스트, 숏폼 MP4, 썸네일 제작은 PC의 스토리메이커 보관함에서 이어서 진행해 주세요.</p>
        </div>`;
    }

    const firstHidden = hiddenModules[0]
      || document.querySelector(`[${PC_CONTINUE_HIDDEN_ATTR}="1"]`);
    if (firstHidden?.parentNode && !card.isConnected) {
      firstHidden.parentNode.insertBefore(card, firstHidden);
    }
  }

  function restore() {
    document.documentElement.classList.remove(ROOT_CLASS);
    document.querySelectorAll(`[${FOOTER_HIDDEN_ATTR}="1"]`)
      .forEach((node) => node.removeAttribute(FOOTER_HIDDEN_ATTR));
    document.querySelectorAll(`[${BROWSER_AI_HIDDEN_ATTR}="1"]`)
      .forEach((node) => node.removeAttribute(BROWSER_AI_HIDDEN_ATTR));
    document.querySelectorAll(`[${PC_CONTINUE_HIDDEN_ATTR}="1"]`)
      .forEach((node) => node.removeAttribute(PC_CONTINUE_HIDDEN_ATTR));
    document.getElementById(PC_CONTINUE_CARD_ID)?.remove();
    restoreMemberButton();
  }

  function apply() {
    scheduled = false;
    if (!isMobileBetaScreen()) {
      restore();
      return;
    }

    hideBrowserAiPanel();
    moveMemberButtonToTop();
    hidePcOnlyProductionModules();

    const home = exactButton(['홈']);
    const create = exactButton(['만들기', '제작']);
    const archive = exactButton(['보관함']);
    if (home && create && archive) {
      const footer = commonFooter(home, create, archive);
      if (footer) footer.setAttribute(FOOTER_HIDDEN_ATTR, '1');
    }

    document.documentElement.classList.add(ROOT_CLASS);
  }

  function scheduleApply() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(apply);
  }

  function startObserver() {
    if (observer) return;
    observer = new MutationObserver(scheduleApply);
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  function stopObserver() {
    observer?.disconnect();
    observer = null;
  }

  function handleViewportChange() {
    if (MOBILE_QUERY.matches) {
      startObserver();
      scheduleApply();
    } else {
      stopObserver();
      restore();
    }
  }

  MOBILE_QUERY.addEventListener?.('change', handleViewportChange);
  window.addEventListener('popstate', scheduleApply);
  window.addEventListener('hashchange', scheduleApply);
  document.addEventListener('DOMContentLoaded', handleViewportChange, { once: true });

  if (document.readyState !== 'loading') handleViewportChange();
})();
