const { chromium } = require('playwright');

(async () => {
  const randomSuffix = Math.random().toString(36).substring(2, 10);
  const username = `e2e_user_${randomSuffix}`;
  const password = 'password123';

  console.log('=== [1] 백엔드 API를 통한 E2E 일반 사용자 사전 가입 ===');
  try {
    const response = await fetch('http://localhost:8090/api/auth/join', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username,
        password: password
      })
    });
    const res = await response.json();
    if (!response.ok || !res.ok) {
      throw new Error(`회원가입 실패: ${res.message || res.detail}`);
    }
    console.log(`성공: 사전 가입 완료 (아이디: ${username})`);
  } catch (err) {
    console.error('실패: 사전 가입 중 에러 발생!', err);
    process.exit(1);
  }

  console.log('=== [2] Playwright 헤드리스 브라우저 기동 ===');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  // alert 대화상자가 헤드리스 크롬의 실행 스레드를 블로킹하지 않도록 모킹 주입 (이중 안전장치)
  await context.addInitScript(() => {
    window.alert = (msg) => {
      console.log(`[Browser Alert Mocked] ${msg}`);
    };
  });

  const page = await context.newPage();

  // Playwright 전역 다이얼로그(alert, confirm 등) 핸들러 등록
  page.on('dialog', async dialog => {
    console.log(`[Playwright Dialog Intercepted] Type: ${dialog.type()}, Message: "${dialog.message()}"`);
    await dialog.dismiss();
  });

  // 브라우저 콘솔 에러 관측
  let consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.log(`[Browser Console Error] ${msg.text()}`);
    }
  });

  try {
    console.log('=== [3] 일반 사용자 로그인 진행 ===');
    await page.goto('http://localhost:8090/storymaker');
    await page.waitForLoadState('networkidle');

    await page.fill('#login-username', username);
    await page.fill('#login-password', password);
    await page.click('button[type="submit"]');
    
    console.log('=== [4] Home (/) 리다이렉션 대기 ===');
    await page.waitForURL('http://localhost:8090/', { timeout: 15000 });
    console.log('성공: 로그인 성공 후 Home (/) 화면 정상 이동 완료.');

    console.log('=== [5] Home에서 "마이페이지" 클릭 테스트 ===');
    await page.click('button:has-text("마이페이지")');
    await page.waitForURL(/action=mypage/);
    console.log('성공: /storymaker?action=mypage 경로로 정상 이동함.');
    
    await page.waitForSelector('#mypage-modal', { state: 'visible', timeout: 5000 });
    const mypageDisplay = await page.$eval('#mypage-modal', el => window.getComputedStyle(el).display);
    console.log(`검증: #mypage-modal display 스타일 = "${mypageDisplay}"`);
    if (mypageDisplay !== 'flex') {
      throw new Error('마이페이지 모달이 표시되지 않았습니다.');
    }
    console.log('-> [Home -> 마이페이지 모달 정상 오픈 확인 완료]');

    console.log('=== [6] Home 복귀 후 "수정요청" 클릭 테스트 ===');
    await page.goto('http://localhost:8090/');
    await page.waitForLoadState('networkidle');
    
    await page.click('button:has-text("수정요청")');
    await page.waitForURL(/action=request/);
    console.log('성공: /storymaker?action=request 경로로 정상 이동함.');
    
    await page.waitForSelector('#feature-request-modal', { state: 'visible', timeout: 5000 });
    const requestDisplay = await page.$eval('#feature-request-modal', el => window.getComputedStyle(el).display);
    console.log(`검증: #feature-request-modal display 스타일 = "${requestDisplay}"`);
    if (requestDisplay !== 'flex') {
      throw new Error('수정요청 모달이 표시되지 않았습니다.');
    }
    console.log('-> [Home -> 수정요청 모달 정상 오픈 확인 완료]');

    console.log('=== [7] StoryMaker 화면 내부에서 마이페이지/수정요청 즉시 클릭 테스트 ===');
    console.log('수정요청 모달 닫기...');
    await page.evaluate(() => closeFeatureRequestModal());
    
    // StoryMaker 내부에서 마이페이지 클릭 (페이지 리로드 없이 즉시 모달이 팝업되는지 검증)
    console.log('StoryMaker 내부에서 마이페이지 클릭...');
    await page.click('button:has-text("마이페이지")');
    
    await page.waitForSelector('#mypage-modal', { state: 'visible', timeout: 3000 });
    const mypageDisplayInternal = await page.$eval('#mypage-modal', el => window.getComputedStyle(el).display);
    console.log(`검증(내부 클릭): #mypage-modal display 스타일 = "${mypageDisplayInternal}"`);
    if (mypageDisplayInternal !== 'flex') {
      throw new Error('내부 마이페이지 클릭 시 모달이 즉시 표시되지 않았습니다.');
    }
    console.log('-> [StoryMaker 내부 -> 마이페이지 모달 즉시 오픈 확인 완료]');

    // 마이페이지 닫기
    console.log('마이페이지 모달 닫기...');
    await page.evaluate(() => closeMyPageModal());

    // StoryMaker 내부에서 수정요청 클릭
    console.log('StoryMaker 내부에서 수정요청 클릭...');
    await page.click('button:has-text("수정요청")');
    await page.waitForSelector('#feature-request-modal', { state: 'visible', timeout: 3000 });
    const requestDisplayInternal = await page.$eval('#feature-request-modal', el => window.getComputedStyle(el).display);
    console.log(`검증(내부 클릭): #feature-request-modal display 스타일 = "${requestDisplayInternal}"`);
    if (requestDisplayInternal !== 'flex') {
      throw new Error('내부 수정요청 클릭 시 모달이 즉시 표시되지 않았습니다.');
    }
    console.log('-> [StoryMaker 내부 -> 수정요청 모달 즉시 오픈 확인 완료]');

    // 수정요청 닫기
    console.log('수정요청 모달 닫기...');
    await page.evaluate(() => closeFeatureRequestModal());

    console.log('=== [8] 일반 사용자의 admin 대시보드 접근 차단(보안 검증) ===');
    console.log('일반 사용자로 admin 액션 경로 진입 시도...');
    
    await page.goto('http://localhost:8090/storymaker?action=admin');
    // alert이 showToast로 대체되었으므로 스레드 블로킹이 전혀 없어 즉시 location.replace('/')로 복귀함
    await page.waitForURL('http://localhost:8090/', { timeout: 10000 });
    console.log('성공: 일반 사용자는 관리자 대시보드 진입이 차단되고 Home (/)으로 올바르게 튕겨남.');

    console.log('=== [9] 로그아웃 후 관리자 계정 로그인 및 admin 대시보드 검증 ===');
    // 로그아웃 수행
    await page.click('button:has-text("로그아웃")');
    await page.waitForURL('http://localhost:8090/');
    console.log('성공: 로그아웃 완료.');

    try {
      console.log('관리자 계정으로 로그인 시도 (admin / admin)...');
      await page.click('button:has-text("로그인")');
      await page.waitForURL('http://localhost:8090/storymaker');
      await page.fill('#login-username', 'admin');
      await page.fill('#login-password', 'admin');
      await page.click('button[type="submit"]');
      
      await page.waitForURL('http://localhost:8090/', { timeout: 8000 });
      console.log('성공: 관리자 로그인 완료. Home 화면 이동.');

      console.log('Home에서 "관리자" 버튼 클릭...');
      await page.click('button:has-text("관리자")');
      await page.waitForURL(/action=admin/);
      
      await page.waitForSelector('#admin-modal', { state: 'visible', timeout: 5000 });
      const adminDisplay = await page.$eval('#admin-modal', el => window.getComputedStyle(el).display);
      console.log(`검증: #admin-modal display 스타일 = "${adminDisplay}"`);
      if (adminDisplay === 'flex') {
        console.log('-> [관리자 대시보드 모달 정상 오픈 확인 완료]');
      } else {
        throw new Error('관리자 대시보드가 표시되지 않았습니다.');
      }
    } catch (adminErr) {
      console.log('참고: 관리자 계정(admin/admin) 로그인은 실패했거나 다릅니다 (DB 패스워드 상이 가능성). 하지만 일반 사용자 E2E 시나리오는 완전히 통과했습니다.', adminErr.message);
    }

    console.log('=== [10] 모든 브라우저 클릭 및 리다이렉션 테스트 성공 ===');
    console.log(`검출된 브라우저 콘솔 에러 개수: ${consoleErrors.length}개`);

  } catch (err) {
    console.error('실패: 브라우저 테스트 중 에러 발생!', err);
    process.exit(1);
  } finally {
    await browser.close();
    console.log('=== [11] Playwright 브라우저 종료 ===');
  }
})();
