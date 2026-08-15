(() => {
  'use strict';

  const API_URL = 'https://mystorymaker.net/wp-json/storymaker/v1/register';
  const MARKER = 'data-storymaker-inline-register';

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  function findRegisterCard() {
    const heading = Array.from(document.querySelectorAll('h1,h2,h3,h4,p,strong,div,span'))
      .find((el) => clean(el.textContent) === '공개 가입 페이지로 연결됩니다.');
    if (!heading) return null;

    let node = heading;
    while (node && node !== document.body) {
      const text = clean(node.textContent);
      if (text.includes('회원가입 페이지 새 탭으로 열기')) return node;
      node = node.parentElement;
    }
    return null;
  }

  function messageHtml(kind, text) {
    const border = kind === 'error' ? 'rgba(248,113,113,.65)' : 'rgba(74,222,128,.55)';
    const bg = kind === 'error' ? 'rgba(127,29,29,.22)' : 'rgba(20,83,45,.22)';
    const color = kind === 'error' ? '#fecaca' : '#bbf7d0';
    return `<div style="margin-top:14px;padding:13px 14px;border:1px solid ${border};border-radius:14px;background:${bg};color:${color};font-size:14px;line-height:1.55;font-weight:700;">${text}</div>`;
  }

  function renderRegisterForm(card) {
    if (!card || card.hasAttribute(MARKER)) return;
    card.setAttribute(MARKER, '1');

    card.innerHTML = `
      <form data-storymaker-register-form style="display:flex;flex-direction:column;gap:14px;">
        <div>
          <strong style="display:block;color:#f8fafc;font-size:18px;line-height:1.4;margin-bottom:6px;">StoryMaker 회원가입</strong>
          <p style="margin:0;color:#94a3b8;font-size:14px;line-height:1.65;">사용자명과 이메일을 입력하면 비밀번호 설정 안내 메일을 보내드립니다.</p>
        </div>
        <label style="display:block;color:#cbd5e1;font-size:14px;font-weight:800;">
          사용자명
          <input data-register-username type="text" autocomplete="username" placeholder="사용자명을 입력하세요" style="width:100%;height:52px;margin-top:8px;padding:0 16px;border:1px solid rgba(148,163,184,.3);border-radius:15px;box-sizing:border-box;background:rgba(15,23,42,.82);color:#f8fafc;font-size:16px;outline:none;" />
        </label>
        <label style="display:block;color:#cbd5e1;font-size:14px;font-weight:800;">
          이메일
          <input data-register-email type="email" autocomplete="email" placeholder="이메일을 입력하세요" style="width:100%;height:52px;margin-top:8px;padding:0 16px;border:1px solid rgba(148,163,184,.3);border-radius:15px;box-sizing:border-box;background:rgba(15,23,42,.82);color:#f8fafc;font-size:16px;outline:none;" />
        </label>
        <div data-register-message></div>
        <button data-register-submit type="submit" style="width:100%;height:56px;border:0;border-radius:17px;background:#4ddbf3;color:#020617;font-size:17px;font-weight:950;cursor:pointer;">가입 안내 메일 받기</button>
        <p style="margin:0;text-align:center;color:#94a3b8;font-size:13px;line-height:1.55;">메일에서 비밀번호를 설정하면 가입이 완료됩니다.</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px;">
          <button data-register-login type="button" style="height:46px;border:1px solid rgba(148,163,184,.28);border-radius:14px;background:rgba(30,41,59,.78);color:#dbeafe;font-size:14px;font-weight:850;cursor:pointer;">로그인</button>
          <button data-register-password type="button" style="height:46px;border:1px solid rgba(148,163,184,.28);border-radius:14px;background:rgba(30,41,59,.78);color:#dbeafe;font-size:14px;font-weight:850;cursor:pointer;">비밀번호 찾기</button>
        </div>
        <a href="https://mystorymaker.net/" target="_blank" rel="noopener" style="display:block;text-align:center;color:#94a3b8;font-size:13px;font-weight:800;text-decoration:none;margin-top:2px;">← StoryMaker 홈으로</a>
      </form>
    `;

    const form = card.querySelector('[data-storymaker-register-form]');
    const loginButton = card.querySelector('[data-register-login]');
    const passwordButton = card.querySelector('[data-register-password]');

    if (loginButton) {
      loginButton.addEventListener('click', () => {
        const modal = card.closest('[role="dialog"], .modal, [class*="modal"]') || document;
        const loginTab = Array.from(modal.querySelectorAll('button')).find((button) => clean(button.textContent) === '로그인');
        if (loginTab) loginTab.click();
      });
    }

    if (passwordButton) {
      passwordButton.addEventListener('click', () => {
        window.open('https://mystorymaker.net/wp-login.php?action=lostpassword', '_blank', 'noopener');
      });
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const username = clean(card.querySelector('[data-register-username]')?.value);
      const email = clean(card.querySelector('[data-register-email]')?.value);
      const message = card.querySelector('[data-register-message]');
      const button = card.querySelector('[data-register-submit]');

      message.innerHTML = '';
      if (!username) {
        message.innerHTML = messageHtml('error', '사용자명을 입력해 주세요.');
        return;
      }
      if (!email || !/^\S+@\S+\.\S+$/.test(email)) {
        message.innerHTML = messageHtml('error', '올바른 이메일 주소를 입력해 주세요.');
        return;
      }

      button.disabled = true;
      button.textContent = '가입 메일 요청 중...';
      try {
        const response = await fetch(API_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, email })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.ok === false) {
          const rawMessage = String(data.message || data.detail || data.code || '회원가입 처리에 실패했습니다.');
          const lowered = rawMessage.toLowerCase();
          if (lowered.includes('already') || lowered.includes('registered') || lowered.includes('existing_user_email') || lowered.includes('email_exists') || rawMessage.includes('이미 등록')) {
            throw new Error('이 이메일 주소는 이미 등록돼 있습니다. 로그인하거나 다른 이메일을 사용해 주세요.');
          }
          if (lowered.includes('existing_user_login') || lowered.includes('username_exists') || rawMessage.includes('사용자명') && rawMessage.includes('존재')) {
            throw new Error('이미 사용 중인 사용자명입니다. 다른 사용자명을 입력해 주세요.');
          }
          throw new Error(rawMessage);
        }

        form.innerHTML = `
          <div style="padding:10px 0 4px;text-align:center;">
            <div style="font-size:42px;line-height:1;margin-bottom:14px;">✓</div>
            <strong style="display:block;color:#f8fafc;font-size:20px;margin-bottom:10px;">가입 안내 메일을 보냈습니다.</strong>
            <p style="margin:0;color:#94a3b8;font-size:14px;line-height:1.7;">${email}<br>메일에서 비밀번호 설정 링크를 눌러 가입을 완료해 주세요.</p>
          </div>
        `;
      } catch (error) {
        const errorMessage = error?.message || '회원가입 처리에 실패했습니다.';
        message.innerHTML = messageHtml('error', errorMessage);
        button.disabled = false;
        button.textContent = '가입 안내 메일 받기';

        if (errorMessage.includes('이메일 주소는 이미 등록') || errorMessage.includes('existing_user_email')) {
          const emailInput = card.querySelector('[data-register-email]');
          if (emailInput) {
            emailInput.value = '';
            requestAnimationFrame(() => {
              emailInput.focus();
              if (typeof emailInput.animate === 'function') {
                emailInput.animate([
                  { borderColor: 'rgba(148,163,184,.30)', boxShadow: '0 0 0 0 rgba(77,219,243,0)' },
                  { borderColor: 'rgba(77,219,243,.95)', boxShadow: '0 0 0 7px rgba(77,219,243,.20)' },
                  { borderColor: 'rgba(77,219,243,.65)', boxShadow: '0 0 0 0 rgba(77,219,243,0)' }
                ], {
                  duration: 900,
                  iterations: 2,
                  easing: 'ease-out'
                });
              }
            });
          }
        }
      }
    });
  }

  function apply() {
    const card = findRegisterCard();
    if (card) renderRegisterForm(card);
  }

  const observer = new MutationObserver(() => apply());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener('click', () => setTimeout(apply, 0), true);
  apply();

  console.info('[StoryMaker V2] inline register bridge active');
})();
