(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_MEMBER_MENU_COLOR__) return;
  window.__STORYMAKER_V1_ADMIN_MEMBER_MENU_COLOR__ = true;

  const STYLE_ID = 'storymaker-v1-admin-member-menu-color-style';
  if (document.getElementById(STYLE_ID)) return;

  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    [data-storymaker-member-menu][data-storymaker-admin-authorized="1"],
    [data-storymaker-member-menu][data-storymaker-admin-authorized="1"] * {
      color: #7fffd4 !important;
      font-weight: 900 !important;
      text-shadow: 0 0 10px rgba(127, 255, 212, 0.35) !important;
    }
  `;
  document.head.appendChild(style);
})();
