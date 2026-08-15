(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ARCHIVE_HEADER_NOTICE__) return;
  window.__STORYMAKER_V1_ARCHIVE_HEADER_NOTICE__ = true;

  const HOST_ID = 'storymaker-v1-inline-panel-host';
  const TITLE_ID = 'storymaker-v1-inline-panel-title';
  const NOTICE_ID = 'storymaker-v1-archive-retention-notice';
  const STYLE_ID = 'storymaker-v1-archive-header-notice-style';
  const NOTICE_TEXT = '콘텐츠 데이터 보관 : 무료 사용자 10개, 스타터 20개 (중요 데이터는 다운로드 해주세요!)';

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .sm-v1-archive-header-active{
        gap:16px!important;
      }
      .sm-v1-archive-title-active{
        font-size:20px!important;
        line-height:1.35!important;
        flex:0 0 auto;
      }
      .sm-v1-inline-head-main{
        display:flex;
        align-items:center;
        gap:18px;
        min-width:0;
        flex:1 1 auto;
        flex-wrap:wrap;
      }
      #${NOTICE_ID}{
        color:#94a3b8;
        font-size:13px;
        line-height:1.5;
        font-weight:750;
        letter-spacing:-.01em;
        white-space:normal;
      }
      @media (max-width:900px){
        .sm-v1-inline-head-main{
          align-items:flex-start;
          flex-direction:column;
          gap:4px;
        }
        #${NOTICE_ID}{font-size:12px;}
      }
    `;
    document.head.appendChild(style);
  }

  function findArchiveTitle() {
    const direct = document.getElementById(TITLE_ID);
    if (direct && clean(direct.textContent) === '보관함') return direct;
    return Array.from(document.querySelectorAll('header h1,header h2,header h3,header div,section h1,section h2,section h3,section div'))
      .find((node) => clean(node.textContent) === '보관함' && node.getBoundingClientRect().height > 0) || null;
  }

  function removeArchiveHeader(title) {
    document.querySelectorAll('.sm-v1-archive-header-active').forEach((node) => node.classList.remove('sm-v1-archive-header-active'));
    document.querySelectorAll('.sm-v1-archive-title-active').forEach((node) => node.classList.remove('sm-v1-archive-title-active'));
    document.getElementById(NOTICE_ID)?.remove();
    const main = title?.closest('.sm-v1-inline-head-main');
    if (main && title) main.replaceWith(title);
  }

  function apply() {
    const title = findArchiveTitle();
    if (!title) return;

    ensureStyle();
    const head = title.closest('header') || title.parentElement;
    if (!head) return;
    head.classList.add('sm-v1-archive-header-active');
    title.classList.add('sm-v1-archive-title-active');

    let main = title.closest('.sm-v1-inline-head-main');
    if (!main) {
      main = document.createElement('div');
      main.className = 'sm-v1-inline-head-main';
      title.parentNode?.insertBefore(main, title);
      main.appendChild(title);
    }

    let notice = document.getElementById(NOTICE_ID);
    if (!notice) {
      notice = document.createElement('div');
      notice.id = NOTICE_ID;
      main.appendChild(notice);
    }
    notice.textContent = NOTICE_TEXT;
  }

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      apply();
    });
  };

  new MutationObserver(schedule).observe(document.documentElement, {childList: true, subtree: true, characterData: true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', schedule, {once: true});
  else schedule();
})();
