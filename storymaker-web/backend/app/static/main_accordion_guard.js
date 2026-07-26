(function(){
  function $(selector){ return document.querySelector(selector); }

  function inputIsOpen(){
    var content = $('#accordion-content');
    return !!(content && content.style.display !== 'none');
  }

  function setInputOpen(open){
    var content = $('#accordion-content');
    var icon = $('#accordion-icon');
    var card = content && (content.closest('.accordion-card') || content.parentElement);
    if (!content) return;
    content.style.display = open ? 'block' : 'none';
    content.style.maxHeight = open ? 'none' : '0';
    content.style.overflow = open ? 'visible' : 'hidden';
    if (card) card.classList.toggle('open', !!open);
    if (icon) icon.textContent = open ? '▲' : '▼';
  }

  function workspaceIsOpen(sectionId){
    var card = $('#workspace-' + sectionId);
    var content = $('#' + sectionId + '-accordion-content');
    return !!(card && content && card.classList.contains('open') && content.style.display !== 'none');
  }

  function setWorkspaceOpen(sectionId, open){
    var card = $('#workspace-' + sectionId);
    var content = $('#' + sectionId + '-accordion-content');
    if (!card || !content) return;

    // AI 콘텐츠 시작 영역은 작업 진행/결과 확인 입력 영역이므로 닫히지 않게 고정한다.
    // 다른 섹션을 여닫아도 이 섹션은 항상 열린 상태를 유지한다.
    if (sectionId === 'ai') open = true;

    card.classList.toggle('open', !!open);

    if (open) {
      content.style.display = 'block';
      content.style.maxHeight = 'none';
      content.style.padding = '';
      content.style.overflow = 'visible';
    } else {
      content.style.display = 'none';
      content.style.maxHeight = '0';
      content.style.padding = '0 24px';
      content.style.overflow = 'hidden';
    }

    try {
      localStorage.setItem('storymaker.workspace.' + sectionId + '.open', open ? 'true' : 'false');
    } catch(e) {}
  }

  function closeMainSectionsExcept(except){
    if (except !== 'input') setInputOpen(false);
    // AI 콘텐츠 시작 영역은 항상 열린 상태로 유지한다.
    setWorkspaceOpen('ai', true);
    if (except !== 'sns') setWorkspaceOpen('sns', false);
  }

  function openMainSection(sectionId){
    closeMainSectionsExcept(sectionId);
    if (sectionId === 'input') setInputOpen(true);
    if (sectionId === 'ai') setWorkspaceOpen('ai', true);
    if (sectionId === 'sns') setWorkspaceOpen('sns', true);
  }

  window.openStoryMakerMainSection = openMainSection;

  function installAccordionPatch(){
    if (window.__storymakerMainAccordionPatched) return;
    window.__storymakerMainAccordionPatched = true;

    window.toggleAccordion = function(){
      if (inputIsOpen()) {
        setInputOpen(false);
      } else {
        openMainSection('input');
      }
    };

    var originalWorkspaceToggle = window.toggleAccordionSection;
    window.toggleAccordionSection = function(sectionId, forceState){
      if (sectionId === 'ai') {
        // AI 콘텐츠 시작 영역은 제목 클릭이나 강제 닫기 요청을 받아도 닫히지 않는 보호 영역이다.
        setWorkspaceOpen('ai', true);
        return;
      }
      if (sectionId === 'sns') {
        var shouldOpen = (forceState === null || forceState === undefined) ? !workspaceIsOpen(sectionId) : !!forceState;
        if (shouldOpen) openMainSection(sectionId);
        else setWorkspaceOpen(sectionId, false);
        return;
      }
      if (typeof originalWorkspaceToggle === 'function') {
        return originalWorkspaceToggle.apply(this, arguments);
      }
    };
  }

  function installButtonFlow(){
    if (window.__storymakerMainButtonFlowPatched) return;
    window.__storymakerMainButtonFlowPatched = true;

    document.addEventListener('click', function(e){
      var aiBtn = e.target.closest && (e.target.closest('.btn-ai-auto') || e.target.closest('button[onclick*="generateAIContentAutomatically"]'));
      var splitBtn = e.target.closest && e.target.closest('button[onclick*="parseChatGPTResult"]');

      if (aiBtn) {
        setTimeout(function(){ openMainSection('ai'); }, 30);
        setTimeout(function(){ openMainSection('ai'); }, 300);
      }
      if (splitBtn) {
        setTimeout(function(){ openMainSection('sns'); }, 30);
        setTimeout(function(){ openMainSection('sns'); }, 300);
      }
    }, true);
  }

  function installParsePatch(){
    if (window.__storymakerParseAccordionPatched) return;
    if (typeof window.parseChatGPTResult !== 'function') return;

    window.__storymakerParseAccordionPatched = true;
    var originalParse = window.parseChatGPTResult;
    window.parseChatGPTResult = async function(){
      var result = await originalParse.apply(this, arguments);
      setTimeout(function(){ openMainSection('sns'); }, 160);
      setTimeout(function(){ openMainSection('sns'); }, 600);
      return result;
    };
  }

  function closeInitialWorkSections(){
    if (window.__storymakerInitialAccordionClosed) return;
    var raw = $('#chatgpt-raw-input');
    var tabs = $('#parsed-tabs-container');
    var hasAiResult = !!(raw && String(raw.value || '').trim());
    var hasSnsResult = !!(tabs && tabs.style.display !== 'none' && tabs.children.length);

    if (!hasAiResult && !hasSnsResult) {
      // AI 콘텐츠 시작 영역은 초기 진입 시 펼쳐 둔다.
      setWorkspaceOpen('ai', true);
      setWorkspaceOpen('sns', false);
      try {
        localStorage.setItem('storymaker.workspace.ai.open', 'true');
        localStorage.setItem('storymaker.workspace.sns.open', 'false');
      } catch(e) {}
    }
  }

  function install(){
    installAccordionPatch();
    installButtonFlow();
    installParsePatch();
    closeInitialWorkSections();
  }

  document.addEventListener('DOMContentLoaded', function(){
    install();
    setTimeout(install, 300);
    setTimeout(install, 1000);
    setTimeout(install, 2500);
    setTimeout(function(){ window.__storymakerInitialAccordionClosed = true; }, 3200);
  });
  install();
})();