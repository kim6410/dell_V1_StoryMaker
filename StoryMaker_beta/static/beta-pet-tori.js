(() => {
  'use strict';
  if (window.__STORYMAKER_BETA_PET_TORI__) return;
  window.__STORYMAKER_BETA_PET_TORI__ = true;

  const style = document.createElement('style');
  style.id = 'storymaker-beta-pet-tori-style';
  style.textContent = `
    .sm-tori-wrap{position:fixed;left:22px;right:auto;bottom:36px;z-index:2147483000;width:150px;height:116px;pointer-events:none;user-select:none;isolation:isolate;filter:drop-shadow(0 12px 18px rgba(0,0,0,.28))}
    .sm-tori-bubble{position:absolute;right:5px;bottom:91px;max-width:190px;padding:8px 11px;border-radius:14px;background:rgba(255,255,255,.96);color:#17304f;font-size:12px;font-weight:900;line-height:1.4;white-space:nowrap;opacity:0;transform:translateY(8px);transition:.24s ease;box-shadow:0 10px 25px rgba(0,0,0,.18)}
    .sm-tori-bubble.show{opacity:1;transform:translateY(0)}
    .sm-tori-bubble:after{content:"";position:absolute;right:24px;bottom:-7px;width:14px;height:14px;background:inherit;transform:rotate(45deg);border-radius:3px}
    .sm-tori-stage{position:absolute;right:0;bottom:0;width:110px;height:84px;pointer-events:auto;cursor:pointer;animation:smToriFloat 4s ease-in-out infinite}
    .sm-tori-stage.jump{animation:smToriJump .85s ease}
    .sm-tori-shadow{position:absolute;right:18px;bottom:2px;width:62px;height:10px;border-radius:50%;background:rgba(0,0,0,.2);filter:blur(2px)}
    .sm-tori-body{position:absolute;right:20px;bottom:8px;width:62px;height:42px;border-radius:28px 28px 23px 23px;background:linear-gradient(160deg,#fffaf4 0%,#f1d8bd 66%,#d8a876 100%);border:2px solid rgba(86,59,37,.16)}
    .sm-tori-head{position:absolute;right:35px;bottom:36px;width:43px;height:38px;border-radius:48% 48% 46% 46%;background:linear-gradient(160deg,#fffdf8,#efd4b6);border:2px solid rgba(86,59,37,.16)}
    .sm-tori-ear{position:absolute;top:-10px;width:14px;height:17px;background:#efd4b6;border:2px solid rgba(86,59,37,.16);border-bottom:0;border-radius:5px 8px 0 0}
    .sm-tori-ear.left{left:4px;transform:rotate(-18deg)}.sm-tori-ear.right{right:4px;transform:rotate(18deg)}
    .sm-tori-ear:after{content:"";position:absolute;inset:4px 3px 1px;background:#f5aeb8;border-radius:4px 4px 0 0}
    .sm-tori-eye{position:absolute;top:15px;width:5px;height:7px;border-radius:50%;background:#243042;animation:smToriBlink 5.4s infinite}.sm-tori-eye.left{left:11px}.sm-tori-eye.right{right:11px}
    .sm-tori-nose{position:absolute;left:50%;top:21px;width:8px;height:6px;border-radius:50% 50% 62% 62%;background:#ef8e9e;transform:translateX(-50%)}
    .sm-tori-mouth:before,.sm-tori-mouth:after{content:"";position:absolute;top:27px;width:7px;height:5px;border-bottom:2px solid #775844;border-radius:0 0 8px 8px}.sm-tori-mouth:before{left:14px}.sm-tori-mouth:after{right:14px}
    .sm-tori-tail{position:absolute;right:-18px;bottom:21px;width:37px;height:23px;border-top:8px solid #d6a16f;border-radius:50%;transform-origin:left center;animation:smToriTail 1.9s ease-in-out infinite}
    .sm-tori-paw{position:absolute;bottom:-3px;width:13px;height:7px;border-radius:50%;background:#fff7ef}.sm-tori-paw.a{left:9px}.sm-tori-paw.b{left:25px}.sm-tori-paw.c{right:24px}.sm-tori-paw.d{right:8px}
    .sm-tori-name{position:absolute;right:27px;bottom:-14px;padding:2px 8px;border-radius:999px;background:rgba(8,22,42,.82);border:1px solid rgba(117,237,206,.3);color:#9ff7df;font-size:10px;font-weight:950;letter-spacing:.08em}
    @keyframes smToriFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
    @keyframes smToriJump{0%,100%{transform:translateY(0)}35%{transform:translateY(-21px) rotate(-2deg)}70%{transform:translateY(0) scale(.97)}}
    @keyframes smToriTail{0%,100%{transform:rotate(5deg)}50%{transform:rotate(24deg)}}
    @keyframes smToriBlink{0%,44%,47%,100%{transform:scaleY(1)}45%,46%{transform:scaleY(.12)}}
    @media(max-width:820px){.sm-tori-wrap{left:10px;right:auto;bottom:22px;transform:scale(.82);transform-origin:left bottom}}
    @media(prefers-reduced-motion:reduce){.sm-tori-stage,.sm-tori-eye,.sm-tori-tail{animation:none!important}}
  `;
  document.head.appendChild(style);

  const root = document.createElement('div');
  root.className = 'sm-tori-wrap';
  root.setAttribute('aria-label', '스토리메이커 고양이 토리');
  root.innerHTML = `
    <div class="sm-tori-bubble">토리가 응원할게.</div>
    <div class="sm-tori-stage" role="button" tabindex="0" aria-label="토리와 인사하기">
      <div class="sm-tori-shadow"></div>
      <div class="sm-tori-body"><div class="sm-tori-tail"></div><i class="sm-tori-paw a"></i><i class="sm-tori-paw b"></i><i class="sm-tori-paw c"></i><i class="sm-tori-paw d"></i></div>
      <div class="sm-tori-head"><i class="sm-tori-ear left"></i><i class="sm-tori-ear right"></i><i class="sm-tori-eye left"></i><i class="sm-tori-eye right"></i><i class="sm-tori-nose"></i><i class="sm-tori-mouth"></i></div>
      <div class="sm-tori-name">TORI · 토리</div>
    </div>`;
  document.body.appendChild(root);

  const stage = root.querySelector('.sm-tori-stage');
  const bubble = root.querySelector('.sm-tori-bubble');
  let bubbleTimer = 0;
  let lastState = '';

  function speak(message, duration = 2300) {
    bubble.textContent = message;
    bubble.classList.add('show');
    window.clearTimeout(bubbleTimer);
    bubbleTimer = window.setTimeout(() => bubble.classList.remove('show'), duration);
  }

  function jump() {
    stage.classList.remove('jump');
    void stage.offsetWidth;
    stage.classList.add('jump');
  }

  function react() {
    const text = document.body?.innerText || '';
    let state = 'idle';
    if (/실패|오류|에러/.test(text)) state = 'error';
    else if (/완료|저장 완료|제작 완료/.test(text)) state = 'done';
    else if (/생성 중|진행 중|렌더|MP3|MP4|TTS/.test(text)) state = 'working';
    if (state === lastState) return;
    lastState = state;
    if (state === 'done') { speak('토리도 신난다. 완성!', 2600); jump(); }
    else if (state === 'error') speak('괜찮아. 토리랑 다시 보자.', 2600);
    else if (state === 'working') speak('토리가 옆에서 지켜보는 중.', 2200);
  }

  function greet() { speak('안녕, 나는 토리야.', 2300); jump(); }
  stage.addEventListener('click', greet);
  stage.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); greet(); } });

  window.setTimeout(() => speak('안녕, 나는 토리야.', 2600), 500);
  window.setInterval(react, 1400);
})();
