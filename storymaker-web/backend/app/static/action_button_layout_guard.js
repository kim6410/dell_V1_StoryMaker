(function(){
  function textOf(el){ return String(el && el.textContent || '').replace(/\s+/g,' ').trim(); }
  function isMobile(){ return window.matchMedia && window.matchMedia('(max-width: 760px)').matches; }

  function ensureStyle(){
    if (document.getElementById('smActionLayoutStyle')) return;
    var st = document.createElement('style');
    st.id = 'smActionLayoutStyle';
    st.textContent = '\n      .ai-action-buttons{display:flex!important;grid-template-columns:none!important;align-items:center!important;gap:10px!important;width:52%!important;max-width:820px!important;min-width:420px!important;}\n      .ai-action-buttons .btn-ai-auto{flex:1 1 auto!important;width:auto!important;max-width:none!important;margin:0!important;}\n      .ai-action-buttons .btn-user-paste{display:none!important;}\n      .ai-action-desc-grid{display:none!important;}\n      .sm-action-row{display:flex!important;align-items:center!important;gap:10px!important;width:52%!important;max-width:820px!important;min-width:420px!important;margin:10px 0 14px!important;}\n      .sm-action-row > button:not(.help-icon){flex:1 1 auto!important;width:auto!important;max-width:none!important;margin:0!important;}\n      .sm-action-row > .help-icon,.ai-action-buttons > .help-icon{display:inline-flex!important;align-items:center!important;justify-content:center!important;flex:0 0 36px!important;width:36px!important;height:36px!important;margin:0!important;}\n      @media (max-width: 760px){.ai-action-buttons,.sm-action-row{width:calc(100% - 2cm)!important;min-width:0!important;max-width:none!important;}}\n    ';
    document.head.appendChild(st);
  }

  function makeHelp(type, label){
    var help = document.createElement('button');
    help.type = 'button';
    help.className = 'help-icon';
    help.setAttribute('data-help', type);
    help.setAttribute('aria-label', label);
    help.textContent = '?';
    return help;
  }

  function styleHelp(help){
    help.style.setProperty('display','inline-flex','important');
    help.style.setProperty('align-items','center','important');
    help.style.setProperty('justify-content','center','important');
    help.style.setProperty('flex','0 0 36px','important');
    help.style.setProperty('width','36px','important');
    help.style.setProperty('height','36px','important');
    help.style.setProperty('margin','0','important');
  }

  function fitRow(row, btn){
    var mobile = isMobile();
    row.style.setProperty('display','flex','important');
    row.style.setProperty('align-items','center','important');
    row.style.setProperty('gap', mobile ? '8px' : '10px','important');
    row.style.setProperty('width', mobile ? '100%' : '52%','important');
    row.style.setProperty('max-width', mobile ? '100%' : '820px','important');
    row.style.setProperty('min-width', mobile ? '0' : '420px','important');
    row.style.setProperty('margin','10px 0 14px','important');
    btn.style.setProperty('flex','1 1 auto','important');
    btn.style.setProperty('width','auto','important');
    btn.style.setProperty('max-width','none','important');
    btn.style.setProperty('min-width','0','important');
    btn.style.setProperty('margin','0','important');
  }

  function ensureAiAutoRow(){
    var btn = document.querySelector('.btn-ai-auto') || Array.prototype.find.call(document.querySelectorAll('button'), function(b){ return textOf(b).indexOf('AI 자동생성') >= 0; });
    if (!btn) return;
    var row = btn.closest('.ai-action-buttons') || btn.parentElement;
    if (!row) return;
    fitRow(row, btn);
    row.querySelectorAll('.btn-user-paste').forEach(function(el){ el.style.setProperty('display','none','important'); });
    document.querySelectorAll('.ai-action-desc-grid').forEach(function(el){ el.style.setProperty('display','none','important'); });
    var help = row.querySelector('button.help-icon[data-help="ai-auto"]') || makeHelp('ai-auto','AI 자동생성 도움말');
    if (help.parentElement !== row) row.appendChild(help);
    styleHelp(help);
  }

  function ensureAllSplitRows(){
    var buttons = Array.prototype.filter.call(document.querySelectorAll('button'), function(b){ return textOf(b) === 'SNS별 분리'; });
    buttons.forEach(function(btn){
      var parent = btn.parentElement;
      if (!parent) return;
      var row = btn.closest('.sm-action-row');
      if (!row) {
        row = document.createElement('div');
        row.className = 'sm-action-row';
        parent.insertBefore(row, btn);
        row.appendChild(btn);
      }
      fitRow(row, btn);
      var help = row.querySelector('button.help-icon[data-help="split"]');
      if (!help) help = makeHelp('split','SNS 분리 도움말');
      if (help.parentElement !== row) row.appendChild(help);
      styleHelp(help);
    });

    document.querySelectorAll('button.help-icon[data-help="split"]').forEach(function(help){
      if (!help.closest('.sm-action-row')) help.style.setProperty('display','none','important');
    });
  }

  function apply(){
    ensureStyle();
    ensureAiAutoRow();
    ensureAllSplitRows();
  }

  window.applyStoryMakerActionButtonLayout = apply;
  document.addEventListener('DOMContentLoaded', function(){
    apply();
    setTimeout(apply, 300);
    setTimeout(apply, 1000);
    setTimeout(apply, 2500);
  });
  window.addEventListener('resize', apply);
  window.addEventListener('orientationchange', function(){ setTimeout(apply, 200); });
  var pending=false;
  var observer = new MutationObserver(function(){
    if (pending) return;
    pending=true;
    setTimeout(function(){
      pending=false;
      observer.disconnect(); // DOM 변경 적용 전 관찰 중단 (무한 루프 방지)
      apply();
      observer.observe(document.body, { childList:true, subtree:true }); // DOM 관찰 재개
    }, 80);
  });
  document.addEventListener('DOMContentLoaded', function(){
    observer.observe(document.body, { childList:true, subtree:true });
  });
})();
