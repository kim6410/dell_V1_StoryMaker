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
        password: password,
        invite_code: 'storymaker2026'
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

  // alert 대화상자가 헤드리스 크롬의 실행 스레드를 블로킹하지 않도록 모킹 주입
  await context.addInitScript(() => {
    window.alert = (msg) => {
      console.log(`[Browser Alert Mocked] ${msg}`);
    };
  });

  const page = await context.newPage();

  // Playwright 전역 다이얼로그 핸들러 등록
  page.on('dialog', async dialog => {
    console.log(`[Playwright Dialog Intercepted] Type: ${dialog.type()}, Message: "${dialog.message()}"`);
    await dialog.dismiss();
  });

  // 브라우저 콘솔 에러 관측
  let consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      const txt = msg.text();
      if (txt.includes('GSI_LOGGER') || txt.includes('accounts.google.com') || txt.includes('403')) {
        console.log(`[Browser Console Error Ignored] ${txt}`);
        return;
      }
      consoleErrors.push(txt);
      console.log(`[Browser Console Error] ${txt}`);
    }
  });

  // 페이지 스크립트 에러 관측
  page.on('pageerror', exception => {
    const txt = exception.toString();
    if (txt.includes('GSI_LOGGER') || txt.includes('accounts.google.com') || txt.includes('403')) {
      console.log(`[Browser PageError Ignored] ${txt}`);
      return;
    }
    consoleErrors.push(txt);
    console.error(`[Browser PageError] ${txt}`);
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
    console.log('성공: 로그인 완료 후 Home으로 정상 이동.');

    console.log('=== [5] 리다이렉션 정착 대기 (3초) 후 내비게이션 바 링크 클릭으로 StoryMaker 진입 ===');
    await page.waitForTimeout(3000);
    await page.waitForSelector('.sns-ai-app-menu a[href="/storymaker"]', { timeout: 5000 });
    await page.click('.sns-ai-app-menu a[href="/storymaker"]');
    await page.waitForLoadState('networkidle');

    console.log('=== [6] 14개 채널 블록 데이터 주입 ===');
    const testInputData = `
[BLOCK:BLOG_TITLES]
1. 네이버 스마트플레이스 검색 노출을 높이는 지역 매장 홍보 전략
2. 울산 신정동 욕실 리모델링 완벽 가이드
3. 마케팅 성공을 위한 SNS AI 콘텐츠 최적화 기법
4. 소상공인을 위한 네이버 플레이스 세팅 요령
5. 욕실 리모델링 전 꼭 확인해야 할 5가지 체크리스트

[BLOCK:BLOG_POST]
# 네이버 스마트플레이스 검색 노출을 높이는 지역 매장 홍보 전략

## 도입부
지역 매장은 고객이 검색하는 순간 발견되어야 합니다. **네이버 스마트플레이스 노출**은 매장의 매출과 직결되는 매우 중요한 첫인상입니다.

## 문제 상황
많은 소상공인분들이 스마트플레이스를 개설만 해두고 방치하고 계십니다. 정보가 누락되어 있거나 키워드가 최적화되지 않아 검색 결과에서 뒤로 밀려나는 아픔을 겪습니다.

## 해결 방법
스마트플레이스 기본 정보인 상호명, 주소, 연락처뿐만 아니라 메뉴 설명과 매장 소개글에 지역명과 업종 핵심 키워드를 자연스럽게 스며들게 배치해야 합니다.

[핵심] 정보의 정확성과 최신의 관리 상태가 최적화의 첫걸음입니다.

## StoryMaker 활용 방법
StoryMaker를 이용하면 내 매장의 특징과 타겟 고객의 키워드를 분석하여 검색에 친화적인 소개 문구와 블로그 콘텐츠를 1초 만에 뚝딱 생성할 수 있습니다.

[실무 팁] 오배송 예방 팁과 마찬가지로 플레이스에서도 주소와 예약 링크의 정확성을 매주 1회 정기 검수하십시오.

## 마무리
지금 바로 스마트플레이스 설정을 점검하고 AI 콘텐츠를 활용하여 매장의 온라인 영토를 확장해 보세요!

[BLOCK:CARROT_TITLES]
1. 신정동 우리 동네 욕실 리모델링 꼼꼼하게 잘하는 곳!
2. 욕실 누수 걱정 끝, 동네 단골 매장과 상의하세요
3. 욕실 인테리어 고민? 무료 견적 상담 받아보세요
4. 우리 집 화장실의 변신, 지역 전문 시공팀이 나섭니다
5. 깔끔한 욕실 수리, 가까운 이웃 매장이 정답입니다

[BLOCK:CARROT_POST]
안녕하세요! 우리 동네 욕실 전문 시공 매장입니다.
화장실 타일이 깨지거나 변기 물이 새서 고민이셨나요?
멀리서 찾지 마시고 동네에서 믿고 맡길 수 있는 이웃 매장과 상의하세요.
친절한 상담 and 꼼꼼한 시공으로 보답하겠습니다.
언제든 채팅으로 문의 남겨주시면 정성껏 답변해 드릴게요!

[BLOCK:PODCAST_50]
#F1
여러분, 화장실 갈 때마다 왠지 모르게 찌뿌둥하고 고쳐야지 마음먹은 적 많으시죠?
#M1
맞습니다. 욕실은 매일 쓰는 공간이라 작은 하자도 엄청 신경 쓰이죠.
#F1
동네 이웃 매장에서 친절하게 수리해 드리니 부담 없이 문의해보세요!

[BLOCK:PODCAST_80]
#F1
우리 집 화장실, 리모델링하고는 싶은데 비용도 걱정되고 믿을 만한 업체를 찾기 어려우셨죠?
#M1
그 마음 잘 압니다. 그래서 저희는 과잉 시공 없이 꼭 필요한 부분만 정직하게 권해드립니다.
#F2
정말요? 동네 매장이라 사후 관리도 확실하겠네요!
#M1
그럼요. 무상 A/S 기간 보증은 물론이고 24시간 언제든 동네 골목 대기 중입니다!

[BLOCK:INSTAGRAM_POST]
매일 마주하는 욕실, 이제는 힐링 공간으로 변신할 때! ✨
동네에서 가장 꼼꼼하게 시공하는 욕실 리모델링 전문팀입니다.
타일 선정부터 세면대 수전 하나까지 고객님의 취향에 맞춤 시공해 드려요.
합리적인 가격과 믿을 수 있는 사후 관리를 약속드립니다.
지금 인스타 DM 또는 프로필 링크로 문의하세요!

[BLOCK:INSTAGRAM_HASHTAGS]
#욕실리모델링 #화장실인테리어 #동네인테리어 #욕실인테리어 #수리전문 #인테리어그램 #맞춤시공 #무료견적 #정직한시공 #힐링공간

[BLOCK:CAROUSEL_7]
## 1. 꼬이고 낡은 욕실의 경고
---
## 2. 겉만 번지르르한 날림 공사는 그만
---
## 3. 우리 가족이 안심하고 쓰는 공간으로
---
## 4. 라이프스타일에 맞춘 타일과 수전 레이아웃
---
## 5. 정직한 견적과 약속된 시공 기일 준수
---
## 6. 철저한 방수 테스트와 깔끔한 마무리
---
## 7. 지금 바로 무료 욕실 상담 예약하세요!

[BLOCK:NAVER_PLACE_NEWS]
신정동 이웃 여러분! 저희 매장이 여름맞이 욕실 부분 리모델링 및 수전 교체 특별 할인 이벤트를 진행합니다.
멀리 갈 필요 없이 동네 골목에서 빠르게 소통하며 A/S 걱정 없는 정직한 시공을 약속드립니다.
자세한 소식은 플레이스 예약 페이지를 참고해 주세요!

[BLOCK:GOOGLE_BUSINESS_POST]
신정동 지역 욕실 리모델링 및 타일 수리 시공 전문 매장입니다.
신뢰할 수 있는 기술력과 정직한 견적으로 최적의 화장실 솔루션을 제공합니다.
운영 시간은 24시간 연중무휴이며 전화 상담 및 무료 출장 견적 지원합니다.

[BLOCK:BLOG_HASHTAGS]
#네이버플레이스노출 #스마트플레이스노출 #욕실리모델링 #화장실수리 #신정동인테리어 #지역매장마케팅

[BLOCK:CARROT_HASHTAGS]
#욕실리모델링 #동네수리 #화장실인테리어 #친절한상담

[BLOCK:WORDPRESS_SEO]
- WordPress 제목: 네이버 스마트플레이스 검색 노출을 높이는 지역 매장 홍보 전략
- Slug: naver-place-seo
- 포커스 키워드: 네이버 스마트플레이스 노출
- SEO 제목: 네이버 스마트플레이스 노출 전략 | SNS AI Studio
- 메타 설명: 네이버 스마트플레이스 노출을 높이기 위해 지역 매장이 확인해야 할 검색 최적화 요소와 AI 콘텐츠 활용 방법을 정리했습니다.
- 카테고리: AI 활용 가이드, 네이버 플레이스
- 태그: 네이버 스마트플레이스, 지역 마케팅, 소상공인 홍보, AI 콘텐츠, 검색 노출
- 대표 이미지 ALT: 네이버 스마트플레이스 노출 전략을 설명하는 지역 매장 마케팅 이미지
- OG 제목: 네이버 스마트플레이스 노출 전략
- OG 설명: 지역 매장이 네이버 검색에서 더 잘 발견되도록 만드는 스마트플레이스 콘텐츠 최적화 방법
- 본문 HTML:
<h2>네이버 스마트플레이스 노출이 중요한 이유</h2>
<p>지역 매장은 고객이 검색하는 순간 발견되어야 합니다. 네이버 스마트플레이스는 매장명, 지역명, 업종명, 리뷰, 사진, 소개 문구가 함께 노출되는 중요한 접점입니다.</p>

<h2>지역 매장이 먼저 점검해야 할 요소</h2>
<p>상호명, 주소, 영업시간, 전화번호, 대표 사진, 메뉴 또는 서비스 설명이 정확하게 입력되어 있어야 합니다.</p>

<h2>실행 체크리스트</h2>
<ul>
  <li>스마트플레이스 기본 정보가 최신 상태인지 확인합니다.</li>
  <li>지역명과 업종명이 자연스럽게 들어간 소개 문구를 작성합니다.</li>
</ul>

<h2>FAQ</h2>
<h3>네이버 스마트플레이스 노출은 블로그와도 관련이 있나요?</h3>
<p>직접적인 순위 요소로 단정하기는 어렵지만, 블로그와 스마트플레이스가 함께 운영되면 고객이 매장을 확인하는 접점이 늘어납니다.</p>
`;

    await page.fill('#chatgpt-raw-input', testInputData);

    console.log('=== [7] "SNS별 분리" 버튼 클릭 및 대기 ===');
    await page.click('button:has-text("SNS별 분리")');
    await page.waitForTimeout(5000); // 렌더링이 완료되길 5초 대기

    console.log('=== [8] 결과 탭 확인 및 WordPress SEO 검증 ===');
    const isWpTabVisible = await page.isVisible('button:has-text("WordPress SEO")');
    console.log(`WordPress SEO 탭 노출 검증 = ${isWpTabVisible}`);
    
    if (!isWpTabVisible) {
      throw new Error('WordPress SEO 결과 탭이 화면에 노출되지 않았습니다!');
    }

    // WordPress SEO 탭 클릭
    await page.click('button:has-text("WordPress SEO")');
    console.log('WordPress SEO 탭 클릭 및 데이터 확인 중...');
    
    await page.waitForSelector('#wp-title', { timeout: 3000 });
    const wpTitleText = await page.textContent('#wp-title');
    console.log(`검증: WordPress 제목 = "${wpTitleText}"`);
    
    if (!wpTitleText || wpTitleText.includes('(없음)')) {
      throw new Error('WordPress 제목 필드가 비어 있거나 정상 파싱되지 않았습니다.');
    }

    console.log('=== [9] E2E 테스트 최종 성공 ===');
    console.log(`브라우저 런타임 에러 개수: ${consoleErrors.length}개`);
    if (consoleErrors.length > 0) {
      throw new Error(`런타임 에러가 발생했습니다: ${JSON.stringify(consoleErrors)}`);
    }

  } catch (err) {
    console.error('실패: 브라우저 테스트 중 에러 발생!', err);
    try {
      await page.screenshot({ path: '/tmp/error_screenshot.png', fullPage: true });
      console.log('에러 스크린샷 저장 완료: /tmp/error_screenshot.png');
      const fs = require('fs');
      fs.copyFileSync('/tmp/error_screenshot.png', '/home/bourne/.gemini/antigravity-cli/brain/3e3cb890-8071-4157-be38-ddd1bb295d51/error_screenshot.png');
      console.log('아티팩트 폴더로 복사 완료.');
    } catch (ssErr) {
      console.error('스크린샷 저장 실패:', ssErr);
    }
    process.exit(1);
  } finally {
    await browser.close();
    console.log('=== [10] Playwright 브라우저 종료 ===');
  }
})();
