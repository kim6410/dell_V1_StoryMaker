(function(){
  'use strict';

  var progressLogBuffer = [];
  var lastStageText = '';
  var originalSetProgress = window.setProgress;
  var originalSetRunning = window.setRunning;
  var lineSeq = 0;

  function $(selector){ return document.querySelector(selector); }

  function nowTime(){
    var d = new Date();
    return String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0') + ':' + String(d.getSeconds()).padStart(2,'0');
  }

  function sanitizeRawLog(line){
    var str = String(line || '').trim();
    if (!str) return '';

    // 내부 서버 경로는 화면에 그대로 노출하지 않고 짧게 치환한다.
    str = str.replace(/\/home\/[^\s"']+/g, '[server-path]');
    str = str.replace(/\/workspace\/[^\s"']+/g, '[workspace-path]');
    str = str.replace(/저장 위치\s*:\s*[^\n]+/g, '저장 위치: [server-path]');
    str = str.replace(/TEMP_DIR\s*=\s*[^\s]+/g, 'TEMP_DIR=[temp]');

    return str;
  }

  function renderLogs(){
    var logs = $('#logs');
    if (!logs) return;
    logs.textContent = progressLogBuffer.length ? progressLogBuffer.join('\n') : '생성 준비가 완료되었습니다.';
    logs.scrollTop = logs.scrollHeight;
  }

  function appendRawLog(line, force){
    var msg = sanitizeRawLog(line);
    if (!msg) return;

    // 같은 문장이 너무 빠르게 반복될 때도 작업감이 보이도록 완전 제거하지 않고 최근 3개 연속 중복만 줄인다.
    var last = progressLogBuffer[progressLogBuffer.length - 1] || '';
    var prev = progressLogBuffer[progressLogBuffer.length - 2] || '';
    var compactLast = last.replace(/^\[[0-9:]+\]\s*/, '');
    var compactPrev = prev.replace(/^\[[0-9:]+\]\s*/, '');
    if (!force && compactLast === msg && compactPrev === msg) return;

    lineSeq += 1;
    progressLogBuffer.push('[' + nowTime() + '] ' + msg);
    if (progressLogBuffer.length > 220) progressLogBuffer = progressLogBuffer.slice(-220);
    renderLogs();
  }

  function resetProgressLog(){
    progressLogBuffer = [];
    lastStageText = '';
    lineSeq = 0;
    renderLogs();
  }

  window.setLog = function(lines){
    var arr = Array.isArray(lines) ? lines : [lines];
    arr.forEach(function(line){
      var text = String(line || '');
      text.split(/\r?\n/).forEach(function(part){ appendRawLog(part, false); });
    });
    renderLogs();
  };

  window.setProgress = function(value, stage){
    if (typeof originalSetProgress === 'function') {
      originalSetProgress(value, stage || '대기 중');
    } else {
      var n = Math.max(0, Math.min(100, Number(value) || 0));
      var progress = $('#progress');
      var percent = $('#percent');
      var stageEl = $('#stage');
      var track = document.querySelector('.progress-track');
      if (progress) progress.style.width = n + '%';
      if (percent) percent.textContent = Math.round(n) + '%';
      if (stageEl) stageEl.textContent = stage || '대기 중';
      if (track) track.setAttribute('aria-valuenow', n);
    }

    if (stage && stage !== '대기 중' && stage !== lastStageText) {
      lastStageText = stage;
      appendRawLog('진행 상태: ' + stage, true);
    }
  };

  window.setRunning = function(on){
    if (typeof originalSetRunning === 'function') originalSetRunning(on);

    var submit = $('#submit');
    var cancel = $('#cancel');
    if (submit) {
      submit.disabled = !!on;
      submit.textContent = on ? '팟캐스트 생성중' : '팟캐스트 생성';
    }
    if (cancel) cancel.disabled = !on;

    if (on) {
      resetProgressLog();
      appendRawLog('팟캐스트 생성 작업을 시작합니다.', true);
      appendRawLog('대본, 음성, 배경음악 설정을 확인합니다.', true);
    } else {
      appendRawLog('작업 상태 업데이트가 종료되었습니다.', false);
    }
  };

  document.addEventListener('click', function(e){
    var submit = e.target && e.target.closest ? e.target.closest('#submit') : null;
    if (submit) {
      window.setTimeout(function(){
        if (submit.disabled) submit.textContent = '팟캐스트 생성중';
      }, 30);
    }
  }, true);
})();
