(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_MEMBER_MENU_COLOR__) return;
  window.__STORYMAKER_V1_ADMIN_MEMBER_MENU_COLOR__ = true;

  const STYLE_ID = 'storymaker-v1-admin-member-menu-color-style';
  if (document.getElementById(STYLE_ID)) return;

  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    [data-storymaker-member-menu][data-storymaker-admin-authorized="1"] {
      background: linear-gradient(135deg, #115e59, #0f766e) !important;
      border: 1px solid #5eead4 !important;
      box-shadow: 0 8px 22px rgba(15, 118, 110, 0.28) !important;
      color: #ffffff !important;
      font-weight: 950 !important;
      cursor: pointer !important;
    }
    [data-storymaker-member-menu][data-storymaker-admin-authorized="1"] * {
      color: #ffffff !important;
      fill: currentColor !important;
      stroke: currentColor !important;
      font-weight: 950 !important;
      text-shadow: none !important;
    }
    [data-storymaker-member-menu][data-storymaker-admin-authorized="1"]:hover,
    [data-storymaker-member-menu][data-storymaker-admin-authorized="1"]:focus-visible {
      background: linear-gradient(135deg, #0f766e, #0d9488) !important;
      border-color: #99f6e4 !important;
      outline: 3px solid rgba(45, 212, 191, 0.28) !important;
      outline-offset: 2px !important;
    }
  `;
  document.head.appendChild(style);
})();
