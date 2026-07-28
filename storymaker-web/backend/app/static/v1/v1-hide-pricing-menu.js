(() => {
  'use strict';

  if (window.__STORYMAKER_V1_HIDE_PRICING_MENU__) return;
  window.__STORYMAKER_V1_HIDE_PRICING_MENU__ = true;

  const LABEL = '요금제';
  const MARK = 'data-storymaker-pricing-hidden';

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();

  function clickableFromLabel(labelEl) {
    let node = labelEl;
    while (node && node !== document.body) {
      const rect = node.getBoundingClientRect();
      const tag = node.tagName;
      if ((tag === 'BUTTON' || tag === 'A' || node.getAttribute('role') === 'button') && rect.width > 70) return node;
      if (rect.width > 100 && rect.height >= 32 && rect.height <= 90) return node;
      node = node.parentElement;
    }
    return labelEl;
  }

  function hidePricingMenu() {
    Array.from(document.querySelectorAll('button,a,div,span,p'))
      .filter((el) => clean(el.textContent) === LABEL)
      .forEach((labelEl) => {
        const item = clickableFromLabel(labelEl);
        if (!item || item.getAttribute(MARK) === '1') return;
        item.setAttribute(MARK, '1');
        item.style.setProperty('display', 'none', 'important');
        item.setAttribute('aria-hidden', 'true');
        item.setAttribute('tabindex', '-1');
      });
  }

  hidePricingMenu();
  new MutationObserver(hidePricingMenu).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  window.addEventListener('popstate', hidePricingMenu);
  window.addEventListener('hashchange', hidePricingMenu);
  console.info('[StoryMaker V1] pricing menu hidden for all users');
})();
