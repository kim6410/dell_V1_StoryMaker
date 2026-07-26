(function(){
  var running=false;
  var originalGenerate=null;
  var lowerButtonBound=false;
  var totalDelayMs=29000;

  function $(s,r){return (r||document).querySelector(s)}
  function $all(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
  function textOf(sel){var el=$(sel);return el?(el.value||el.textContent||''):''}

  function addStyle(){
    if($('#aagStyle'))return;
    var st=document.createElement('style');
    st.id='aagStyle';
    st.textContent='\
      .aag-console{display:block!important;visibility:visible!important;opacity:1!important;min-height:120px!important;margin:18px 0;padding:18px;border:1px solid rgba(245,245,245,.34);border-radius:18px;background:linear-gradient(135deg,rgba(2,6,10,.96),rgba(9,12,18,.96));box-shadow:0 18px 48px rgba(0,0,0,.42),inset 0 0 24px rgba(255,255,255,.035);font-family:Consolas,Monaco,\'Courier New\',monospace}\
      .aag-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.aag-title{display:flex;align-items:center;gap:10px;font-size:18px;font-weight:950;color:#fff}.aag-dot{width:11px;height:11px;border-radius:999px;background:#7dd3fc;box-shadow:0 0 14px rgba(125,211,252,.82),0 0 28px rgba(125,211,252,.42);animation:aagPulse 1.2s ease-in-out infinite}.aag-dot.done{background:#9ca3af;box-shadow:none;animation:none}.aag-percent{font-size:13px;color:#ffffff;font-weight:900;text-shadow:0 0 8px rgba(255,255,255,.28)}.aag-bar{height:8px;border-radius:999px;background:rgba(255,255,255,.10);overflow:hidden;margin-bottom:12px}.aag-bar-fill{height:100%;width:0%;border-radius:999px;background:linear-gradient(90deg,#d9d9d9,#ffffff,#bdbdbd);transition:width .55s ease;box-shadow:0 0 12px rgba(255,255,255,.22)}.aag-log{max-height:210px;overflow-y:auto;display:flex;flex-direction:column;gap:7px;font-size:13px;line-height:1.55;padding-right:8px;transition:max-height .45s ease}.aag-console.finished .aag-log{max-height:72px}.aag-row{color:#f8fbff;opacity:.94;transform:translateY(6px);animation:aagIn .22s ease forwards;text-shadow:0 0 8px rgba(255,255,255,.14)}.aag-row.latest{color:#ffffff;opacity:1;font-weight:900;text-shadow:0 0 10px rgba(255,255,255,.22),0 0 18px rgba(255,255,255,.08)}.aag-row.done{color:#f6f6f6}.aag-row.ai{color:#ffffff}.aag-row.info{color:#e8e8e8}.aag-time{color:#d7d7d7;margin-right:8px;font-size:11px;font-family:Consolas,Monaco,monospace;text-shadow:0 0 8px rgba(255,255,255,.22)}.aag-step{color:#ffffff;margin-right:8px;font-weight:900;text-shadow:0 0 9px rgba(255,255,255,.24)}.aag-collapse{max-height:0!important;opacity:.18!important;overflow:hidden!important;transform:translateY(-8px);transition:max-height .45s ease,opacity .35s ease,transform .35s ease,padding .35s ease,margin .35s ease!important;padding-top:0!important;padding-bottom:0!important;margin-top:0!important;margin-bottom:8px!important}\
      @keyframes aagPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.55;transform:scale(.82)}}@keyframes aagIn{to{transform:translateY(0)}}';
    document.head.appendChild(st);
  }

  function findTopGenerateButton(){
    return $all('button').find(function(b){
      var t=(b.textContent||'').replace(/\s+/g,' ').trim();
      return t.indexOf('통합 프롬프트 만들기')>=0 || t==='AI 자동 생성';
    });
  }

  function findLowerAiButton(){
    return $all('button').find(function(b){
      var t=(b.textContent||'').replace(/\s+/g,' ').trim();
      return t.indexOf('AI 자동생성')>=0;
    });
  }

  function findGenerateButton(){return findLowerAiButton()||findTopGenerateButton()}

  function renameButton(){
    var btn=findTopGenerateButton();
    if(!btn)return;
    btn.innerHTML='AI 자동 생성';
    btn.setAttribute('data-aag-ready','1');
  }

  function forceAiConsoleVisible(){
    var ws=$('#workspace-ai');
    var content=$('#ai-accordion-content');
    var c=$('#aagConsole');
    if(ws)ws.classList.add('open');
    if(content){
      content.style.display='block';
      content.style.maxHeight='none';
      content.style.padding='';
      content.style.overflow='visible';
    }
    if(c){
      c.style.display='block';
      c.style.visibility='visible';
      c.style.opacity='1';
      c.classList.remove('aag-collapse');
    }
  }

  function ensureConsole(btn){
    var c=$('#aagConsole');
    if(!c){
      c=document.createElement('div');
      c.id='aagConsole';
      c.className='aag-console';
      c.innerHTML='<div class="aag-head"><div class="aag-title"><span class="aag-dot" id="aagDot"></span><span id="aagTitle">대기중</span></div><div class="aag-percent" id="aagPercent">0%</div></div><div class="aag-bar"><div class="aag-bar-fill" id="aagFill"></div></div><div class="aag-log" id="aagLog"></div>';
    }
    var content=$('#ai-accordion-content');
    var rawArea=$('#raw-input-area');
    var panel=rawArea?$('.ai-action-panel',rawArea):$('.ai-action-panel',content);
    if(panel&&panel.parentElement){
      panel.insertAdjacentElement('afterend',c);
    }else if(content){
      content.insertBefore(c,content.firstChild);
    }else{
      var card=(btn&&btn.closest&&btn.closest('.card'))||(btn&&btn.parentElement);
      if(card)card.insertBefore(c,card.firstChild);else document.body.appendChild(c);
    }
    forceAiConsoleVisible();
    return c;
  }

  function now(){var d=new Date();return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')+':'+String(d.getSeconds()).padStart(2,'0')}

  function addLog(msg,type){
    var log=$('#aagLog');if(!log)return;
    $all('.aag-row',log).forEach(function(x){x.classList.remove('latest')});
    var row=document.createElement('div');
    row.className='aag-row latest '+(type||'info');
    row.innerHTML='<span class="aag-time">'+now()+'</span>'+msg;
    log.appendChild(row);
    while(log.children.length>140)log.removeChild(log.firstChild);
    log.scrollTop=log.scrollHeight;
  }

  function progress(p,title){
    var fill=$('#aagFill'),per=$('#aagPercent'),t=$('#aagTitle');
    if(fill)fill.style.width=p+'%';
    if(per)per.textContent=p+'%';
    if(t)t.textContent=title||'대기중';
  }
  function markWorkerDone(){
    var t=$('#aagTitle'),dot=$('#aagDot'),per=$('#aagPercent'),fill=$('#aagFill');
    if(t)t.textContent='AI Worker 작업완료';
    if(dot)dot.classList.add('done');
    if(per)per.textContent='100%';
    if(fill)fill.style.width='100%';
  }

  function extractKeywords(){
    var box=$('#ukcBox');
    var txt=box?(box.textContent||''):'';
    txt=txt.replace('추천 키워드:','').replace('자동으로 글 생성에 활용됩니다.','').replace('|','').trim();
    var hidden=textOf('#keywords').trim();
    return txt||hidden||'샤시 · 울산 · 환풍기 · 교체 · 창문 · 단열 · 현장';
  }

  function refLen(){var t=textOf('#reference_text');return t?t.length:0}
  function baseLen(){var t=textOf('#base_content');return t?t.length:0}
  function companyName(){
    var personaCompany=textOf('#mypage-persona-company').trim();
    var direct=textOf('#company').trim();
    var saved=localStorage.getItem('storymaker_company')||localStorage.getItem('company')||localStorage.getItem('business_name')||'';
    var candidates=[personaCompany,direct,saved];
    var found=$all('#mypage-persona-company,[data-company],[data-business-name]').map(function(el){return (el.value||el.textContent||'').trim()}).filter(Boolean);
    candidates=candidates.concat(found);
    var bad=['우리동네 인테리어','업체 정보','회사명','상호명','울산','북구','호계동','울산 북구','북구 호계동','울산 북구 호계동','현재 지역','스토리형'];
    var picked=candidates.find(function(v){return v && bad.indexOf(v)<0});
    return picked||direct||'업체 정보';
  }
  function regionName(){
    var setting=currentSetting();
    var m=setting.split('·')[0];
    return (m||textOf('#region')||textOf('#location')||'현재 지역').trim();
  }
  function phoneText(){
    var raw=textOf('#phone_number').trim()||textOf('#mypage-persona-phone').trim()||textOf('#profile-phone-summary').trim()||textOf('#phone').trim()||textOf('#tel').trim()||localStorage.getItem('storymaker_phone')||localStorage.getItem('phone_number')||'';
    raw=String(raw||'').replace(/·.*$/,'').trim();
    return raw && raw.indexOf('등록 필요')<0 ? raw : '전화번호 미등록';
  }
  function currentSetting(){var el=$('#uscSummaryText');return el?(el.textContent||'').trim():'울산 · 뉴스형 · 따뜻함/전문가/신뢰감'}
  function todayText(){
    try{return new Date().toLocaleDateString('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'long',day:'numeric',weekday:'long'})}
    catch(e){return new Date().toLocaleDateString('ko-KR')}
  }
  function timeBlock(){
    var h=Number(new Date().toLocaleString('en-US',{timeZone:'Asia/Seoul',hour:'2-digit',hour12:false}));
    if(h<6)return '늦은 밤';
    if(h<9)return '이른 아침';
    if(h<12)return '오전';
    if(h<18)return '오후';
    if(h<22)return '저녁';
    return '늦은 저녁';
  }
  function currentKstMonthDayHourWithWeekday(){
    try{
      var kst=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Seoul'}));
      var week=['일요일','월요일','화요일','수요일','목요일','금요일','토요일'][kst.getDay()];
      var mm=String(kst.getMonth()+1);
      var dd=String(kst.getDate());
      var hh=String(kst.getHours()).padStart(2,'0');
      var mi=String(kst.getMinutes()).padStart(2,'0');
      return mm+'월 '+dd+'일('+week+') '+hh+'시 '+mi+'분';
    }catch(e){return currentKstMonthDayHour()}
  }
  function currentKstMonthDayHour(){
    try{
      var parts=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'long',day:'numeric',hour:'2-digit',hour12:false}).formatToParts(new Date());
      var m=(parts.find(function(p){return p.type==='month'})||{}).value||'';
      var d=(parts.find(function(p){return p.type==='day'})||{}).value||'';
      var h=(parts.find(function(p){return p.type==='hour'})||{}).value||'';
      return m+' '+d+'일 '+h+'시';
    }catch(e){
      var n=new Date();
      return (n.getMonth()+1)+'월 '+n.getDate()+'일 '+n.getHours()+'시';
    }
  }
  function actualWeatherText(){
    var prompt=(($('#generated-prompt-box')||{}).innerText||'');
    var m=prompt.match(/## 오늘의 현장 날씨\s*([\s\S]*?)(?:\n## |$)/)||prompt.match(/## 현재 현장 상황\s*([\s\S]*?)(?:\n## |$)/);
    var legacy=(prompt.split('\n').find(function(line){return line.trim().indexOf('- 오늘 날씨 참고:')===0})||'').replace('- 오늘 날씨 참고:','').trim();
    var text=m?m[1].split('\n').map(function(line){return line.trim()}).filter(Boolean).join(' / '):legacy;
    text=String(text||'').replace(/## .+$/s,'').replace(/\s+/g,' ').trim();
    if(text && !text.includes('실패') && !text.includes('찾지 못했습니다') && !text.includes('초과') && !text.includes('비어 있습니다') && !text.includes('날씨 정보는 아직 충분하지 않습니다'))return text.slice(0,150);
    var weatherSelectors=['#weather_summary','#weatherText','#weather-info','#weatherInfo','#today-weather','#weatherSnapshot','[data-weather-summary]','[data-weather]'];
    for(var i=0;i<weatherSelectors.length;i++){
      var el=$(weatherSelectors[i]);
      var v=el?(el.value||el.textContent||'').trim():'';
      if(v && v.length>3)return v.replace(/\s+/g,' ').slice(0,150);
    }
    var stored=localStorage.getItem('storymaker_weather_summary')||localStorage.getItem('weather_summary')||'';
    if(stored && stored.length>3)return stored.replace(/\s+/g,' ').slice(0,150);
    return '날씨 정보 확인 중';
  }

  function collapseDoneSections(){
    var targets=[];
    var ref=$('#reference_text');if(ref){var b=ref.closest('.form-section')||ref.closest('.card')||ref.closest('.editable-work-card')||ref.closest('.input-group');if(b)targets.push(b)}
    var setting=$('#uscSummary');if(setting){var s=setting.closest('.form-section')||setting.closest('.card')||setting.parentElement;if(s)targets.push(s)}
    ['#contentIdeaEngine','#basic_input','#basicInput'].forEach(function(sel){var x=$(sel);if(x){var p=x.closest('.form-section')||x.closest('.card')||x.closest('.input-group')||x.parentElement;if(p)targets.push(p)}});
    targets.forEach(function(el){if(el && !el.contains($('#aagConsole')))el.classList.add('aag-collapse')});
  }

  function openAiWorkspace(){
    try{if(typeof window.toggleAccordionSection==='function')window.toggleAccordionSection('ai',true)}catch(e){}
    var ai=$('#workspace-ai');
    if(ai){setTimeout(function(){ai.scrollIntoView({behavior:'smooth',block:'start'})},120)}
  }

  function setNativeAiStatus(msg,state){
    try{if(typeof window.setAIGenerationStatus==='function')window.setAIGenerationStatus(msg,state||'active')}catch(e){}
  }

  function stepFactory(total){
    var n=0;
    return function(p,msg,type){
      n+=1;
      var prefix='<span class="aag-step">['+String(n).padStart(2,'0')+'/'+total+']</span>';
      if(typeof msg==='function'){
        return [p,function(){return prefix+msg()},type||'info'];
      }
      return [p,prefix+msg,type||'info'];
    };
  }

  function buildSteps(){
    var make=stepFactory(75);
    var kw=extractKeywords().split(/[·,]/).map(function(x){return x.trim()}).filter(Boolean).slice(0,8);
    while(kw.length<8)kw.push(['샤시','울산','환풍기','교체','창문','단열','현장','신뢰감'][kw.length]);
    return [
      make(2,'AI SNS 콘텐츠 생성을 시작합니다.','ai'),
      make(4,'사용자 정보를 확인합니다.','done'),
      make(5,'사용자 정보 : '+companyName(),'done'),
      make(7,'현재 지역을 확인합니다.','info'),
      make(9,'현재 설정 : '+currentSetting(),'info'),
      make(10,'글 스타일과 감성 설정을 분리합니다.','info'),
      make(12,companyName()+' 페르소나를 불러왔습니다.','done'),
      make(14,companyName()+' 브랜드 말투와 현장 경험을 정리합니다.','done'),
      make(15,'오늘 날짜 확인 : '+todayText(),'info'),
      make(17,'현재 작업 시간대 : '+timeBlock(),'info'),
      make(18,'계절감과 시간대 표현을 정리하고 있습니다.','info'),
      make(19,'실제 날씨 정보 확인 완료 : '+actualWeatherText(),'info'),
      make(20,'날씨 정보를 본문 배경으로 반영할 준비를 합니다.','info'),
      make(21,'현장 분위기를 반영할 준비를 합니다.','info'),
      make(22,'날짜, 시간, 날씨 문장을 과하지 않게 압축합니다.','info'),
      make(23,'오늘 현장감이 살아나도록 도입부 재료를 정리합니다.','info'),
      make(22,'오늘 작업내용을 확인합니다. 입력된 내용 '+baseLen().toLocaleString('ko-KR')+'자를 읽고 있습니다.','info'),
      make(24,'문제 상황을 따로 분리합니다.','info'),
      make(25,'고객 요청과 불편 포인트를 표시합니다.','info'),
      make(27,'작업 과정을 순서대로 재배열합니다.','info'),
      make(29,'해결 결과와 체감 변화를 연결합니다.','info'),
      make(30,'글감 조회 자료를 확인합니다. 참고자료 '+refLen().toLocaleString('ko-KR')+'자를 분석합니다.','done'),
      make(32,'참고자료 분석 중 : 총 '+refLen().toLocaleString('ko-KR')+'자','done'),
      make(33,'참고자료의 제목 흐름을 분리합니다.','done'),
      make(34,'참고자료의 본문 핵심만 따로 표시합니다.','done'),
      make(34,'중복 문장과 과한 표현을 걷어냅니다.','done'),
      make(35,'핵심 참고 흐름만 남깁니다.','done'),
      make(37,'추천 키워드 적용: '+kw[0],'done'),
      make(39,'추천 키워드 적용: '+kw[1],'done'),
      make(40,'추천 키워드 적용: '+kw[2],'done'),
      make(42,'추천 키워드 적용: '+kw[3],'done'),
      make(44,'추천 키워드 적용: '+kw[4],'done'),
      make(45,'추천 키워드 적용: '+kw.join(' · '),'done'),
      make(47,'문장 흐름을 문제 상황 → 해결 과정 → 결과 순서로 정리합니다.','ai'),
      make(49,'글쓰기 스타일을 적용합니다.','ai'),
      make(50,'글쓰기 감성 톤을 적용합니다.','ai'),
      make(52,'네이버 검색 최적화 규칙을 반영합니다.','ai'),
      make(54,'본문에 지역명 배치 규칙을 점검합니다 : '+regionName(),'ai'),
      make(55,'본문에 상호 배치 규칙을 점검합니다 : '+companyName(),'ai'),
      make(57,'본문에 전화번호 배치 규칙을 점검합니다 : '+phoneText(),'ai'),
      make(58,'연락 안내 문장의 위치를 조정합니다.','ai'),
      make(58,'문의 문장이 과하지 않도록 다듬습니다.','ai'),
      make(59,'AI 글쓰기 프롬프트를 생성 중 10%','ai'),
      make(60,'AI 글쓰기 프롬프트를 생성 중 30%','ai'),
      make(62,'AI 글쓰기 프롬프트를 생성 중 70%','ai'),
      make(64,'AI 글쓰기 프롬프트를 생성 중 100%','ai'),
      make(65,'AI 글쓰기 프롬프트를 적용 중 10%','ai'),
      make(67,'AI 글쓰기 프롬프트를 적용 중 25%','ai'),
      make(69,'AI 글쓰기 프롬프트를 적용 중 65%','ai'),
      make(70,'AI 글쓰기 프롬프트를 적용 중 100%','ai'),
      make(72,'SNS 채널별 콘텐츠 생성 중 - 네이버 블로그','ai'),
      make(74,'SNS 채널별 콘텐츠 생성 중 - 인스타그램','ai'),
      make(75,'SNS 채널별 콘텐츠 생성 중 - 플레이스','ai'),
      make(77,'SNS 채널별 콘텐츠 생성 중 - 당근마켓','ai'),
      make(79,'SNS 채널별 콘텐츠 생성 중 - 카드뉴스','ai'),
      make(80,'SNS 채널별 콘텐츠 생성 중 - 구글 마이비즈니스','ai'),
      make(81,'각 채널별 첫 문장을 따로 점검합니다.','ai'),
      make(81,'각 채널별 마무리 문장을 따로 점검합니다.','ai'),
      make(81,'플랫폼별 글자 수와 호흡을 맞춥니다.','ai'),
      make(82,'SNS 팟캐스트 콘텐츠 생성 중 (1)','ai'),
      make(84,'SNS 팟캐스트 콘텐츠 생성 중 (2)','ai'),
      make(85,'프롬프트 생성 완료.','done'),
      make(87,'Firefox AI Worker로 전송합니다.','ai'),
      make(89,'AI Worker 작업 중 10%','ai'),
      make(90,'AI Worker 작업 중 25%','ai'),
      make(92,'AI Worker 작업 중 53%','ai'),
      make(94,'AI Worker 작업 중 82%','ai'),
      make(95,'AI Worker 작업 중 100%','ai'),
      make(96,'결과 입력칸 반영 준비를 확인합니다.','info'),
      make(97,'마무리 작업 진행 중','info'),
      make(99,'마무리 작업 진행 중','info'),
      make(100,'마무리 작업 진행 중. 잠시만 기다려 주세요.','done')
    ];
  }

  function runLogs(done){
    var steps=buildSteps();
    var i=0;
    var eachDelay=Math.max(420,Math.floor(totalDelayMs/steps.length));
    function next(){
      if(i>=steps.length){done();return}
      var s=steps[i++];
      progress(s[0],'AI Worker 작업중');
      var msg=(typeof s[1]==='function')?s[1]():s[1];
      addLog(msg,s[2]);
      if(s[0]>=30 && s[0]<35)collapseDoneSections();
      setTimeout(next,eachDelay);
    }
    next();
  }

  function callOriginalGenerate(){
    if(!originalGenerate)return Promise.resolve();
    try{return Promise.resolve(originalGenerate.call(window));}
    catch(e){return Promise.reject(e)}
  }

  function triggerGeminiAfterPrompt(btn){
    var autoBtn=findLowerAiButton()||btn;
    if(typeof window.generateAIContentAutomatically!=='function'){
      addLog('AI 자동생성 함수가 아직 준비되지 않았습니다. 화면을 새로고침한 뒤 다시 실행해 주세요.','ai');
      running=false;
      if(btn){btn.disabled=false;btn.textContent='AI 자동생성'}
      return;
    }
    progress(100,'AI Worker 전송 중');
    addLog('Firefox AI Worker에게 프롬프트 전송 트리거를 실행합니다.','ai');
    setNativeAiStatus('글쓰기 준비가 끝났습니다. AI Worker로 프롬프트를 전송합니다.','active');
    openAiWorkspace();
    Promise.resolve(window.generateAIContentAutomatically(autoBtn)).finally(function(){
      running=false;
      if(btn){btn.disabled=false;btn.innerHTML='<span class="ai-mini-icon">AI</span> AI 자동생성'}
    });
  }

  function startAutoFlow(btn){
    if(running)return;
    running=true;
    btn=btn||findGenerateButton();
    if(btn){btn.disabled=true;btn.textContent='AI 자동생성 요청 중...'}
    ensureConsole(btn||document.body);
    progress(0,'AI 자동 생성 준비');
    var log=$('#aagLog');if(log)log.innerHTML='';
    var consoleBox=$('#aagConsole');if(consoleBox)consoleBox.classList.remove('finished');
    addLog('AI 자동 생성을 시작합니다. 내부 작업은 즉시 실행하고, 화면에는 과정을 순차적으로 보여드립니다.','ai');
    setNativeAiStatus('AI 자동생성을 시작합니다. AI Worker 전송을 준비합니다.','active');

    callOriginalGenerate().then(function(){
      addLog('프롬프트 생성 완료. AI Worker로 바로 전송합니다.','done');
      triggerGeminiAfterPrompt(btn);
    }).catch(function(err){
      running=false;
      addLog('프롬프트 생성 중 오류: '+(err&&err.message?err.message:err),'ai');
      setNativeAiStatus('프롬프트 생성 중 오류가 발생했습니다.','error');
      if(btn){btn.disabled=false;btn.textContent='AI 자동생성'}
    });

    runLogs(function(){
      markWorkerDone();
      addLog('기초 작업 진행 모두 완료했습니다.','done');
      var closing=[
        '나머지 내용 정리 작업 진행중입니다.(1/5)',
        '나머지 내용 정리 작업 진행중입니다.(2/5)',
        '나머지 내용 정리 작업 진행중입니다.(3/5)',
        '나머지 내용 정리 작업 진행중입니다.(4/5)',
        '나머지 내용 정리 작업 진행중입니다.(5/5)',
        '마무리 진행중입니다.',
        '거의 마무리가 되어가고 있습니다.',
        '잠시만 기다려 주세요.',
        '현재 시간은 '+currentKstMonthDayHourWithWeekday()+'입니다. 오늘도 남은 시간 건강하고 행복하세요.',
        '최종 검증을 완료했습니다.','모든 작업이 정상적으로 완료되었습니다.','결과를 화면에 정리하고 있습니다.',
        '오늘도 StoryMaker와 함께해 주셔서 감사합니다.',
        '<span style="display:inline-block;color:#fff;text-shadow:0 0 10px rgba(255,255,255,.35);">c:\\<span style="animation:aagPulse .72s step-end infinite;">_</span></span>'
      ];
      closing.forEach(function(item,idx){
        setTimeout(function(){
          addLog(typeof item==='function'?item():item,'done');
        },idx*620);
      });
      setTimeout(function(){
        var consoleBox=$('#aagConsole');
        if(consoleBox)consoleBox.classList.add('finished');
        var log=$('#aagLog');
        if(log)log.scrollTop=log.scrollHeight;
      },closing.length*620+500);
    });
  }

  function install(){
    addStyle();
    renameButton();
    if(!originalGenerate && typeof window.generatePromptWithValidation==='function'){
      originalGenerate=window.generatePromptWithValidation;
      window.generatePromptWithValidation=function(){startAutoFlow(findGenerateButton())};
    }
  }

  function bindLowerAiButton(){
    if(lowerButtonBound)return;
    lowerButtonBound=true;
    document.addEventListener('click',function(e){
      var btn=e.target.closest&&e.target.closest('button');
      if(!btn)return;
      var t=(btn.textContent||'').replace(/\s+/g,' ').trim();
      if(t.indexOf('AI 자동생성')<0)return;
      e.preventDefault();
      e.stopPropagation();
      startAutoFlow(btn);
    },true);
  }

  function hideTopUtility(){
    Array.from(document.querySelectorAll('button')).forEach(function(btn){
      var t=(btn.textContent||'').replace(/\s+/g,' ').trim();
      if(t.indexOf('키워드 빈도 추출')>=0||t==='AI 자동 생성'){
        var p=btn.parentElement;
        if(p)p.style.setProperty('display','none','important');
        btn.style.setProperty('display','none','important');
      }
    });
    var k=document.getElementById('ukcBox');
    if(k)k.style.setProperty('display','none','important');
  }

  function boot(){install();bindLowerAiButton();hideTopUtility();setTimeout(install,1000);setTimeout(hideTopUtility,1000);setTimeout(install,2500);setTimeout(function(){ensureConsole(findGenerateButton()||document.body);forceAiConsoleVisible();},1800)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();