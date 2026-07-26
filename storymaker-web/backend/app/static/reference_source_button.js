(function(){
  function ensureStyle(){
    if(document.getElementById('refSourceButtonStyle')) return;
    var st=document.createElement('style');
    st.id='refSourceButtonStyle';
    st.textContent='\
.ref-selected-source-bar{display:none!important;align-items:center!important;justify-content:space-between!important;gap:10px!important;width:100%!important;margin-top:8px!important;padding:8px 10px!important;border:1px solid rgba(56,189,248,.22)!important;border-radius:10px!important;background:rgba(15,23,42,.46)!important;box-sizing:border-box!important}\
.ref-selected-source-bar.show{display:flex!important}\
.ref-selected-source-title{min-width:0!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;color:#aebdd2!important;font-size:12px!important;line-height:1.4!important}\
.ref-selected-source-title b{color:#e5efff!important;font-weight:800!important}\
.ref-source-open{display:inline-flex!important;margin:0!important;width:auto!important;white-space:nowrap!important;box-shadow:none!important;flex:0 0 auto!important}\
@media(max-width:720px){.ref-selected-source-bar{align-items:stretch!important;flex-direction:column!important}.ref-selected-source-title{white-space:normal!important}.ref-source-open{width:100%!important}}';
    document.head.appendChild(st);
  }

  function ensureSourceBar(){
    var ref=document.querySelector('#reference_text');
    if(!ref) return null;
    var bar=document.querySelector('#refSelectedSourceBar');
    if(bar) return bar;

    bar=document.createElement('div');
    bar.id='refSelectedSourceBar';
    bar.className='ref-selected-source-bar';
    bar.innerHTML='<div class="ref-selected-source-title" id="refSelectedSourceTitle"><b>선택 출처:</b> 참고자료를 선택하면 표시됩니다.</div><button type="button" id="refSourceOpenBtn" class="ref-source-open">원본 확인</button>';

    if(ref.parentNode){
      if(ref.nextSibling){
        ref.parentNode.insertBefore(bar,ref.nextSibling);
      }else{
        ref.parentNode.appendChild(bar);
      }
    }

    var btn=bar.querySelector('#refSourceOpenBtn');
    btn.addEventListener('click',function(){
      var url=btn.getAttribute('data-url');
      if(url) window.open(url,'_blank','noopener,noreferrer');
    });
    return bar;
  }

  function showSource(item){
    var bar=ensureSourceBar();
    if(!bar || !item) return;
    var btn=bar.querySelector('#refSourceOpenBtn');
    var titleBox=bar.querySelector('#refSelectedSourceTitle');
    var titleEl=item.querySelector('.ref-title');
    var title=(titleEl && titleEl.textContent || '네이버 블로그 참고자료').trim();
    var url=item.getAttribute('data-url')||'';
    if(url){
      btn.setAttribute('data-url',url);
      titleBox.innerHTML='<b>선택 출처:</b> '+title;
      bar.classList.add('show');
    }
  }

  function bind(){
    ensureStyle();
    ensureSourceBar();
    document.addEventListener('click',function(e){
      var b=e.target.closest('button');
      if(!b || (b.textContent||'').trim()!=='선택') return;
      var item=e.target.closest('.ref-item');
      if(!item) return;
      setTimeout(function(){ showSource(item); },450);
    },true);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
  setTimeout(bind,1000);
})();