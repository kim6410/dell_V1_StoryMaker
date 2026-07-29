(() => {
  'use strict';

  const REMOVE_LABELS = ['단계별 제작', '팟캐스트', '릴스/숏츠', '릴스/쇼츠', '체험 연구실'];

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  function findSidebar() {
    const marker = Array.from(document.querySelectorAll('h1,h2,h3,div,span,p'))
      .find((el) => {
        const text = clean(el.textContent);
        return text === 'StoryMaker AI v1' || text === '자동 스토리메이커';
      });

    let node = marker || document.querySelector('aside');
    while (node && node !== document.body) {
      const rect = node.getBoundingClientRect();
      if (
        rect.width >= 180 &&
        rect.width <= 420 &&
        rect.height >= window.innerHeight * 0.65
      ) {
        return node;
      }
      node = node.parentElement;
    }

    return document.querySelector('aside');
  }

  function cleanupSidebarMenus() {
    const sidebar = findSidebar();
    if (!sidebar) return;

    const items = Array.from(sidebar.querySelectorAll('button, a'));
    items.forEach((item) => {
      const label = clean(item.textContent);
      if (REMOVE_LABELS.includes(label)) {
        item.remove();
      }
    });
  }

  const observer = new MutationObserver(() => cleanupSidebarMenus());
  observer.observe(document.documentElement, { childList: true, subtree: true });

  cleanupSidebarMenus();
  setTimeout(cleanupSidebarMenus, 500);
  setTimeout(cleanupSidebarMenus, 1500);
  setTimeout(cleanupSidebarMenus, 3000);

  console.info('[StoryMaker V1] menu cleanup bridge active (only workpanel & archive remain)');
})();
