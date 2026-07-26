(function(){
  function $(s,r){return (r||document).querySelector(s)}
  function $all(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
  function esc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  function api(url,opt){return (window.fetchWithAuth||window.fetch)(url,opt||{})}

  function addCss(){
    if($('#refLookupStyle'))return;
    var st=document.createElement('style');
    st.id='refLookupStyle';
    st.textContent='\
.ref-entry-shell{display:flex!important;flex-direction:column!important;gap:10px!important;width:100%!important;margin:0 0 12px!important;box-sizing:border-box!important}\
.ref-entry-toolbar{display:grid!important;grid-template-columns:auto auto minmax(180px,1fr)!important;align-items:center!important;gap:10px!important;width:100%!important;min-width:0!important;box-sizing:border-box!important}\
.ref-entry-label{display:inline-flex!important;align-items:center!important;gap:6px!important;min-width:max-content!important;white-space:nowrap!important}\
.ref-entry-label .label-with-help{display:inline-flex!important;align-items:center!important;gap:6px!important;margin:0!important}\
.ref-entry-label label,.ref-entry-label .step-label-inline{display:inline-flex!important;align-items:center!important;margin:0!important;white-space:nowrap!important}\
.ref-entry-main{width:100%!important;min-width:0!important;box-sizing:border-box!important}\
.ref-entry-main textarea{display:block!important;width:100%!important;min-height:7.5em!important;box-sizing:border-box!important}\
.ref-lookup-toggle{width:auto!important;min-width:110px!important;white-space:nowrap!important;flex:0 0 auto!important}\
.ref-lookup-row{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;align-items:center!important;gap:8px!important;width:100%!important;min-width:0!important;box-sizing:border-box!important}\
.ref-lookup-row input{width:100%!important;min-width:0!important;margin:0!important;box-sizing:border-box!important}\
.ref-lookup-row button{width:auto!important;white-space:nowrap!important;flex:0 0 auto!important}\
.ref-source-slot{display:inline-flex!important;align-items:center!important;justify-content:flex-end!important;min-width:0!important}\
.ref-source-slot .ref-source-open{width:auto!important;white-space:nowrap!important}\
.ref-list{display:none!important;flex-direction:column!important;gap:8px!important;width:100%!important;max-width:100%!important;margin:0!important;padding:10px!important;border:1px solid rgba(56,189,248,.20)!important;border-radius:14px!important;background:rgba(2,6,23,.28)!important;box-sizing:border-box!important;overflow:visible!important;white-space:normal!important}\
.ref-list.is-visible{display:flex!important}\
.ref-item{border:1px solid rgba(148,163,184,.22)!important;border-radius:12px!important;background:rgba(15,23,42,.65)!important;padding:9px 10px!important;width:100%!important;max-width:none!important;min-width:0!important;box-sizing:border-box!important;overflow:hidden!important}\
.ref-title{font-weight:900!important;color:#fff!important;margin-bottom:3px!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important}\
.ref-snippet{font-size:12px!important;color:#aebdd2!important;line-height:1.45!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:normal!important}\
.ref-actions{display:flex!important;gap:6px!important;margin-top:7px!important;flex-wrap:wrap!important}\
.ref-actions button{width:auto!important;box-shadow:none!important}\
.ref-detail{display:none;margin-top:10px;padding:10px;border-radius:12px;background:rgba(2,6,23,.42);font-size:13px;color:#dbeafe;line-height:1.65;white-space:pre-line}\
.ref-item.open .ref-detail{display:block}\
@media(max-width:720px){.ref-entry-toolbar{grid-template-columns:1fr!important;gap:8px!important}.ref-entry-label{min-width:0!important}.ref-lookup-toggle{width:100%!important}.ref-source-slot{justify-content:stretch!important}.ref-source-slot .ref-source-open.show{width:100%!important}}';
    document.head.appendChild(st);
  }

  function dataList(res){
    var d=res&&res.data?res.data:res;
    return d.items||d.results||d.blogs||d.posts||[];
  }
  function itemUrl(it){return it.url||it.link||it.post_url||it.blog_url||''}
  function itemTitle(it){return it.title||it.name||it.post_title||'제목 없음'}
  function itemText(it){return it.summary||it.snippet||it.description||it.content||''}
  function lineBreakText(s){return String(s||'').replace(/([.!?。？！]|다\.|요\.|죠\.|니다\.)\s*/g,'$1\n').replace(/\n{3,}/g,'\n\n').trim()}

  function findLabelWrap(ref){
    var label=document.querySelector('label[for="reference_text"]');
    if(label){
      return label.closest('.label-with-help')||label;
    }
    var prev=ref.previousElementSibling;
    if(prev && /참고자료/.test(prev.textContent||'')) return prev;
    return null;
  }

  function showList(html){
    var list=$('#refList');
    if(!list)return;
    list.innerHTML=html;
    list.classList.add('is-visible');
  }

  function hideList(){
    var list=$('#refList');
    if(!list)return;
    list.innerHTML='';
    list.classList.remove('is-visible');
  }

  function install(){
    var ref=$('#reference_text');
    if(!ref||$('#refLookupWrap'))return;
    addCss();

    var parent=ref.parentNode;
    var labelBox=findLabelWrap(ref);
    var shell=document.createElement('div');
    shell.id='refLookupWrap';
    shell.className='ref-entry-shell';

    var toolbar=document.createElement('div');
    toolbar.className='ref-entry-toolbar';

    var toggle=document.createElement('button');
    toggle.type='button';
    toggle.className='ref-lookup-toggle';
    toggle.id='refLookupToggle';
    toggle.textContent='글감 조회';

    var labelSlot=document.createElement('div');
    labelSlot.className='ref-entry-label';

    var searchRow=document.createElement('div');
    searchRow.className='ref-lookup-row';
    searchRow.innerHTML='<input type="text" id="refKeyword" placeholder="예: 울산 욕실 수리"><button type="button" id="refSearchBtn">검색</button>';

    var list=document.createElement('div');
    list.id='refList';
    list.className='ref-list';

    var main=document.createElement('div');
    main.className='ref-entry-main';

    var anchor=(labelBox && labelBox.parentNode===parent) ? labelBox : ref;
    parent.insertBefore(shell,anchor);

    if(labelBox){
      labelSlot.appendChild(labelBox);
    }else{
      labelSlot.innerHTML='<label for="reference_text"><span class="step-label-inline">참고자료 입력</span></label>';
    }

    toolbar.appendChild(toggle);
    toolbar.appendChild(labelSlot);
    toolbar.appendChild(searchRow);
    shell.appendChild(toolbar);
    shell.appendChild(list);
    main.appendChild(ref);
    shell.appendChild(main);

    toggle.onclick=function(e){
      e.preventDefault();
      var kw=$('#refKeyword');
      if(list.innerHTML.trim()) list.classList.toggle('is-visible');
      if(kw) kw.focus();
    };
    $('#refSearchBtn').onclick=function(){ search(); };
    $('#refKeyword').addEventListener('keydown',function(e){
      if(e.key==='Enter'){
        e.preventDefault();
        search();
      }
    });
  }

  async function search(){
    var kw=($('#refKeyword')||{}).value||'';
    kw=kw.trim();
    if(!kw){showList('<div class="ref-snippet">키워드를 하나 입력해 주세요.</div>');return}
    showList('<div class="ref-snippet">블로그 상위 글을 찾는 중입니다...</div>');
    try{
      var r=await api('/api/content-ideas/naver-blog/search?keyword='+encodeURIComponent(kw)+'&limit=5',{method:'GET'});
      var j=await r.json();
      var arr=dataList(j).slice(0,5);
      if(!arr.length){showList('<div class="ref-snippet">검색 결과가 없습니다.</div>');return}
      showList(arr.map(function(it,i){
        var title=itemTitle(it), sn=itemText(it), url=itemUrl(it);
        return '<div class="ref-item" data-i="'+i+'" data-url="'+esc(url)+'"><div class="ref-title">'+esc(title)+'</div><div class="ref-snippet">'+esc(sn).slice(0,140)+'</div><div class="ref-actions"><button type="button" data-act="detail">자세히 보기</button><button type="button" data-act="select">선택</button></div><div class="ref-detail"></div></div>';
      }).join(''));
      $all('.ref-item',$('#refList')).forEach(function(el){el._data=arr[Number(el.getAttribute('data-i'))]});
      $('#refList').onclick=handleList;
    }catch(e){
      showList('<div class="ref-snippet">검색 중 문제가 생겼습니다.</div>');
    }
  }

  async function handleList(e){
    var btn=e.target.closest('button'); if(!btn)return;
    var item=e.target.closest('.ref-item'); if(!item)return;
    var act=btn.getAttribute('data-act');
    if(act==='detail')await detail(item);
    if(act==='select')await selectItem(item);
  }

  async function detail(item){
    $all('.ref-item').forEach(function(x){if(x!==item)x.classList.remove('open')});
    var box=$('.ref-detail',item);
    item.classList.add('open');
    if(box.getAttribute('data-loaded'))return;
    box.textContent='본문을 불러오는 중입니다...';
    var url=item.getAttribute('data-url');
    try{
      var r=await api('/api/content-ideas/naver-blog/extract?url='+encodeURIComponent(url),{method:'GET'});
      var j=await r.json();
      var d=j.data&&j.data.data?j.data.data:(j.data||j);
      var picked=d.item||d;
      var body=picked.full_text||picked.content||picked.text||picked.summary||picked.excerpt||d.full_text||d.content||d.text||d.summary||itemText(item._data)||'';
      box.textContent=lineBreakText(String(body));
      box.setAttribute('data-loaded','1');
    }catch(e){
      box.textContent=itemText(item._data).slice(0,700)||'본문을 불러오지 못했습니다.';
    }
  }

  async function selectItem(item){
    var ref=$('#reference_text'); if(!ref)return;
    var title=itemTitle(item._data), brief=itemText(item._data), detail=$('.ref-detail',item).textContent||'';
    var sourceUrl=item.getAttribute('data-url')||itemUrl(item._data)||'';
    var body=detail||brief||'';

    if(sourceUrl){
      try{
        ref.value='선택한 원문 전체를 불러오는 중입니다...';
        ref.dispatchEvent(new Event('input',{bubbles:true}));
        var r=await api('/api/content-ideas/naver-blog/extract?url='+encodeURIComponent(sourceUrl),{method:'GET'});
        var j=await r.json();
        var d=j.data&&j.data.data?j.data.data:(j.data||j);
        var picked=d.item||d;
        body=picked.full_text||picked.content||picked.text||picked.summary||picked.excerpt||d.full_text||d.content||d.text||d.summary||body;
      }catch(e){
        body=body||brief||'';
      }
    }

    var val=lineBreakText(String(body||''))+'\n\n출처: '+title+'\n원문 링크: '+sourceUrl;
    ref.value=val;
    ref.dispatchEvent(new Event('input',{bubbles:true}));
    ref.rows=8;
    ref.style.minHeight='14em';
    ref.style.height='auto';
    hideList();
    ref.scrollIntoView({behavior:'smooth',block:'center'});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
  setTimeout(install,1000);
})();