(function(){
  function $(s,r){return (r||document).querySelector(s)}
  function $all(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
  function now(){var d=new Date();return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')+':'+String(d.getSeconds()).padStart(2,'0')}

  function addStyle(){
    if($('#smConsoleRestoreStyle'))return;
    var st=document.createElement('style');
    st.id='smConsoleRestoreStyle';
    st.textContent='\
      #aagConsole,#sm-ai-live-console{display:block!important;visibility:visible!important;opacity:1!important;max-height:none!important;overflow:visible!important;margin:16px 0!important;padding:16px!important;border:1px solid rgba(125,211,252,.52)!important;border-radius:18px!important;background:linear-gradient(135deg,rgba(2,6,23,.96),rgba(15,23,42,.98))!important;box-shadow:0 16px 42px rgba(0,0,0,.38),0 0 22px rgba(56,189,248,.16)!important;color:#eaf6ff!important;font-family:Consolas,Monaco,\'Courier New\',monospace!important}\
      #sm-ai-live-console .sm-console-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px;font-weight:900;color:#fff}\
      #sm-ai-live-console .sm-console-dot{width:10px;height:10px;border-radius:999px;background:#22d3ee;box-shadow:0 0 14px rgba(34,211,238,.9);display:inline-block;margin-right:8px;animation:smConsolePulse 1.1s infinite}\
      #sm-ai-live-console .sm-console-log{max-height:180px!important;overflow-y:auto!important;display:flex;flex-direction:column;gap:6px;font-size:13px;line-height:1.55}\
      #sm-ai-live-console .sm-console-row{color:#f8fbff}\
      #sm-ai-live-console .sm-console-time{color:#93c5fd;margin-right:8px;font-size:11px}\
      #workspace-ai.open #ai-accordion-content{display:block!important;max-height:none!important;overflow:visible!important}\
      @keyframes smConsolePulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.45;transform:scale(.82)}}';
    document.head.appendChild(st);
  }

  function openAiSection(){
    var ws=$('#workspace-ai');
    var content=$('#ai-accordion-content');
    if(ws)ws.classList.add('open');
    if(content){
      content.style.setProperty('display','block','important');
      content.style.setProperty('max-height','none','important');
      content.style.setProperty('overflow','visible','important');
      content.style.setProperty('padding','24px','important');
    }
  }

  function ensureConsole(){
    addStyle();
    openAiSection();
    var c=$('#aagConsole')||$('#sm-ai-live-console');
    if(!c){
      c=document.createElement('div');
      c.id='sm-ai-live-console';
      c.innerHTML='<div class="sm-console-head"><div><span class="sm-console-dot"></span>AI Worker 작업 로그</div><div id="sm-console-percent">준비중</div></div><div class="sm-console-log" id="sm-console-log"></div>';
    }
    var content=$('#ai-accordion-content');
    var raw=$('#raw-input-area');
    var firstPanel=raw?$('.ai-action-panel',raw):null;
    if(firstPanel&&firstPanel.parentElement){
      firstPanel.insertAdjacentElement('afterend',c);
    }else if(content){
      content.insertBefore(c,content.firstChild);
    }else{
      document.body.appendChild(c);
    }
    c.style.setProperty('display','block','important');
    c.style.setProperty('visibility','visible','important');
    c.style.setProperty('opacity','1','important');
    c.classList.remove('aag-collapse');
    return c;
  }

  function addLog(message){
    var c=ensureConsole();
    var log=$('#aagLog',c)||$('#sm-console-log',c);
    if(!log)return;
    var row=document.createElement('div');
    row.className='sm-console-row';
    row.innerHTML='<span class="sm-console-time">['+now()+']</span>'+message;
    log.appendChild(row);
    while(log.children.length>80)log.removeChild(log.firstChild);
    log.scrollTop=log.scrollHeight;
  }

  function looksLikeTrigger(btn){
    if(!btn)return false;
    var t=(btn.textContent||'').replace(/\s+/g,' ').trim();
    return t.indexOf('AI 자동생성')>=0 || t.indexOf('AI 자동 생성')>=0 || t.indexOf('다음 단계: AI 콘텐츠 제작')>=0 || t.indexOf('AI 콘텐츠 제작')>=0;
  }

  function bind(){
    addStyle();
    document.addEventListener('click',function(e){
      var btn=e.target.closest&&e.target.closest('button');
      if(!looksLikeTrigger(btn))return;
      ensureConsole();
      addLog('AI 콘텐츠 제작 로그창을 열었습니다.');
      setTimeout(function(){addLog('입력값과 프롬프트 상태를 확인하고 있습니다.');},420);
      setTimeout(function(){addLog('AI Worker 작업 흐름을 준비합니다.');},900);
      setTimeout(function(){
        var target=$('#aagConsole')||$('#sm-ai-live-console');
        if(target)target.scrollIntoView({behavior:'smooth',block:'center'});
      },180);
    },true);

    setInterval(function(){
      var ws=$('#workspace-ai');
      var c=$('#aagConsole')||$('#sm-ai-live-console');
      if(c&&ws&&ws.classList.contains('open')){
        c.style.setProperty('display','block','important');
        c.style.setProperty('visibility','visible','important');
        c.style.setProperty('opacity','1','important');
        c.classList.remove('aag-collapse');
      }
    },700);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
})();
