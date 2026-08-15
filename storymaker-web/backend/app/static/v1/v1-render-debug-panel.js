(() => {
  if (window.__V1_RENDER_DEBUG_PANEL__) return;
  window.__V1_RENDER_DEBUG_PANEL__ = true;

  const MAX_LINES = 180;
  const lines = [];
  let panelBody = null;

  const now = () => new Date().toLocaleTimeString('ko-KR', { hour12: false });
  const safeText = (value) => {
    try {
      if (typeof value === 'string') return value;
      return JSON.stringify(value);
    } catch (_) {
      return String(value);
    }
  };

  const add = (type, message) => {
    const line = `[${now()}] [${type}] ${message}`;
    lines.push(line);
    if (lines.length > MAX_LINES) lines.splice(0, lines.length - MAX_LINES);
    if (panelBody) {
      panelBody.textContent = lines.join('\n');
      panelBody.scrollTop = panelBody.scrollHeight;
    }
  };

  const findMonitor = () => {
    const all = Array.from(document.querySelectorAll('div,section,article'));
    return all.find((el) => {
      if (el.dataset && el.dataset.v1DebugPanelHost) return false;
      const text = (el.textContent || '').trim();
      return text.includes('STORYMAKER RENDER MONITOR') && text.includes('[READY]');
    });
  };

  const mount = () => {
    if (document.getElementById('v1-render-debug-panel')) return true;
    const monitor = findMonitor();
    if (!monitor || !monitor.parentElement) return false;

    const panel = document.createElement('section');
    panel.id = 'v1-render-debug-panel';
    panel.dataset.v1DebugPanelHost = '1';
    panel.style.cssText = [
      'margin-top:14px',
      'border:1px solid rgba(96,165,250,.35)',
      'border-radius:18px',
      'background:#050b1f',
      'overflow:hidden',
      'box-shadow:inset 0 0 0 1px rgba(255,255,255,.02)'
    ].join(';');

    const head = document.createElement('div');
    head.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid rgba(96,165,250,.22);font:700 12px/1.4 system-ui;color:#8fb7ff;letter-spacing:.12em';
    head.innerHTML = '<span>DETAIL ERROR · OPERATION LOG</span>';

    const buttons = document.createElement('div');
    buttons.style.cssText = 'display:flex;gap:8px';

    const copy = document.createElement('button');
    copy.type = 'button';
    copy.textContent = '복사';
    copy.style.cssText = 'border:1px solid rgba(143,183,255,.35);background:#0b1533;color:#dbeafe;border-radius:10px;padding:5px 10px;cursor:pointer';
    copy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(lines.join('\n'));
        add('PANEL', '로그를 클립보드에 복사했습니다.');
      } catch (error) {
        add('PANEL', `복사 실패: ${error?.message || error}`);
      }
    };

    const clear = document.createElement('button');
    clear.type = 'button';
    clear.textContent = '지우기';
    clear.style.cssText = copy.style.cssText;
    clear.onclick = () => {
      lines.length = 0;
      if (panelBody) panelBody.textContent = '';
    };

    buttons.append(copy, clear);
    head.appendChild(buttons);

    panelBody = document.createElement('pre');
    panelBody.style.cssText = 'margin:0;padding:14px 16px;height:220px;overflow:auto;white-space:pre-wrap;word-break:break-word;font:12px/1.65 Consolas,monospace;color:#cbd5e1;background:#030817';

    panel.append(head, panelBody);
    monitor.parentElement.appendChild(panel);
    add('PANEL', '임시 상세 로그 패널이 연결되었습니다.');
    return true;
  };

  const originalFetch = window.fetch;
  window.fetch = async function(input, init) {
    const url = typeof input === 'string' ? input : input?.url || '';
    const method = init?.method || 'GET';
    const interesting = /slideshow|shortform|browser-podcast|browser-shortform|mobile\/one-shot|podcast|thumbnail|jobs\//i.test(url);
    const started = performance.now();
    if (interesting) add('FETCH', `${method} ${url}`);
    try {
      const response = await originalFetch.apply(this, arguments);
      if (interesting) {
        const ms = Math.round(performance.now() - started);
        add('FETCH', `${response.status} ${method} ${url} · ${ms}ms`);
        if (!response.ok) {
          try {
            const body = await response.clone().text();
            add('RESPONSE', body.slice(0, 3000));
          } catch (_) {}
        }
      }
      return response;
    } catch (error) {
      if (interesting) add('FETCH ERROR', `${method} ${url} · ${error?.stack || error}`);
      throw error;
    }
  };

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url) {
    this.__v1Debug = { method, url, started: 0 };
    return originalOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function() {
    const meta = this.__v1Debug;
    if (meta && /slideshow|shortform|podcast|mobile\/one-shot|jobs\//i.test(meta.url || '')) {
      meta.started = performance.now();
      add('XHR', `${meta.method} ${meta.url}`);
      this.addEventListener('loadend', () => {
        const ms = Math.round(performance.now() - meta.started);
        add('XHR', `${this.status} ${meta.method} ${meta.url} · ${ms}ms`);
        if (this.status >= 400) add('XHR RESPONSE', String(this.responseText || '').slice(0, 3000));
      }, { once: true });
    }
    return originalSend.apply(this, arguments);
  };

  const originalConsoleError = console.error.bind(console);
  console.error = (...args) => {
    add('CONSOLE ERROR', args.map(safeText).join(' '));
    originalConsoleError(...args);
  };

  const originalConsoleWarn = console.warn.bind(console);
  console.warn = (...args) => {
    const text = args.map(safeText).join(' ');
    if (/slideshow|shortform|podcast|render|mp4|error|failed|closed file/i.test(text)) add('CONSOLE WARN', text);
    originalConsoleWarn(...args);
  };

  window.addEventListener('error', (event) => {
    add('WINDOW ERROR', `${event.message || 'unknown'} @ ${event.filename || ''}:${event.lineno || 0}:${event.colno || 0}`);
  });

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    add('PROMISE ERROR', reason?.stack || reason?.message || safeText(reason));
  });

  const mountTimer = setInterval(() => {
    if (mount()) clearInterval(mountTimer);
  }, 500);
  setTimeout(() => clearInterval(mountTimer), 30000);

  add('BOOT', `페이지 ${location.href}`);
})();
