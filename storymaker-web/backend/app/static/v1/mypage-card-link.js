(() => {
  if (window.__STORYMAKER_MYPAGE_TEXT_LINK_V6__) return;
  window.__STORYMAKER_MYPAGE_TEXT_LINK_V6__ = true;

  const normalize = (value = '') => String(value).replace(/\s+/g, ' ').trim();

  const findProfileCard = () => {
    const leaves = [...document.querySelectorAll('div, span, p, strong')]
      .filter((el) => el.children.length === 0);

    const roleLeaf = leaves.find((el) => {
      const text = normalize(el.textContent);
      return (text.includes('관리자') || text.includes('사용자')) && text.includes('free');
    });

    if (!roleLeaf) return null;

    let node = roleLeaf;
    for (let depth = 0; node && depth < 7; depth += 1, node = node.parentElement) {
      const text = normalize(node.textContent);
      const rect = node.getBoundingClientRect();
      if (
        (text.includes('관리자') || text.includes('사용자')) &&
        text.includes('free') &&
        rect.width >= 180 && rect.width <= 420 &&
        rect.height >= 70 && rect.height <= 180
      ) return node;
    }
    return null;
  };

  const findTargetTexts = (card) => {
    if (!card) return [];
    return [...card.querySelectorAll('div, span, p, strong')].filter((el) => {
      if (el.children.length !== 0) return false;
      const text = normalize(el.textContent);
      const isRole = (text.includes('관리자') || text.includes('사용자')) && text.includes('free');
      const isUsername = Boolean(text) && !isRole && text.length <= 80;
      return isUsername || isRole;
    });
  };

  const openCompanyInfo = () => {
    const menu = [...document.querySelectorAll('button, a, [role="button"]')]
      .find((el) => normalize(el.textContent) === '업체 정보');
    if (!menu) return false;
    menu.click();
    return true;
  };

  const install = () => {
    const card = findProfileCard();
    if (!card) return;

    card.dataset.mypageProfileCard = '1';
    if (card.dataset.mypageCompanyAreaLinked !== '1') {
      card.dataset.mypageCompanyAreaLinked = '1';
      card.addEventListener('click', (event) => {
        const rect = card.getBoundingClientRect();
        if (event.clientX >= rect.right - 96) return;
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        openCompanyInfo();
      }, true);
    }

    findTargetTexts(card).forEach((el) => {
      if (el.dataset.mypageReactLinked === '1') return;
      el.dataset.mypageReactLinked = '1';
      el.style.cursor = 'pointer';
      el.setAttribute('role', 'link');
      el.setAttribute('tabindex', '0');
      el.setAttribute('aria-label', '업체 정보 열기');

      const open = (event) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        openCompanyInfo();
      };

      el.addEventListener('click', open, true);
      el.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') open(event);
      }, true);
    });
  };

  install();
  new MutationObserver(install).observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });
  setTimeout(install, 500);
  setTimeout(install, 1500);
})();
