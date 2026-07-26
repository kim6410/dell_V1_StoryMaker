(function(){
  function addStyle(){
    if(document.getElementById('refDetailFixStyle')) return;
    var st=document.createElement('style');
    st.id='refDetailFixStyle';
    st.textContent='\
      .ref-detail{\
        display:none;\
        margin-top:12px!important;\
        padding:14px 16px!important;\
        border-radius:14px!important;\
        background:rgba(2,6,23,.46)!important;\
        color:#e5efff!important;\
        font-size:15px!important;\
        line-height:1.72!important;\
        white-space:pre-line!important;\
        min-height:15.5em!important;\
        max-height:22em!important;\
        overflow-y:auto!important;\
      }\
      .ref-item.open .ref-detail{display:block!important;}\
    ';
    document.head.appendChild(st);
  }
  function patchDetailOpen(){
    document.addEventListener('click',function(e){
      var btn=e.target.closest('button');
      if(!btn) return;
      var label=(btn.textContent||'').trim();
      if(label.indexOf('자세히 보기')>=0){
        setTimeout(function(){
          document.querySelectorAll('.ref-item').forEach(function(item){
            var detail=item.querySelector('.ref-detail');
            if(!detail) return;
            if(item.classList.contains('open')){
              detail.style.setProperty('display','block','important');
              detail.style.setProperty('min-height','15.5em','important');
              detail.style.setProperty('max-height','22em','important');
              detail.style.setProperty('overflow-y','auto','important');
              detail.style.setProperty('line-height','1.72','important');
            }else{
              detail.style.setProperty('display','none','important');
            }
          });
        },250);
      }
    },true);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){addStyle();patchDetailOpen();});
  else{addStyle();patchDetailOpen();}
})();