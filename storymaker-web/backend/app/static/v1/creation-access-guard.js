(function(){
  'use strict';
  if(window.__STORYMAKER_CREATION_ACCESS_GUARD__) return;
  window.__STORYMAKER_CREATION_ACCESS_GUARD__=true;

  function text(el){return String((el&&el.innerText)||'').replace(/\s+/g,' ').trim();}
  function user(){try{return JSON.parse(localStorage.getItem('storymaker_user')||'null')}catch(e){return null}}
  function personas(){
    var list=[];
    try{list=JSON.parse(localStorage.getItem('storymaker_personas')||'[]')}catch(e){}
    if(!Array.isArray(list)||!list.length){
      try{list=JSON.parse(localStorage.getItem('myPersonas')||'[]')}catch(e){}
    }
    if((!Array.isArray(list)||!list.length)&&Array.isArray(window.myPersonas)) list=window.myPersonas;
    return Array.isArray(list)?list:[];
  }
  async function loadPersonas(){
    var list=[];
    try{
      var token=String(localStorage.getItem('storymaker_token')||'').trim();
      var headers=token?{'Authorization':'Bearer '+token}:{};
      var response=await fetch('/v1-api/auth/personas',{credentials:'include',headers:headers});
      var body=await response.json();
      list=body&&body.ok&&Array.isArray(body.data)?body.data:[];
    }catch(e){}
    if(!list.length) list=personas();
    return Array.isArray(list)?list:[];
  }
  function missingFields(persona){
    var p=persona||{};
    var keywords=Array.isArray(p.keywords)?p.keywords.filter(Boolean):String(p.keywords||'').split(',').map(function(value){return value.trim()}).filter(Boolean);
    var checks=[
      ['업체명',p.company_name||p.company],
      ['지역',p.region||p.area],
      ['전화번호',p.phone_number||p.phone||p.tel||p.business_phone],
      ['핵심 키워드',keywords.length],
      ['페르소나 상세 설명',String(p.content||p.persona||p.description||'').trim().length>=10]
    ];
    return checks.filter(function(item){return !item[1]}).map(function(item){return item[0]});
  }
  async function missingField(){
    var list=await loadPersonas();
    if(!list.length) return '업체정보 전체';
    if(list.some(function(persona){return missingFields(persona).length===0})) return '';
    var target=list.find(function(persona){return persona&&persona.is_default})||list[0]||{};
    return missingFields(target).join(', ')||'업체정보 전체';
  }
  function isCreationButton(btn){
    if(!btn) return false;
    var t=text(btn);
    return /딸깍|자동\s*생성|콘텐츠\s*생성|작업\s*시작|제작\s*시작/.test(t);
  }
  function goLogin(){location.href='/storymaker?action=login';}
  function goCompanyInfo(){
    var menu=[].slice.call(document.querySelectorAll('button,a,[role="button"]')).find(function(node){return text(node)==='업체 정보'});
    if(menu){menu.click();return;}
    location.href='/v1/?page=business';
  }

  document.addEventListener('click',async function(e){
    var btn=e.target&&e.target.closest&&e.target.closest('button,a,[role="button"]');
    if(!isCreationButton(btn)||btn.dataset.smGuardPass==='1') return;

    e.preventDefault();
    e.stopImmediatePropagation();

    var logged=!!user()||!!String(localStorage.getItem('storymaker_token')||'').trim();
    if(!logged){
      alert('로그인 후 이용할 수 있습니다.\n\n확인을 누르면 로그인 화면으로 이동합니다.');
      goLogin();
      return;
    }

    var missing=await missingField();
    if(missing){
      alert('딸깍 제작을 시작하려면 업체 기초정보를 먼저 등록해야 합니다.\n\n필수 입력: 업체명, 지역, 전화번호, 핵심 키워드, 페르소나 상세 설명\n\n현재 누락: '+missing+'\n\n확인을 누르면 업체 정보 화면으로 이동합니다.');
      goCompanyInfo();
      return;
    }

    btn.dataset.smGuardPass='1';
    btn.click();
    setTimeout(function(){delete btn.dataset.smGuardPass},0);
  },true);
})();
