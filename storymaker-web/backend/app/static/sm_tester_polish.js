(function(){
  function isAdmin(){
    var text=(document.body&&document.body.innerText||'').replace(/\s+/g,' ');
    return text.indexOf('역할: 관리자')>=0 || text.indexOf('Admin')>=0 || text.indexOf('관리자 화면')>=0 || location.search.indexOf('mode=admin')>=0;
  }
  function run(){
    var admin=isAdmin();
    document.querySelectorAll('.sm-mode-sub').forEach(function(el){
      if((el.textContent||'').indexOf('기본 기능')>=0){el.textContent='오늘 작업 내용을 입력하고 SNS 글을 만들어 보세요.';}
    });
    document.querySelectorAll('.sm-mode-buttons').forEach(function(el){
      el.hidden=!admin;
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){run();setTimeout(run,800);});
  else{run();setTimeout(run,800);}
})();