(function(){
  function findButtons(){
    return Array.from(document.querySelectorAll('button'));
  }
  function isTopUtilityButton(btn){
    var t=(btn.textContent||'').replace(/\s+/g,' ').trim();
    return t.indexOf('키워드 빈도 추출')>=0 || t==='AI 자동 생성';
  }
  function isLowerAiButton(btn){
    var t=(btn.textContent||'').replace(/\s+/g,' ').trim();
    return t.indexOf('AI 자동생성')>=0;
  }
  function hideTopUtility(){
    findButtons().forEach(function(btn){
      if(isTopUtilityButton(btn)){
        var wrap=btn.parentElement;
        if(wrap) wrap.style.setProperty('display','none','important');
        btn.style.setProperty('display','none','important');
      }
    });
    var ukc=document.getElementById('ukcBox');
    if(ukc) ukc.style.setProperty('display','none','important');
  }
  function triggerMainFlow(btn){
    if(window.generatePromptWithValidation){
      window.generatePromptWithValidation();
      return;
    }
    var legacy=findButtons().find(function(b){return (b.textContent||'').indexOf('통합 프롬프트 만들기')>=0});
    if(legacy) legacy.click();
  }
  function bindLowerButton(){
    document.addEventListener('click',function(e){
      var btn=e.target.closest&&e.target.closest('button');
      if(!btn || !isLowerAiButton(btn)) return;
      e.preventDefault();
      e.stopPropagation();
      btn.disabled=true;
      var old=btn.textContent;
      btn.textContent='AI 자동생성 중...';
      triggerMainFlow(btn);
      setTimeout(function(){btn.disabled=false;btn.textContent=old||'AI 자동생성';},5000);
    },true);
  }
  function boot(){
    hideTopUtility();
    bindLowerButton();
    setTimeout(hideTopUtility,800);
    setTimeout(hideTopUtility,1800);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();