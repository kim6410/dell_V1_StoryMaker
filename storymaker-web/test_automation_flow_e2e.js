const { chromium } = require('playwright');

(async () => {
  console.log('===================================================');
  console.log('StoryMaker 자동화 파이프라인 E2E 테스트 시작');
  console.log('===================================================');

  const testPromptText = `StoryMaker 생성 환경
프롬프트 버전: StoryMaker Prompt v3.0
브랜드명: 오박사만능인테리어
대표 전화번호: 010-8284-5584
지역명: 울산 신정동
글쓰기 스타일: 스토리형
스타일 지침: 따뜻하고 전문적인 어조로 설명해 주세요.

[BLOCK:BLOG_POST]
울산 신정동 욕실 리모델링 관련 프롬프트입니다.
`;

  // 1. 임의 사용자 생성 및 가입
  const randomSuffix = Math.random().toString(36).substring(2, 10);
  const username = `test_auto_user_${randomSuffix}`;
  const password = 'password123';

  console.log(`[1] 백엔드에 테스트용 임시 사용자 가입 요청 (${username})...`);
  try {
    let response = await fetch('http://localhost:8090/api/auth/join', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username,
        password: password,
        invite_code: 'storymaker2026'
      })
    });
    let res = await response.json();
    if (!response.ok || !res.ok) {
      throw new Error(`회원가입 실패: ${res.message || res.detail}`);
    }
    console.log(`-> 사용자 가입 성공.`);

    // 2. 테스트용 프롬프트를 백엔드에 미리 스냅샷으로 저장
    console.log('[2] 백엔드에 테스트용 프롬프트 스냅샷 미리 저장 (/api/test/prompt-snapshot)...');
    response = await fetch('http://localhost:8090/api/test/prompt-snapshot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        generated_prompt: testPromptText,
        project_title: 'E2E 테스트 프로젝트',
        payload: {}
      })
    });
    res = await response.json();
    if (!response.ok || !res.ok) {
      throw new Error(`프롬프트 스냅샷 저장 실패: ${res.message}`);
    }
    console.log(`-> 프롬프트 스냅샷 저장 완료 (latest_prompt.md 생성 완료).`);

  } catch (err) {
    console.error('사전 세팅 중 오류 발생:', err);
    process.exit(1);
  }

  // 3. Playwright 브라우저 기동
  console.log('[3] Playwright 브라우저 기동 (헤드리스)...');
  const browser = await chromium.launch({ headless: true });
  
  // 두 개의 별도 페이지(컨텍스트) 생성하여 동시 실행
  const contextA = await browser.newContext();
  await contextA.addInitScript(() => {
    window.alert = (msg) => console.log(`[Alert Mocked A] ${msg}`);
  });
  const pageA = await contextA.newPage();

  const contextB = await browser.newContext();
  await contextB.addInitScript(() => {
    window.alert = (msg) => console.log(`[Alert Mocked B] ${msg}`);
  });
  const pageB = await contextB.newPage();

  // Dialog dismiss 등록
  pageA.on('dialog', async d => await d.dismiss());
  pageB.on('dialog', async d => await d.dismiss());

  // 콘솔 및 에러 모니터링
  pageA.on('pageerror', exc => console.error('[PageA Error]', exc.toString()));
  pageB.on('pageerror', exc => console.error('[PageB Error]', exc.toString()));
  
  // StoryMaker 화면 디버그 로그 출력
  pageA.on('console', msg => {
    console.log(`[PageA Console] [${msg.type()}] ${msg.text()}`);
  });

  // Mock GPT 화면 디버그 로그 출력
  pageB.on('console', msg => {
    if (msg.text().includes('[MockGPT]') || msg.text().includes('[API]') || msg.text().includes('[오류]')) {
      console.log(`[Worker Console] ${msg.text()}`);
    }
  });

  try {
    // 4. PageA에서 로그인 진행 및 /storymaker-test 진입
    console.log('[4] PageA: StoryMaker 로그인 진행 중...');
    await pageA.goto('http://localhost:8090/storymaker');
    await pageA.waitForLoadState('networkidle');
    await pageA.fill('#login-username', username);
    await pageA.fill('#login-password', password);
    await pageA.click('button[type="submit"]');

    console.log('-> Home 리다이렉션 대기...');
    await pageA.waitForURL('http://localhost:8090/', { timeout: 15000 });
    console.log('-> 로그인 성공.');

    console.log('[5] PageA: /storymaker-test 화면으로 진입...');
    await pageA.goto('http://localhost:8090/storymaker-test?e2e=1');
    await pageA.waitForLoadState('networkidle');
    console.log('-> /storymaker-test 화면 로드 완료.');

    // 5. PageB에서 Mock ChatGPT 워커 기동
    console.log('[6] PageB: Mock ChatGPT 자동화 워커(시뮬레이터) 로드 중...');
    await pageB.goto('http://localhost:8090/static/mock-chatgpt.html?automate=1');
    await pageB.waitForLoadState('networkidle');
    console.log('-> Mock ChatGPT 자동화 워커 로드 및 폴링 시작 완료.');

    // 6. PageA의 iframe에 프롬프트 텍스트 주입하여 플레이스홀더 우회
    console.log('[7] PageA: iframe 내부 #generated-prompt-box 에 테스트 프롬프트 주입...');
    const iframeElement = await pageA.waitForSelector('#storymaker-test-frame', { timeout: 10000 });
    const frame = await iframeElement.contentFrame();
    if (!frame) {
      throw new Error('storymaker-test-frame contentFrame을 가져올 수 없습니다.');
    }

    // iframe이 준비되고 브리지가 박스를 잡을 수 있도록 여유 시간을 둠
    await frame.waitForSelector('#generated-prompt-box', { timeout: 10000 });
    await frame.evaluate((text) => {
      const box = document.getElementById('generated-prompt-box');
      if (box) {
        box.innerText = text;
        box.style.color = '#ffffff'; // 플레이스홀더 색상이 아닌 본문 색상으로 변경
      }
    }, testPromptText);
    console.log('-> 프롬프트 주입 완료.');

    // 7. "자동으로 AI 결과 만들기" 버튼 클릭
    await frame.waitForSelector('#btn-auto-generate', { timeout: 10000 });
    console.log('-> "자동으로 AI 결과 만들기" 버튼 클릭!');
    await frame.click('#btn-auto-generate');

    // 8. 결과 반영 대기 및 검증 (약 15초 대기)
    console.log('[8] E2E 파이프라인 진행 대기 및 최종 AI 결과 바인딩 관측 중...');
    console.log('-> 15초 동안 자동화 동작 완료를 기다립니다...');
    await pageA.waitForTimeout(15000);

    // PageA의 iframe 내부에서 결과 탭(예: "블로그")이 정상적으로 보이고 비어있지 않은지 검증
    console.log('[9] 최종 결과 검증 중 (블로그 탭 비동기 렌더링 대기)...');
    
    try {
      // 비동기 파싱 완료 및 탭 렌더링을 최대 10초 대기
      await frame.waitForSelector('button:has-text("블로그")', { timeout: 10000 });
    } catch (e) {
      console.log('-> 경고: 블로그 탭 대기 타임아웃 발생, 강제 체크 진행합니다.');
    }

    const isBlogTabVisible = await frame.isVisible('button:has-text("블로그")');
    console.log(`-> 블로그 탭 표시 여부: ${isBlogTabVisible}`);

    if (!isBlogTabVisible) {
      throw new Error('E2E 자동 생성 실패: 블로그 결과 탭이 보이지 않습니다.');
    }

    // 블로그 탭 클릭하여 결과 데이터 검증
    await frame.click('button:has-text("블로그")');
    await frame.waitForTimeout(1000);
    
    const blogTextVal = await frame.$eval('#text-BLOG', el => el.value || el.innerText || '');
    console.log(`-> 검증된 블로그 결과 텍스트 길이: ${blogTextVal.length} 자`);

    if (!blogTextVal || blogTextVal.trim() === '' || !blogTextVal.includes('욕실 리모델링')) {
      throw new Error('파싱된 블로그 결과 본문이 비어 있거나 정상 파싱되지 않았습니다.');
    }

    console.log('===================================================');
    console.log('SUCCESS: StoryMaker E2E 테스트 자동화 파이프라인 검증 성공!');
    console.log('===================================================');

  } catch (err) {
    console.error('===================================================');
    console.error('FAILURE: E2E 테스트 중 에러 발생!', err.message);
    console.error('===================================================');
    
    try {
      const artifactDir = '/home/bourne/.gemini/antigravity-cli/brain/f5abe6db-b54d-4a63-a9af-9be6b360bfaa';
      const screenshotPath = `${artifactDir}/error_screenshot.png`;
      await pageA.screenshot({ path: screenshotPath, fullPage: true });
      console.log(`-> [디버그] 에러 스크린샷이 아티팩트로 저장되었습니다: ${screenshotPath}`);
    } catch (ssErr) {
      console.error('스크린샷 획득 실패:', ssErr.message);
    }
    
    process.exit(1);
  } finally {
    await browser.close();
    console.log('[10] Playwright 브라우저 종료 및 리소스 정리.');
  }
})();
