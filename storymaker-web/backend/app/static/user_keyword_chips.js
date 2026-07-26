(function(){
  var STOP=['은','는','이','가','을','를','의','에','에서','으로','로','와','과','도','만','까지','부터','에게','한테','께','하고','그리고','하지만','그래서','오늘','이번','저희','우리','합니다','했습니다','있습니다','있는','없는','같은','때문','정도','경우','내용','작업','진행'];
  function $(s,r){return (r||document).querySelector(s)}
  function words(text){
    var freq={};
    String(text||'').replace(/[A-Za-z0-9_]+|[가-힣]{2,}/g,function(w){
      w=w.trim();
      if(w.length<2||STOP.indexOf(w)>=0)return;
      w=w.replace(/(으로|에서|에게|부터|까지|하고|처럼|보다|이며|이고|입니다|합니다|했습니다|했다|했고|하는|있는|없는|은|는|이|가|을|를|의|에|로|도|만)$/,'');
      if(w.length<2||STOP.indexOf(w)>=0)return;
      freq[w]=(freq[w]||0)+1;
    });
    return Object.keys(freq).sort(function(a,b){return freq[b]-freq[a]||b.length-a.length}).slice(0,7);
  }
  function style(){
    if($('#ukcStyle'))return;
    var st=document.createElement('style');
    st.id='ukcStyle';
    st.textContent='.ukc-line{margin:8px 0 0;color:#9fb2c9;font-size:12px;line-height:1.55}.ukc-line b{color:#dff7ff;font-weight:800}.ukc-line span{color:#cfe8ff}';
    document.head.appendChild(st);
  }
  function render(list){
    var btn=$('#extractKeywordsBtn')||Array.from(document.querySelectorAll('button')).find(function(b){return (b.textContent||'').indexOf('키워드 빈도 추출')>=0});
    if(!btn)return;
    var box=$('#ukcBox');
    if(!box){box=document.createElement('div');box.id='ukcBox';box.className='ukc-line';(btn.parentElement||btn).insertAdjacentElement('afterend',box)}
    if(!list.length){box.innerHTML='<b>추천 키워드:</b> 아직 부족합니다.';return}
    box.innerHTML='<b>추천 키워드:</b> <span>'+list.join(' · ')+'</span> &nbsp;|&nbsp; 자동으로 글 생성에 활용됩니다.';
  }
  function collect(){
    var text='';
    document.querySelectorAll('textarea').forEach(function(el){text+=' '+(el.value||el.textContent||'')});
    return text;
  }
  function boot(){
    style();
    document.addEventListener('click',function(e){
      var b=e.target.closest&&e.target.closest('button');
      if(!b)return;
      if((b.textContent||'').indexOf('키워드 빈도 추출')>=0){
        setTimeout(function(){render(words(collect()))},350);
      }
    },true);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();