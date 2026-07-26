(function(){
  var path = (window.location && window.location.pathname) || '';
  if (path === '/storymaker' || path === '/storymaker/') {
    console.warn('[StoryMaker Debug] user_ui_cleanup_guard disabled on /storymaker for shake test');
    return;
  }
  function currentUser(){
    try { return JSON.parse(localStorage.getItem('storymaker_user') || '{}'); }
    catch(e) { return {}; }
  }
  function isAdminUser(){
    var user = currentUser();
    return user && user.role === 'admin';
  }
  function hidePromptWorkspace(){
    var prompt = document.getElementById('workspace-prompt');
    if (prompt) prompt.style.setProperty('display', 'none', 'important');
  }
  function syncAdminModeToggle(){
    var admin = isAdminUser();
    document.querySelectorAll('button').forEach(function(btn){
      var text = String(btn.textContent || '').replace(/\s+/g,' ').trim();
      if (text !== '?ъ슜??' && text !== '愿由ъ옄') return;
      var box = btn.closest('.mode-toggle, .role-toggle, .admin-toggle, .user-admin-toggle, .segment-toggle, .toggle-group, .pill-toggle, .tab-toggle') || btn.parentElement;
      if (!box) return;
      var labels = Array.prototype.map.call(box.querySelectorAll('button'), function(b){
        return String(b.textContent || '').replace(/\s+/g,' ').trim();
      });
      if (labels.indexOf('?ъ슜??') >= 0 && labels.indexOf('愿由ъ옄') >= 0) {
        if (!admin) box.style.setProperty('display', 'none', 'important');
        else box.style.removeProperty('display');
      }
    });
  }
  function applyCleanup(){
    hidePromptWorkspace();
    syncAdminModeToggle();
  }
  window.applyStoryMakerUserUiCleanup = applyCleanup;
  document.addEventListener('DOMContentLoaded', function(){
    applyCleanup();
    setTimeout(applyCleanup, 300);
    setTimeout(applyCleanup, 1000);
    setTimeout(applyCleanup, 2500);
  });
  var observer = new MutationObserver(function(){ applyCleanup(); });
  document.addEventListener('DOMContentLoaded', function(){
    observer.observe(document.body, { childList:true, subtree:true });
  });
})();