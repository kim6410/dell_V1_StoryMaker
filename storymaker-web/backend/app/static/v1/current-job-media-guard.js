(function(){
  'use strict';
  const GUARD_KEY = 'storymaker_v1_current_source_job';
  const HANDOFF_KEYS = [
    'storymaker_latest_podcast_for_slideshow',
    'storymaker_auto_run_shortform',
    'storymaker_consumed_podcast_handoff',
    'podcast_generation_history'
  ];
  const IDB_NAME = 'storymaker-browser-media';
  const STORE_NAME = 'podcasts';

  function safeRemoveStorage(){
    for (const key of HANDOFF_KEYS) {
      try { localStorage.removeItem(key); } catch(_) {}
      try { sessionStorage.removeItem(key); } catch(_) {}
    }
  }

  function clearIndexedDb(){
    try {
      const req = indexedDB.open(IDB_NAME);
      req.onsuccess = () => {
        const db = req.result;
        try {
          if (db.objectStoreNames.contains(STORE_NAME)) {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            tx.objectStore(STORE_NAME).clear();
            tx.oncomplete = () => db.close();
            tx.onerror = () => db.close();
          } else {
            db.close();
          }
        } catch (_) { try { db.close(); } catch(__) {} }
      };
      req.onerror = () => {};
    } catch (_) {}
  }

  function activateSource(sourceId){
    if (!sourceId) return;
    let previous = '';
    try { previous = localStorage.getItem(GUARD_KEY) || ''; } catch(_) {}
    if (previous === sourceId) return;
    safeRemoveStorage();
    clearIndexedDb();
    try { localStorage.setItem(GUARD_KEY, sourceId); } catch(_) {}
    try { console.info('[V1-CURRENT-JOB-GUARD] new source job', sourceId); } catch(_) {}
  }

  function extractSource(value){
    const s = String(value || '');
    const m = s.match(/storymaker_main_\d{14}/);
    return m ? m[0] : '';
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = function(input, init){
    try {
      const url = typeof input === 'string' ? input : (input && input.url);
      const source = extractSource(url);
      if (source) activateSource(source);
    } catch(_) {}
    return originalFetch(input, init).then(function(response){
      try {
        const clone = response.clone();
        clone.json().then(function(data){
          try {
            const text = JSON.stringify(data);
            const source = extractSource(text);
            if (source) activateSource(source);
          } catch(_) {}
        }).catch(function(){});
      } catch(_) {}
      return response;
    });
  };
})();

