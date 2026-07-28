(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_MEMBER_MENU_COLOR__) return;
  window.__STORYMAKER_V1_ADMIN_MEMBER_MENU_COLOR__ = true;

  const TARGET_COLOR = '#7fffd4';
  let isAdmin = false;

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();

  function detectAdmin(user) {
    if (!user || typeof user !== 'object') return false;
    const role = clean(user.role || user.user_role || user.type).toLowerCase();
    return user.is_admin === true || user.admin === true || role === 'admin';
  }

  function colorMemberMenu() {
    if (!isAdmin) return;
    document.querySelectorAll('button,a,[role="button"],li').forEach((item) => {
      const rect = item.getBoundingClientRect();
      if (rect.left >= 320 || rect.width < 80 || rect.height < 24 || rect.height > 100) return;
      const isMemberLabel = (value) => ['회원관리', '회원 관리'].includes(clean(value));
      const exact = Array.from(item.querySelectorAll('*')).find((node) => isMemberLabel(node.textContent))
        || (isMemberLabel(item.textContent) ? item : null);
      if (!exact) return;
      exact.style.setProperty('color', TARGET_COLOR, 'important');
      exact.style.setProperty('font-weight', '900', 'important');
      item.dataset.storymakerAdminMemberMenu = '1';
    });
  }

  async function resolveRole() {
    try {
      const response = await fetch('/v1-api/auth/me', {
        credentials: 'include',
        headers: {Accept: 'application/json'},
      });
      const payload = await response.json().catch(() => ({}));
      const user = payload?.data?.user || payload?.user || payload?.data || null;
      isAdmin = response.ok && detectAdmin(user);
    } catch (_) {
      isAdmin = false;
    }
    colorMemberMenu();
  }

  new MutationObserver(colorMemberMenu).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  resolveRole();
})();
