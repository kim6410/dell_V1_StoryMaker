(function(){
  function isPc(){ return window.matchMedia && window.matchMedia('(min-width: 761px)').matches; }

  function applyPcInnerAlign(){
    if(!isPc()) return;

    var toolbar=document.querySelector('.workspace-toolbar');
    if(toolbar){
      toolbar.style.setProperty('display','flex','important');
      toolbar.style.setProperty('justify-content','flex-start','important');
      toolbar.style.setProperty('align-items','center','important');
      toolbar.style.setProperty('gap','2cm','important');
      toolbar.style.setProperty('flex-wrap','wrap','important');

      var left=toolbar.children && toolbar.children[0];
      var right=toolbar.children && toolbar.children[1];
      if(left){
        left.style.setProperty('flex','0 0 auto','important');
        left.style.setProperty('max-width','none','important');
      }
      if(right){
        right.style.setProperty('display','flex','important');
        right.style.setProperty('align-items','center','important');
        right.style.setProperty('justify-content','flex-start','important');
        right.style.setProperty('gap','12px','important');
        right.style.setProperty('margin-left','0','important');
        right.style.setProperty('margin-right','0','important');
        right.style.setProperty('flex','0 0 auto','important');
        right.style.setProperty('max-width','none','important');
      }
    }

    var inputHead=document.querySelector('#input-card > h2.heading-with-help');
    var acc=document.querySelector('#accordion-icon');
    if(inputHead){
      inputHead.style.setProperty('display','flex','important');
      inputHead.style.setProperty('justify-content','flex-start','important');
      inputHead.style.setProperty('align-items','center','important');
      inputHead.style.setProperty('gap','2cm','important');
      inputHead.style.setProperty('flex-wrap','nowrap','important');
    }
    if(acc){
      acc.style.setProperty('margin-left','0','important');
      acc.style.setProperty('flex','0 0 auto','important');
    }

    var heroArrow=document.querySelector('#sm-header-podcast-arrow');
    var heroHeader=document.querySelector('.container > header');
    if(heroHeader){
      heroHeader.style.setProperty('position','relative','important');
    }
    if(heroArrow){
      heroArrow.style.setProperty('position','absolute','important');
      heroArrow.style.setProperty('right','2cm','important');
      heroArrow.style.setProperty('top','50%','important');
      heroArrow.style.setProperty('transform','translateY(-50%)','important');
      heroArrow.style.setProperty('margin','0','important');
    }

    var settingButtons=Array.prototype.slice.call(document.querySelectorAll('button')).filter(function(b){
      return ((b.innerText||b.textContent||'').trim()==='설정');
    });
    settingButtons.forEach(function(b){
      var p=b.parentElement;
      if(p){
        p.style.setProperty('display','flex','important');
        p.style.setProperty('justify-content','flex-start','important');
        p.style.setProperty('gap','2cm','important');
      }
      b.style.setProperty('margin-left','2cm','important');
      b.style.setProperty('margin-right','auto','important');
    });

    Array.prototype.slice.call(document.querySelectorAll('*')).forEach(function(el){
      var txt=(el.innerText||'').trim();
      if(/^\d{1,2}:\d{2}\s*\/\s*[\d,]+자\s*입력됨$/.test(txt)){
        el.style.setProperty('margin-left','2cm','important');
        el.style.setProperty('margin-right','auto','important');
        el.style.setProperty('display','inline-flex','important');
      }
    });
  }

  function bind(){
    applyPcInnerAlign();
    setTimeout(applyPcInnerAlign,300);
    setTimeout(applyPcInnerAlign,900);
    setTimeout(applyPcInnerAlign,1800);
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',bind); else bind();
  window.addEventListener('resize',applyPcInnerAlign);
})();
