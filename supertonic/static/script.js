// =============================================================================
// 전역 상태
// =============================================================================
let currentProject = {
    client: '강경숯불바베큐',
    date: '2026-03-04',
    title: '봄비가내리는저녁'
};

let currentJobId = null;
let currentHistory = [];
let currentHistoryIndex = -1;
let selectedFiles = [];
let externalSites = [];

// WebSocket 연결
let ws = null;

// =============================================================================
// DOM 요소 안전하게 가져오는 함수들 (DOM 로딩 문제 해결)
// =============================================================================
function getClientInput() { return document.getElementById('clientName'); }
function getDateInput() { return document.getElementById('projectDate'); }
function getTitleInput() { return document.getElementById('projectTitle'); }
function getProjectPreview() { return document.getElementById('projectPreview'); }

function getScriptInput() { return document.getElementById('scriptInput'); }
function getMaleVoice() { return document.getElementById('maleVoice'); }
function getFemaleVoice() { return document.getElementById('femaleVoice'); }
function getSpeed() { return document.getElementById('speed'); }
function getSpeedValue() { return document.getElementById('speedValue'); }

function getVoiceVolume() { return document.getElementById('voiceVolume'); }
function getVoiceVolumeValue() { return document.getElementById('voiceVolumeValue'); }
function getMusicVolume() { return document.getElementById('musicVolume'); }
function getMusicVolumeValue() { return document.getElementById('musicVolumeValue'); }
function getAudioPlayer() { return document.getElementById('audioPlayer'); }
function getMusicRandom() { return document.getElementById('musicRandom'); }
function getRunPodcastBtn() { return document.getElementById('runPodcastBtn'); }

function getPodcastProgress() { return document.getElementById('podcastProgress'); }
function getPodcastProgressFill() { return document.getElementById('podcastProgressFill'); }
function getPodcastStage() { return document.getElementById('podcastStage'); }
function getPodcastEta() { return document.getElementById('podcastEta'); }
function getPodcastLog() { return document.getElementById('podcastLog'); }
function getPodcastResult() { return document.getElementById('podcastResult'); }
function getPodcastMp3Link() { return document.getElementById('podcastMp3Link'); }
function getPodcastSrtLink() { return document.getElementById('podcastSrtLink'); }

function getDropzone() { return document.getElementById('dropzone'); }
function getFileInput() { return document.getElementById('fileInput'); }
function getFolderInput() { return document.getElementById('folderInput'); }
function getSelectFilesBtn() { return document.getElementById('selectFilesBtn'); }
function getSelectFolderBtn() { return document.getElementById('selectFolderBtn'); }
function getFileList() { return document.getElementById('fileList'); }
function getRunSlideshowBtn() { return document.getElementById('runSlideshowBtn'); }

function getSlideshowProgress() { return document.getElementById('slideshowProgress'); }
function getSlideshowProgressFill() { return document.getElementById('slideshowProgressFill'); }
function getSlideshowStage() { return document.getElementById('slideshowStage'); }
function getSlideshowEta() { return document.getElementById('slideshowEta'); }
function getSlideshowLog() { return document.getElementById('slideshowLog'); }

function getHistoryList() { return document.getElementById('historyList'); }
function getHistorySearch() { return document.getElementById('historySearch'); }

function getMobilePlayer() { return document.getElementById('mobilePlayer'); }
function getCurrentVideoTitle() { return document.getElementById('currentVideoTitle'); }
function getPrevVideoBtn() { return document.getElementById('prevVideoBtn'); }
function getNextVideoBtn() { return document.getElementById('nextVideoBtn'); }
function getOpenVideoFolderBtn() { return document.getElementById('openVideoFolderBtn'); }

// =============================================================================
// 상호/전화번호 관련 함수
// =============================================================================
function getBrandName() { return document.getElementById('brandName'); }
function getPhoneNumber() { return document.getElementById('phoneNumber'); }

// 외부 도구 관련 (매번 새로 조회)
function getSiteSelector() { return document.getElementById('siteSelector'); }
function getCustomUrl() { return document.getElementById('customUrl'); }
function getToolToggle() { return document.getElementById('toolToggle'); }
function getExternalToolContent() { return document.getElementById('externalToolContent'); }
function getExternalFrame() { return document.getElementById('externalFrame'); }
function getIframeFallback() { return document.getElementById('iframeFallback'); }
function getYoutubeUrl() { return document.getElementById('youtubeUrl'); }
function getYoutubeAutoplay() { return document.getElementById('youtubeAutoplay'); }
function getYoutubeLoop() { return document.getElementById('youtubeLoop'); }
function getYoutubeContainer() { return document.getElementById('youtubeContainer'); }
function getUrlIframeContainer() { return document.getElementById('urlIframeContainer'); }

// =============================================================================
// 초기화
// =============================================================================
async function init() {
    console.log('앱 초기화 시작...');

    // DOM 요소들 다시 확인
    const clientInput = getClientInput();
    const dateInput = getDateInput();
    const titleInput = getTitleInput();
    const projectPreview = getProjectPreview();
    const speed = getSpeed();
    const speedValue = getSpeedValue();
    const selectFilesBtn = getSelectFilesBtn();
    const selectFolderBtn = getSelectFolderBtn();
    const fileInput = getFileInput();
    const folderInput = getFolderInput();
    const runPodcastBtn = getRunPodcastBtn();
    const runSlideshowBtn = getRunSlideshowBtn();
    const historySearch = getHistorySearch();
    const prevVideoBtn = getPrevVideoBtn();
    const nextVideoBtn = getNextVideoBtn();
    const openVideoFolderBtn = getOpenVideoFolderBtn();
    const newProjectBtn = document.getElementById('newProjectBtn');
    const saveProjectBtn = document.getElementById('saveProjectBtn');

    // 프로젝트 정보 변경 감지
    if (clientInput) clientInput.addEventListener('input', updateProjectPreview);
    if (dateInput) dateInput.addEventListener('input', updateProjectPreview);
    if (titleInput) titleInput.addEventListener('input', updateProjectPreview);

    // 속도 슬라이더
    if (speed && speedValue) {
        speed.addEventListener('input', (e) => {
            speedValue.textContent = e.target.value;
        });
    }

    // 볼륨 슬라이더
    const voiceVolume = getVoiceVolume();
    const voiceVolumeValue = getVoiceVolumeValue();
    const musicVolume = getMusicVolume();
    const musicVolumeValue = getMusicVolumeValue();

    function syncVoiceVolume() {
        if (voiceVolume && voiceVolumeValue) voiceVolumeValue.textContent = Number(voiceVolume.value).toFixed(2);
    }
    function syncMusicVolume() {
        if (musicVolume && musicVolumeValue) musicVolumeValue.textContent = Number(musicVolume.value).toFixed(2);
    }

    if (voiceVolume) voiceVolume.addEventListener('input', syncVoiceVolume);
    if (musicVolume) musicVolume.addEventListener('input', syncMusicVolume);
    syncVoiceVolume();
    syncMusicVolume();

    // 히스토리 로드
    await loadHistory();

    // 외부 사이트 로드
    loadExternalSites();

    // 드래그앤드롭 이벤트
    setupDragAndDrop();

    // 파일 선택 버튼
    if (selectFilesBtn && fileInput) {
        selectFilesBtn.addEventListener('click', () => fileInput.click());
    }
    if (selectFolderBtn && folderInput) {
        selectFolderBtn.addEventListener('click', () => folderInput.click());
    }

    if (fileInput) fileInput.addEventListener('change', handleFileSelect);
    if (folderInput) folderInput.addEventListener('change', handleFileSelect);

    // 실행 버튼 이벤트 연결
    if (runPodcastBtn) {
        console.log('팟캐스트 버튼 찾음');
        runPodcastBtn.addEventListener('click', runPodcast);
    } else {
        console.log('팟캐스트 버튼 못 찾음');
    }

    if (runSlideshowBtn) {
        console.log('슬라이드쇼 버튼 찾음');
        runSlideshowBtn.addEventListener('click', runSlideshow);
    } else {
        console.log('슬라이드쇼 버튼 못 찾음');
    }

    // 새 프로젝트 버튼 이벤트
    if (newProjectBtn) {
        newProjectBtn.addEventListener('click', resetProject);
        console.log('새 프로젝트 버튼 찾음');
    }

    // 프로젝트 저장 버튼 이벤트
    if (saveProjectBtn) {
        saveProjectBtn.addEventListener('click', saveProject);
        console.log('프로젝트 저장 버튼 찾음');
    }

    // SLID_Maker 버튼 이벤트
    const openSlidMakerBtn = document.getElementById('openSlidMakerBtn');
    if (openSlidMakerBtn) {
        openSlidMakerBtn.addEventListener('click', openSlidMaker);
        console.log('SLID_Maker 버튼 찾음');
    }

    // 폴더 열기 버튼 이벤트
    if (openVideoFolderBtn) {
        openVideoFolderBtn.addEventListener('click', openCurrentVideoFolder);
    }

    // 🔥 프로필 초기화 (강화)
    console.log('프로필 초기화 중...');

    // 1. 프로필 선택기 업데이트
    updateProfileSelector();

    // 2. 프로필 이벤트 설정
    setupProfileEvents();

    // 3. 마지막 사용 프로필 로드 (약간 지연)
    setTimeout(() => {
        loadLastUsedProfile();
    }, 200);

    // 히스토리 검색
    if (historySearch) historySearch.addEventListener('input', filterHistory);

    // 프리뷰 컨트롤
    if (prevVideoBtn) prevVideoBtn.addEventListener('click', playPrevVideo);
    if (nextVideoBtn) nextVideoBtn.addEventListener('click', playNextVideo);

    // 주기적 히스토리 갱신 (100초)
    setInterval(loadHistory, 100000);

    // 외부도구 패널 초기 표시
    setTimeout(() => {
        console.log('외부도구 패널 초기화...');

        const externalToolContent = getExternalToolContent();
        const toolToggle = getToolToggle();

        if (externalToolContent) {
            externalToolContent.style.display = 'block';
            console.log('외부도구 패널 표시됨');
        } else {
            console.log('외부도구 패널 없음');
        }

        if (toolToggle) {
            toolToggle.textContent = '▼';
        }

        // 기본 URL 탭 활성화
        switchToolTab('url');

        console.log('모바일 프리뷰:', document.querySelector('.mobile-preview'));
    }, 500);
}


function updateProjectPreview() {
    const clientInput = getClientInput();
    const dateInput = getDateInput();
    const titleInput = getTitleInput();
    const projectPreview = getProjectPreview();
    
    if (!clientInput || !dateInput || !titleInput || !projectPreview) return;
    
    currentProject.client = clientInput.value || '업체명';
    currentProject.date = dateInput.value;
    currentProject.title = titleInput.value || '제목';
    
    const preview = `${currentProject.client}_${currentProject.date}_${currentProject.title}`;
    projectPreview.textContent = preview.replace(/\s+/g, '_');
    console.log('프로젝트 프리뷰 업데이트:', preview);
}

// =============================================================================
// 드래그앤드롭
// =============================================================================
function setupDragAndDrop() {
    const dropzone = getDropzone();
    const fileInput = getFileInput();
    
    if (!dropzone || !fileInput) return;
    
    dropzone.addEventListener('click', () => fileInput.click());
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = '#3b82f6';
    });
    
    dropzone.addEventListener('dragleave', () => {
        dropzone.style.borderColor = '#334155';
    });
    
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = '#334155';
        
        const items = e.dataTransfer.items;
        const files = [];
        
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item.kind === 'file') {
                const file = item.getAsFile();
                if (file.type.startsWith('image/')) {
                    files.push(file);
                }
            }
        }
        
        if (files.length > 0) {
            console.log('드래그된 파일 수:', files.length);
            handleFiles(files);
        } else {
            alert('이미지 파일만 드래그해주세요.');
        }
    });
}

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    console.log('선택된 파일 수:', files.length);
    
    // 이미지 파일만 필터링
    const imageFiles = files.filter(file => file.type.startsWith('image/'));
    
    if (imageFiles.length === 0) {
        alert('이미지 파일만 선택해주세요.');
        return;
    }
    
    handleFiles(imageFiles);
}

function handleFiles(files) {
    console.log('handleFiles 호출됨, 파일 수:', files.length);
    
    selectedFiles = files;
    updateFileList();
    
    const runSlideshowBtn = getRunSlideshowBtn();
    if (runSlideshowBtn) {
        runSlideshowBtn.disabled = false;
        console.log('슬라이드쇼 버튼 활성화됨');
    }
    
    console.log('파일 처리 완료:', selectedFiles.length, '개');
}

function updateFileList() {
    const fileList = getFileList();
    if (!fileList) return;
    
    fileList.innerHTML = '';
    
    if (selectedFiles.length === 0) {
        fileList.innerHTML = '<div style="color:#94a3b8;">선택된 파일 없음</div>';
        return;
    }
    
    selectedFiles.forEach((file, i) => {
        const div = document.createElement('div');
        div.textContent = `${i + 1}. ${file.name} (${(file.size / 1024).toFixed(1)}KB)`;
        div.style.color = '#e0e5f0';
        div.style.padding = '4px';
        div.style.borderBottom = '1px solid #334155';
        fileList.appendChild(div);
    });
    
    console.log('파일 목록 업데이트됨:', selectedFiles.length, '개');
}

// =============================================================================
// 팟캐스트 생성
// =============================================================================
async function runPodcast() {
    console.log('runPodcast 함수 실행됨!');
    console.log('현재 프로젝트 키:', getProjectPreview().textContent);
    
    const scriptInput = getScriptInput();
    const projectPreview = getProjectPreview();
    const maleVoice = getMaleVoice();
    const femaleVoice = getFemaleVoice();
    const speed = getSpeed();
    const musicRandom = getMusicRandom();
    const runPodcastBtn = getRunPodcastBtn();
    const podcastProgress = getPodcastProgress();
    const podcastResult = getPodcastResult();
    const podcastLog = getPodcastLog();
    
    if (!scriptInput || !projectPreview || !maleVoice || !femaleVoice || !speed || !musicRandom) {
        console.error('필수 요소를 찾을 수 없습니다');
        return;
    }
    
    const script = scriptInput.value.trim();
    if (!script) {
        alert('대본을 입력해주세요.');
        return;
    }
    
    console.log('대본 길이:', script.length);
    
    const formData = new FormData();
    formData.append('project_key', projectPreview.textContent);
    formData.append('script', script);
    formData.append('male_voice', maleVoice.value);
    formData.append('female_voice', femaleVoice.value);
    formData.append('speed', speed.value);
    formData.append('music_random', musicRandom.checked);
    formData.append('voice_volume', getVoiceVolume() ? getVoiceVolume().value : 1.0);
    formData.append('music_volume', getMusicVolume() ? getMusicVolume().value : 0.3);
    
    if (runPodcastBtn) runPodcastBtn.disabled = true;
    if (podcastProgress) podcastProgress.style.display = 'block';
    if (podcastResult) podcastResult.style.display = 'none';
    if (podcastLog) podcastLog.innerHTML = '';
    
    try {
        console.log('API 요청 시작...');
        const response = await fetch('/api/podcast/run', {
            method: 'POST',
            body: formData
        });
        
        console.log('응답 상태:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP 오류: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('응답 데이터:', data);
        
        currentJobId = data.job_id;
        
        // 폴링으로 상태 확인
        pollJobStatus(currentJobId, 'podcast');
        
    } catch (error) {
        console.error('Error:', error);
        if (podcastLog) {
            podcastLog.innerHTML += `<div style="color:#ff4444">오류: ${error.message}</div>`;
        }
        if (runPodcastBtn) runPodcastBtn.disabled = false;
    }
}

// =============================================================================
// 슬라이드쇼 생성
// =============================================================================
async function runSlideshow() {
    console.log('runSlideshow 함수 실행됨!');
    
    const projectPreview = getProjectPreview();
    const runSlideshowBtn = getRunSlideshowBtn();
    const slideshowProgress = getSlideshowProgress();
    const slideshowLog = getSlideshowLog();
    
    if (!projectPreview || !runSlideshowBtn || !slideshowProgress || !slideshowLog) {
        console.error('필수 요소를 찾을 수 없습니다');
        return;
    }
    
    if (selectedFiles.length === 0) {
        alert('이미지를 선택해주세요.');
        return;
    }
    
    console.log('선택된 이미지:', selectedFiles.length);
    
    const formData = new FormData();
    formData.append('project_key', projectPreview.textContent);
    formData.append('mp3_path', `/media/podcast/${projectPreview.textContent}.mp3`);
    formData.append('srt_path', `/media/podcast/${projectPreview.textContent}.srt`);
    formData.append('render_target', 'macmini');
    formData.append('brand_name', _el('wmBrandName')?.value || _el('brandName')?.value || '');
    formData.append('phone_number', _el('wmPhoneNumber')?.value || _el('phoneNumber')?.value || '');
    formData.append('brand_size', _el('wmBrandSize')?.value || '60');
    formData.append('phone_size', _el('wmPhoneSize')?.value || '43');
    formData.append('margin_bottom', _el('wmMarginBottom')?.value || '91');
    formData.append('box_enabled', !!_el('wmBoxEnabled')?.checked);
    formData.append('stroke_enabled', !!_el('wmStrokeEnabled')?.checked);
    formData.append('shadow_enabled', !!_el('wmShadowEnabled')?.checked);
    formData.append('subtitle_enabled', !!_el('subEnabled')?.checked);
    formData.append('subtitle_font_size', _el('subFontSize')?.value || '10');
    formData.append('subtitle_margin', _el('subMarginV')?.value || '30');
    formData.append('mm_sub_boost', _el('mmSubBoost')?.value || '0');
    formData.append('mm_sub_lift', _el('mmSubLift')?.value || '70');
    formData.append('mm_wm_lift', _el('mmWmLift')?.value || '0');
    formData.append('mm_wm_gap', _el('mmWmGap')?.value || '25');
    
    selectedFiles.forEach(file => {
        formData.append('images', file);
    });
    
    runSlideshowBtn.disabled = true;
    slideshowProgress.style.display = 'block';
    slideshowLog.innerHTML = '';
    
    try {
        console.log('API 요청 시작...');
        const response = await fetch('/api/slideshow/run', {
            method: 'POST',
            body: formData
        });
        
        console.log('응답 상태:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP 오류: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('응답 데이터:', data);
        
        currentJobId = data.job_id;
        
        // 폴링으로 상태 확인
        pollJobStatus(currentJobId, 'slideshow');
        
    } catch (error) {
        console.error('Error:', error);
        if (slideshowLog) {
            slideshowLog.innerHTML += `<div style="color:#ff4444">오류: ${error.message}</div>`;
        }
        runSlideshowBtn.disabled = false;
    }
}

// =============================================================================
// 작업 상태 폴링
// =============================================================================
function pollJobStatus(jobId, type) {
    console.log(`상태 폴링 시작: ${jobId} (${type})`);
    
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/api/jobs/${jobId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP 오류: ${response.status}`);
            }
            
            const job = await response.json();
            console.log(`작업 상태:`, job);
            
            if (type === 'podcast') {
                updatePodcastProgress(job);
            } else {
                updateSlideshowProgress(job);
            }
            
            if (job.status === 'completed' || job.status === 'failed') {
                console.log(`작업 완료: ${job.status}`);
                clearInterval(interval);
                
                if (job.status === 'completed' && type === 'podcast') {
                    const podcastResult = getPodcastResult();
                    const podcastMp3Link = getPodcastMp3Link();
                    const podcastSrtLink = getPodcastSrtLink();
                    const runSlideshowBtn = getRunSlideshowBtn();
                    
                    if (podcastResult) podcastResult.style.display = 'flex';
                    if (podcastMp3Link) {
                        podcastMp3Link.href = job.result.mp3_url;
                        console.log('MP3 링크:', podcastMp3Link.href);
                    }
                    if (podcastSrtLink) podcastSrtLink.href = job.result.srt_url;
                    
                    // 현재 프로필에 SRT 내용 저장
                    const profileName = document.getElementById('profileSelector').value;
                    if (profileName && profileName !== 'default') {
                        const scriptContent = document.getElementById('scriptInput').value;
                        localStorage.setItem(`profile_${profileName}_last_srt`, scriptContent);
                        console.log(`프로필 ${profileName}에 SRT 저장됨`);
                    }
                    
                    if (selectedFiles.length > 0 && runSlideshowBtn) {
                        runSlideshowBtn.disabled = false;
                    }
                    
                    // 100초 후 자동 초기화
                    autoResetAfterPodcast();
                }
                
                if (job.status === 'completed' && type === 'slideshow') {
                    await loadHistory();
                    
                    setTimeout(() => {
                        const mp4Url = job.result.mp4_url;
                        const projectPreview = getProjectPreview();
                        if (projectPreview) {
                            playVideo(mp4Url, projectPreview.textContent);
                            
                            // 폴더 열기 버튼 표시
                            const openVideoFolderBtn = getOpenVideoFolderBtn();
                            if (openVideoFolderBtn) {
                                openVideoFolderBtn.style.display = 'inline-block';
                                // 현재 재생 중인 파일 정보 저장
                                window.currentVideoFile = {
                                    name: `${projectPreview.textContent}.mp4`,
                                    type: 'mp4',
                                    url: mp4Url
                                };
                            }
                        }
                    }, 1000);
                }
            }
            
        } catch (error) {
            console.error('Polling error:', error);
            clearInterval(interval);
        }
    }, 1000);
}

function updatePodcastProgress(job) {
    const podcastProgressFill = getPodcastProgressFill();
    const podcastStage = getPodcastStage();
    const podcastLog = getPodcastLog();
    
    if (podcastProgressFill) podcastProgressFill.style.width = `${job.percent}%`;
    if (podcastStage) podcastStage.textContent = job.stage || '진행 중...';
    
    if (job.log && job.log.length > 0 && podcastLog) {
        const lastLog = job.log[job.log.length - 1];
        podcastLog.innerHTML += `<div>${lastLog}</div>`;
        podcastLog.scrollTop = podcastLog.scrollHeight;
    }
}

function updateSlideshowProgress(job) {
    const slideshowProgressFill = getSlideshowProgressFill();
    const slideshowStage = getSlideshowStage();
    const slideshowLog = getSlideshowLog();
    
    if (slideshowProgressFill) slideshowProgressFill.style.width = `${job.percent}%`;
    if (slideshowStage) slideshowStage.textContent = job.stage || '진행 중...';
    
    if (job.log && job.log.length > 0 && slideshowLog) {
        const lastLog = job.log[job.log.length - 1];
        slideshowLog.innerHTML += `<div>${lastLog}</div>`;
        slideshowLog.scrollTop = slideshowLog.scrollHeight;
    }
}

// =============================================================================
// 히스토리
// =============================================================================
async function loadHistory() {
    try {
        const response = await fetch('/api/history/mp4?limit=50');
        
        if (!response.ok) {
            throw new Error(`HTTP 오류: ${response.status}`);
        }
        
        const history = await response.json();
        console.log('히스토리 로드됨:', history.length, '개');
        currentHistory = history;
        renderHistory(history);
    } catch (error) {
        console.error('히스토리 로드 실패:', error);
        currentHistory = [];
        renderHistory([]);
    }
}

function renderHistory(history) {
    const historyList = getHistoryList();
    if (!historyList) return;
    
    historyList.innerHTML = '';
    
    if (!history || history.length === 0) {
        historyList.innerHTML = '<div class="history-item">생성된 파일이 없습니다</div>';
        return;
    }
    
    history.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'history-item';
        if (index === currentHistoryIndex) {
            div.classList.add('selected');
        }
        
        const fileType = item.type || 'mp4';
        const fileName = item.name || '파일명 없음';
        const mtimeStr = item.mtime_str || '';
        const sizeMb = item.size_mb || 0;
        
        // 파일 경로 결정
        // 서버가 OUTPUT/SlidShow 등 실제 위치를 찾아서 열도록 '파일명만' 전달합니다.
        let filePath = fileName;
        
        // HTML 구조 (onclick 제거)
        div.innerHTML = `
            <div class="title">${fileName} <span class="badge">${fileType.toUpperCase()}</span></div>
            <div class="meta">
                <span>${mtimeStr}</span>
                <span>${sizeMb}MB</span>
            </div>
            <div class="history-actions">
                <button class="folder-btn" data-path="${filePath.replace(/\\/g, '\\\\')}">폴더 열기</button>
                <button class="delete-btn" data-filename="${fileName}" data-type="${fileType}">삭제</button>
            </div>
        `;
        
        // 아이템 클릭 이벤트 (재생)
        div.addEventListener('click', (e) => {
            // 버튼 클릭 시 이벤트 전파 방지
            if (e.target.tagName === 'BUTTON') return;
            
            currentHistoryIndex = index;
            playMedia(item);
            renderHistory(history);
        });
        
        // 폴더 열기 버튼 이벤트
        const folderBtn = div.querySelector('.folder-btn');
        if (folderBtn) {
            folderBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // 이벤트 버블링 방지
                e.preventDefault();
                
                const path = folderBtn.dataset.path;
                console.log('폴더 열기 버튼 클릭:', path);
                
                // 직접 openFolder 함수 호출
                openFolder(path);
            });
        }
        
        // 삭제 버튼 이벤트
        const deleteBtn = div.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // 이벤트 버블링 방지
                e.preventDefault();
                
                const filename = deleteBtn.dataset.filename;
                const filetype = deleteBtn.dataset.type;
                console.log('삭제 버튼 클릭:', filename, filetype);
                
                // 직접 deleteFile 함수 호출
                deleteFile(filename, filetype);
            });
        }
        
        historyList.appendChild(div);
    });
}

function filterHistory() {
    const historySearch = getHistorySearch();
    if (!historySearch) return;
    
    const searchTerm = historySearch.value.toLowerCase();
    const filtered = currentHistory.filter(item => 
        item.name && item.name.toLowerCase().includes(searchTerm)
    );
    renderHistory(filtered);
}


// =============================================================================
// SLID_Maker.exe 실행
// =============================================================================
function openSlidMaker() {
    console.log('SLID_Maker.exe 실행 시도...');

    // 로컬 경로 (서버가 실행 요청을 처리)
    const exePath = 'I:\\SLID\\SLID_Maker.py';

    fetch('/api/run-slid-maker', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            exePath: exePath,
            brandName: getBrandName() ? getBrandName().value : '',
            phoneNumber: getPhoneNumber() ? getPhoneNumber().value : ''
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            console.log('SLID_Maker 실행됨');
        } else {
            alert('SLID_Maker를 실행할 수 없습니다.\n' + (data.message || ''));
        }
    })
    .catch(err => {
        console.error('실행 오류:', err);
        alert('실행 중 오류가 발생했습니다.');
    });
}


// =============================================================================
// 파일 관리 함수 (디버깅 강화 버전)
// =============================================================================
async function openFolder(path) {
    console.log('폴더 열기 시도:', path);

    if (!path) {
        alert('경로가 비어있습니다.');
        return;
    }

    // 경로 정리 (줄바꿈, 따옴표 제거)
    path = path.replace(/[\n\r"]/g, '').trim();

    // 백슬래시 처리
    path = path.replace(/\\\\/g, '\\');

    console.log('정리된 경로:', path);

    try {
        const response = await fetch('/api/open-folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ path: path })
        });

        const result = await response.json();
        console.log('서버 응답:', result);

        if (result.status === 'ok') {
            console.log('폴더 열기 성공');
            alert('폴더가 열렸습니다. 잠시만 기다려주세요...');
        } else {
            alert('폴더를 열 수 없습니다.\n' + (result.message || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('폴더 열기 오류:', error);
        alert('폴더 열기 중 네트워크 오류가 발생했습니다.\n' + error.message);
    }
}

async function deleteFile(filename, type) {
    if (!filename) {
        alert('파일명이 없습니다.');
        return;
    }

    // 파일명 정리 (앞뒤 공백 제거)
    const cleanFilename = filename.trim();

    console.log('삭제할 파일명:', cleanFilename);
    console.log('파일 타입:', type);

    if (!confirm(`'${cleanFilename}' 파일을 삭제할까요?`)) return;

    try {
        console.log('삭제 요청:', { filename: cleanFilename, type });

        const response = await fetch('/api/delete-file', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                filename: cleanFilename, 
                type: type 
            })
        });

        const result = await response.json();
        console.log('삭제 응답:', result);

        if (result.status === 'ok') {
            alert('파일이 삭제되었습니다.');
            loadHistory(); // 히스토리 새로고침
        } else {
            alert('파일 삭제 실패: ' + (result.message || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('삭제 오류:', error);
        alert('파일 삭제 중 오류 발생: ' + error.message);
    }
}


// =============================================================================
// 비디오 재생
// =============================================================================
function playMedia(item) {
    const video = document.getElementById('mobilePlayer');
    const audio = getAudioPlayer();
    const title = document.getElementById('currentVideoTitle');
    const openVideoFolderBtn = getOpenVideoFolderBtn();

    if (title) title.textContent = item.name || '선택된 파일';
    
    // 현재 재생 중인 파일 정보 저장
    window.currentVideoFile = {
        name: item.name,
        type: item.type,
        url: item.url
    };
    
    if (openVideoFolderBtn) {
        openVideoFolderBtn.style.display = 'inline-block';
    }

    if (item.type === 'mp3') {
        if (video) { 
            try { video.pause(); } catch(e){} 
            video.removeAttribute('src'); 
            video.load(); 
        }
        if (audio) {
            audio.src = item.url;
            audio.load();
            audio.play().catch(() => {});
        }
    } else {
        if (audio) { 
            try { audio.pause(); } catch(e){} 
            audio.removeAttribute('src'); 
            audio.load(); 
        }
        if (video) {
            video.src = item.url;
            video.load();
            video.play().catch(() => {});
        }
    }
    renderHistory(currentHistory);
}

function playVideo(url, title) {
    const mobilePlayer = getMobilePlayer();
    const currentVideoTitle = getCurrentVideoTitle();
    const openVideoFolderBtn = getOpenVideoFolderBtn();
    
    if (!mobilePlayer || !currentVideoTitle) return;
    
    mobilePlayer.src = url;
    mobilePlayer.load();
    mobilePlayer.play().catch(e => console.log('Autoplay prevented:', e));
    currentVideoTitle.textContent = title || '재생 중...';
    
    // 현재 재생 중인 파일 정보 저장
    window.currentVideoFile = {
        name: title + '.mp4',
        type: 'mp4',
        url: url
    };
    
    if (openVideoFolderBtn) {
        openVideoFolderBtn.style.display = 'inline-block';
    }
}

function playPrevVideo() {
    if (currentHistoryIndex > 0) {
        currentHistoryIndex--;
        const item = currentHistory[currentHistoryIndex];
        playMedia(item);
        renderHistory(currentHistory);
    }
}

function playNextVideo() {
    if (currentHistoryIndex < currentHistory.length - 1) {
        currentHistoryIndex++;
        const item = currentHistory[currentHistoryIndex];
        playMedia(item);
        renderHistory(currentHistory);
    }
}

// =============================================================================
// 팝업 창 열기
// =============================================================================
function openPopup(event, url) {
    event.preventDefault();
    
    // 팝업 창 열기
    const popup = window.open(url, 'popup', 'width=800,height=600,scrollbars=yes,resizable=yes');
    
    if (!popup) {
        alert('팝업이 차단되었습니다. 팝업 차단을 해제해주세요.');
    }
}

// =============================================================================
// 외부 도구 (iframe 방식)
// =============================================================================
function toggleExternalTool() {
    const externalToolContent = getExternalToolContent();
    const toolToggle = getToolToggle();
    
    if (!externalToolContent || !toolToggle) return;
    
    if (externalToolContent.style.display === 'none' || externalToolContent.style.display === '') {
        externalToolContent.style.display = 'block';
        toolToggle.textContent = '▼';
    } else {
        externalToolContent.style.display = 'none';
        toolToggle.textContent = '▲';
    }
}

function switchToolTab(tabName, evt) {
    console.log('탭 전환:', tabName);

    // 탭 버튼 활성화
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // 이벤트 객체가 있으면 해당 버튼 활성화
    if (evt && evt.target) {
        evt.target.classList.add('active');
    } else {
        // 이벤트 객체가 없으면 tabName으로 찾아서 활성화(안전장치)
        document.querySelectorAll('.tab-btn').forEach(btn => {
            const t = (btn.textContent || '').toLowerCase();
            if (tabName === 'url' && t.includes('url')) btn.classList.add('active');
            if (tabName !== 'url' && (t.includes('유튜브') || t.includes('youtube'))) btn.classList.add('active');
        });
    }

    // 탭 내용 전환
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    const urlIframeContainer = getUrlIframeContainer();
    const youtubeContainer = getYoutubeContainer();

    if (tabName === 'url') {
        const urlTab = document.getElementById('urlTab');
        if (urlTab) urlTab.classList.add('active');
        if (urlIframeContainer) urlIframeContainer.style.display = 'block';
        if (youtubeContainer) youtubeContainer.innerHTML = '';
    } else {
        const ytTab = document.getElementById('youtubeTab');
        if (ytTab) ytTab.classList.add('active');
        if (urlIframeContainer) urlIframeContainer.style.display = 'none';
        loadYouTubeMusic();
    }
}

function loadSelectedSite() {
    const siteSelector = getSiteSelector();
    const externalFrame = getExternalFrame();
    const iframeFallback = getIframeFallback();
    
    if (!siteSelector || !externalFrame || !iframeFallback) {
        console.log('iframe 요소를 찾을 수 없습니다');
        return;
    }
    
    const url = siteSelector.value;
    console.log('로드 시도:', url);
    
    iframeFallback.style.display = 'none';
    externalFrame.style.display = 'block';
    
    let loaded = false;
    let checked = false;
    
    externalFrame.onload = () => {
        loaded = true;
        console.log('iframe onload 발생:', url);
        
        setTimeout(() => {
            if (checked) return;
            checked = true;
            
            try {
                const doc = externalFrame.contentDocument || externalFrame.contentWindow?.document;
                if (doc && doc.URL !== 'about:blank') {
                    console.log('iframe 정상 로드됨');
                } else {
                    throw new Error('접근 불가');
                }
            } catch (e) {
                console.log('onload 되었으나 접근 불가 (CORS 차단)');
                externalFrame.style.display = 'none';
                iframeFallback.style.display = 'flex';
            }
        }, 500);
    };
    
    externalFrame.src = url;
    
    setTimeout(() => {
        if (checked) return;
        checked = true;
        
        if (!loaded) {
            console.log('onload 없음 - iframe 차단됨:', url);
            externalFrame.style.display = 'none';
            iframeFallback.style.display = 'flex';
        }
    }, 5000);
}

function openInNewTab() {
    const siteSelector = getSiteSelector();
    if (!siteSelector) return;
    
    const url = siteSelector.value;
    if (url) {
        console.log('새 탭 열기:', url);
        window.open(url, '_blank');
    }
}

function addCustomSite() {
    const customUrl = getCustomUrl();
    const siteSelector = getSiteSelector();
    
    if (!customUrl || !siteSelector) return;
    
    let url = customUrl.value.trim();
    if (!url) return;
    
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url;
    }
    
    try {
        new URL(url);
    } catch (e) {
        alert('올바른 URL을 입력해주세요.\n예: https://google.com');
        return;
    }
    
    const existingOptions = Array.from(siteSelector.options).map(opt => opt.value);
    if (existingOptions.includes(url)) {
        alert('이미 등록된 URL입니다.');
        siteSelector.value = url;
        customUrl.value = '';
        loadSelectedSite();
        return;
    }
    
    const option = document.createElement('option');
    option.value = url;
    option.textContent = url.length > 30 ? url.substring(0, 30) + '...' : url;
    siteSelector.appendChild(option);
    
    siteSelector.value = url;
    
    let sites = JSON.parse(localStorage.getItem('externalSites') || '[]');
    sites.push(url);
    localStorage.setItem('externalSites', JSON.stringify(sites));
    
    customUrl.value = '';
    
    loadSelectedSite();
}

function deleteSelectedSite() {
    const selector = getSiteSelector();
    if (!selector) return;
    
    const selectedValue = selector.value;
    const selectedText = selector.options[selector.selectedIndex].text;
    
    // 기본 URL 확인 (ChatGPT, Claude 등)
    const defaultUrls = ['https://chatgpt.com', 'https://claude.ai', 'https://perplexity.ai', 'https://www.google.com', 'https://www.naver.com'];
    
    if (defaultUrls.includes(selectedValue)) {
        alert('기본 URL은 삭제할 수 없습니다.');
        return;
    }
    
    if (!confirm(`'${selectedText}' URL을 삭제할까요?`)) return;
    
    // localStorage에서 삭제
    let sites = JSON.parse(localStorage.getItem('externalSites') || '[]');
    sites = sites.filter(url => url !== selectedValue);
    localStorage.setItem('externalSites', JSON.stringify(sites));
    
    // 셀렉터에서 삭제
    selector.remove(selector.selectedIndex);
    
    // 첫 번째 옵션 선택
    selector.selectedIndex = 0;
    loadSelectedSite();
}

function loadExternalSites() {
    const siteSelector = getSiteSelector();
    if (!siteSelector) return;
    
    const saved = localStorage.getItem('externalSites');
    if (saved) {
        try {
            const sites = JSON.parse(saved);
            sites.forEach(url => {
                const exists = Array.from(siteSelector.options).some(opt => opt.value === url);
                if (!exists) {
                    const option = document.createElement('option');
                    option.value = url;
                    option.textContent = url.length > 30 ? url.substring(0, 30) + '...' : url;
                    siteSelector.appendChild(option);
                }
            });
        } catch (e) {
            console.error('저장된 사이트 로드 실패:', e);
        }
    }
    
    fetch('/api/external-sites/default')
        .then(res => res.json())
        .then(sites => {
            externalSites = sites;
        })
        .catch(err => console.error('기본 사이트 로드 실패:', err));
}

// =============================================================================
// 유튜브 뮤직 함수 (통합 버전)
// =============================================================================
function loadYouTubeMusic() {
    console.log('loadYouTubeMusic 호출됨');

    const urlInput = document.getElementById('youtubeUrl');
    const container = document.getElementById('youtubeContainer');

    if (!urlInput || !container) {
        console.log('요소를 찾을 수 없음');
        return;
    }

    let videoId = urlInput.value.trim();
    if (!videoId) {
        videoId = 'd27gTrPPAyk';
    }

    // URL에서 ID 추출
    if (videoId.includes('youtube.com') || videoId.includes('youtu.be') || videoId.includes('music.youtube.com')) {
        const match = videoId.match(/(?:v=|youtu\.be\/|embed\/|watch\?v=)([^&?]+)/);
        if (match) videoId = match[1];
    }

    const autoplay = document.getElementById('youtubeAutoplay')?.checked ? 1 : 0;
    const loop = document.getElementById('youtubeLoop')?.checked ? 1 : 0;

    // mute=1 추가 (자동재생을 위해)
    let src = `https://www.youtube.com/embed/${videoId}?autoplay=${autoplay}&mute=1&rel=0&modestbranding=1`;
    if (loop) {
        src += `&loop=1&playlist=${videoId}`;
    }

    container.innerHTML = `
        <iframe width="100%" height="100%" src="${src}" 
                frameborder="0" allow="autoplay; encrypted-media; picture-in-picture" 
                allowfullscreen style="border-radius: 8px;">
        </iframe>
    `;
    console.log('유튜브 로드됨:', src);
}

// 페이지 로드 시 유튜브 기본 로드 (init과 충돌 안 나게 안전 처리)
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        const container = document.getElementById('youtubeContainer');
        // 컨테이너가 없으면 아무 것도 안 함
        if (!container) return;
        console.log('유튜브 초기 로드');
        loadYouTubeMusic();
    }, 500);
});

// =============================================================================// =============================================================================
// 프로젝트 저장
// =============================================================================
function saveProject() {
    console.log('프로젝트 저장...');
    
    const project = {
        client: getClientInput().value,
        date: getDateInput().value,
        title: getTitleInput().value,
        script: getScriptInput().value,
        settings: getCurrentSettings()
    };
    
    localStorage.setItem('lastProject', JSON.stringify(project));
    alert('프로젝트가 저장되었습니다.');
}


// =============================================================================
// 자동 초기화 함수
// =============================================================================
function autoResetAfterPodcast() {
    console.log('20초 후 자동 초기화됩니다...');

    // 카운트다운 메시지 표시
    const podcastLog = getPodcastLog();
    if (podcastLog) {
        const countdownDiv = document.createElement('div');
        countdownDiv.className = 'auto-reset-message';
        countdownDiv.id = 'countdownMessage';
        countdownDiv.textContent = '20초 후 자동 초기화됩니다...';
        podcastLog.appendChild(countdownDiv);
    }

    let countdown = 100;
    const interval = setInterval(() => {
        countdown--;
        const countdownMsg = document.getElementById('countdownMessage');
        if (countdownMsg) {
            countdownMsg.textContent = `${countdown}초 후 자동 초기화됩니다...`;
        }

        if (countdown <= 0) {
            clearInterval(interval);
            // 자동 초기화 실행
            resetProject();

            // 완료 메시지
            const podcastLog2 = getPodcastLog();
            if (podcastLog2) {
                const completeMsg = document.createElement('div');
                completeMsg.textContent = '초기화 완료! 새 대본을 입력하세요.';
                completeMsg.style.color = '#4caf50';
                podcastLog2.appendChild(completeMsg);
            }
        }
    }, 1000);
}


// =============================================================================
// 새 프로젝트 초기화 (수정)
// =============================================================================
function resetProject() {
    console.log('새 프로젝트 초기화...');

    document.getElementById('clientName').value = '오박사만능인테리어';
    document.getElementById('projectDate').value = '2026-03-04';
    document.getElementById('projectTitle').value = '봄비가내리는저녁';

    document.getElementById('scriptInput').value = '';

    updateProjectPreview();

    selectedFiles = [];
    document.getElementById('fileList').innerHTML = '';
    document.getElementById('runSlideshowBtn').disabled = true;

    document.getElementById('podcastProgress').style.display = 'none';
    document.getElementById('slideshowProgress').style.display = 'none';
    document.getElementById('podcastResult').style.display = 'none';

    document.getElementById('podcastLog').innerHTML = '';
    document.getElementById('slideshowLog').innerHTML = '';

    document.getElementById('mobilePlayer').src = '';
    document.getElementById('currentVideoTitle').textContent = '선택된 영상 없음';

    // 실행 버튼 활성화
    const runPodcastBtn = getRunPodcastBtn();
    const runSlideshowBtn = getRunSlideshowBtn();
    if (runPodcastBtn) runPodcastBtn.disabled = false;
    if (runSlideshowBtn) runSlideshowBtn.disabled = selectedFiles.length === 0;

    // 폴더 열기 버튼 숨기기
    const openVideoFolderBtn = getOpenVideoFolderBtn();
    if (openVideoFolderBtn) {
        openVideoFolderBtn.style.display = 'none';
    }

    console.log('새 프로젝트 초기화 완료!');
}

// =============================================================================
// 프로필 관리 (수정 버전)
// =============================================================================

// 현재 설정 가져오기
// 현재 설정 가져오기
function getCurrentSettings() {
    const maleVoiceEl = document.getElementById('maleVoice');
    const femaleVoiceEl = document.getElementById('femaleVoice');
    const speedEl = document.getElementById('speed');
    const musicRandomEl = document.getElementById('musicRandom');
    const voiceVolumeEl = document.getElementById('voiceVolume');
    const musicVolumeEl = document.getElementById('musicVolume');
    const clientNameEl = document.getElementById('clientName');
    const projectTitleEl = document.getElementById('projectTitle');
    const brandNameEl = document.getElementById('brandName');
    const phoneNumberEl = document.getElementById('phoneNumber');

    // 체크박스 값 정확히 가져오기
    let musicRandom = true;
    if (musicRandomEl) {
        musicRandom = musicRandomEl.checked === true;
    }

    return {
        maleVoice: maleVoiceEl?.value || 'ko-KR-InJoonNeural',
        femaleVoice: femaleVoiceEl?.value || 'ko-KR-SunHiNeural',
        speed: speedEl?.value || '1.0',
        musicRandom: musicRandom,  // 수정됨
        voiceVolume: voiceVolumeEl?.value || '1.0',
        musicVolume: musicVolumeEl?.value || '0.3',
        clientName: clientNameEl?.value || '',
        projectTitle: projectTitleEl?.value || '',
        brandName: brandNameEl?.value || '',
        phoneNumber: phoneNumberEl?.value || ''
    };
}


// 설정 적용하기
function applySettings(settings) {
    if (!settings) return;

    // 음성 설정
    const maleVoice = document.getElementById('maleVoice');
    if (maleVoice && settings.maleVoice) maleVoice.value = settings.maleVoice;

    const femaleVoice = document.getElementById('femaleVoice');
    if (femaleVoice && settings.femaleVoice) femaleVoice.value = settings.femaleVoice;

    // 속도 설정
    const speed = document.getElementById('speed');
    const speedValue = document.getElementById('speedValue');
    if (speed && settings.speed) {
        speed.value = settings.speed;
        if (speedValue) speedValue.textContent = settings.speed;
    }

    // 볼륨 설정
    const voiceVolume = document.getElementById('voiceVolume');
    const voiceVolumeValue = document.getElementById('voiceVolumeValue');
    if (voiceVolume && settings.voiceVolume) {
        voiceVolume.value = settings.voiceVolume;
        if (voiceVolumeValue) voiceVolumeValue.textContent = Number(settings.voiceVolume).toFixed(2);
    }

    const musicVolume = document.getElementById('musicVolume');
    const musicVolumeValue = document.getElementById('musicVolumeValue');
    if (musicVolume && settings.musicVolume) {
        musicVolume.value = settings.musicVolume;
        if (musicVolumeValue) musicVolumeValue.textContent = Number(settings.musicVolume).toFixed(2);
    }

    // 체크박스 설정
    const musicRandom = document.getElementById('musicRandom');
    if (musicRandom && settings.musicRandom !== undefined) {
        musicRandom.checked = settings.musicRandom === true;
    }

    // 프로젝트 정보 설정
    const clientName = document.getElementById('clientName');
    if (clientName && settings.clientName !== undefined) clientName.value = settings.clientName;

    const projectTitle = document.getElementById('projectTitle');
    if (projectTitle && settings.projectTitle !== undefined) projectTitle.value = settings.projectTitle;

    // 상호/전화번호 설정
    const brandName = document.getElementById('brandName');
    if (brandName && settings.brandName !== undefined) brandName.value = settings.brandName;

    const phoneNumber = document.getElementById('phoneNumber');
    if (phoneNumber && settings.phoneNumber !== undefined) phoneNumber.value = settings.phoneNumber;

    // 프로젝트 프리뷰 업데이트
    updateProjectPreview();

    console.log('설정 적용 완료:', settings);
}

// 프로필 저장하기
function savePreset(name) {
    console.log('프로필 저장 시작...');

    const profileName = (typeof name === 'string' && name.trim()) ? name.trim() : prompt('저장할 프로필 이름을 입력하세요:', '새 프로필');
    if (!profileName) return;

    const settings = getCurrentSettings();
    settings.savedAt = new Date().toLocaleString();

    // 기존 프로필 로드
    let profiles = {};
    try {
        const saved = localStorage.getItem('podcastProfiles');
        if (saved) {
            profiles = JSON.parse(saved);
        }
    } catch (e) {
        console.error('프로필 로드 실패:', e);
    }

    // 프로필 저장
    profiles[profileName] = settings;
    localStorage.setItem('podcastProfiles', JSON.stringify(profiles));

    // 현재 대본도 프로필별로 저장
    const scriptInput = document.getElementById('scriptInput');
    if (scriptInput && scriptInput.value) {
        localStorage.setItem(`profile_${profileName}_last_srt`, scriptInput.value);
    }

    // 프로필 선택기 업데이트
    updateProfileSelector(profileName);

    console.log(`프로필 저장됨: ${profileName}`, settings);
    alert(`'${profileName}' 프로필이 저장되었습니다.`);
}

function saveProfile() {
    console.log('saveProfile 호출됨');
    savePreset();
}

// 프로필 불러오기
function loadProfile() {
    console.log('loadProfile 호출됨');
    const selector = document.getElementById('profileSelector');
    if (!selector) return;

    const profileName = selector.value;
    if (profileName && profileName !== 'default') {
        loadPreset(profileName);
    } else {
        resetToDefaultSettings();
    }
}

function loadPreset(name) {
    const profileName = name;
console.log('프로필 불러오기 시도:', profileName);

    if (!profileName || profileName === 'default') {
        // 기본 프로필 선택 시 기본값으로 리셋
        resetToDefaultSettings();
        return;
    }

    try {
        const profiles = JSON.parse(localStorage.getItem('podcastProfiles') || '{}');
        const settings = profiles[profileName];

        if (settings) {
            // 설정 적용
            applySettings(settings);

            // 프로필의 마지막 대본 로드
            const lastSrt = localStorage.getItem(`profile_${profileName}_last_srt`);
            const scriptInput = document.getElementById('scriptInput');
            if (scriptInput && lastSrt) {
                scriptInput.value = lastSrt;
                console.log(`프로필 ${profileName}의 마지막 대본 로드됨`);
            }

            console.log(`프로필 불러옴: ${profileName}`);
        } else {
            console.warn(`프로필 없음: ${profileName}`);
        }
    } catch (e) {
        console.error('프로필 불러오기 실패:', e);
    }
}

function loadProfileByName(name) {
    console.log('loadProfileByName 호출됨:', name);
    if (name && name !== 'default') {
        loadPreset(name);
    } else {
        resetToDefaultSettings();
    }
}

// 기본 설정으로 리셋
function resetToDefaultSettings() {
    const defaultSettings = {
        maleVoice: 'ko-KR-InJoonNeural',
        femaleVoice: 'ko-KR-SunHiNeural',
        speed: '1.0',
        musicRandom: true,
        voiceVolume: '1.0',
        musicVolume: '0.3',
        clientName: '오박사만능인테리어',
        projectTitle: '봄비가내리는저녁',
        brandName: '강경숯불바베큐',
        phoneNumber: '0507-1393-5889'
    };

    applySettings(defaultSettings);

    // 대본은 비우기
    const scriptInput = document.getElementById('scriptInput');
    if (scriptInput) scriptInput.value = '';
}

// 프로필 삭제
function deleteProfile() {
    const selector = document.getElementById('profileSelector');
    if (!selector) return;

    const profileName = selector.value;
    if (!profileName || profileName === 'default') {
        alert('기본 프로필은 삭제할 수 없습니다.');
        return;
    }

    if (!confirm(`'${profileName}' 프로필을 삭제할까요?`)) return;

    try {
        let profiles = JSON.parse(localStorage.getItem('podcastProfiles') || '{}');
        delete profiles[profileName];
        localStorage.setItem('podcastProfiles', JSON.stringify(profiles));

        // 프로필 관련 대본도 삭제
        localStorage.removeItem(`profile_${profileName}_last_srt`);

        updateProfileSelector('default');
        resetToDefaultSettings();

        console.log(`프로필 삭제됨: ${profileName}`);
    } catch (e) {
        console.error('프로필 삭제 실패:', e);
        alert('프로필 삭제 중 오류가 발생했습니다.');
    }
}

// 프로필 선택기 업데이트
function updateProfileSelector(selectedName = null) {
    const selector = document.getElementById('profileSelector');
    if (!selector) return;

    // 기본 옵션 제외하고 모두 제거
    while (selector.options.length > 1) {
        selector.remove(1);
    }

    try {
        const profiles = JSON.parse(localStorage.getItem('podcastProfiles') || '{}');

        // 프로필 목록 정렬 후 추가
        Object.keys(profiles).sort().forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            selector.appendChild(option);
        });

        // 선택된 프로필 설정
        if (selectedName && selectedName !== 'default') {
            selector.value = selectedName;
        } else {
            selector.value = 'default';
        }

        console.log('프로필 선택기 업데이트됨, 프로필 수:', Object.keys(profiles).length);
    } catch (e) {
        console.error('프로필 목록 로드 실패:', e);
    }
}

// 마지막 사용 프로필 로드
function loadLastUsedProfile() {
    try {
        const lastProfile = localStorage.getItem('lastUsedProfile');
        console.log('마지막 사용 프로필:', lastProfile);

        if (lastProfile && lastProfile !== 'default') {
            const profiles = JSON.parse(localStorage.getItem('podcastProfiles') || '{}');
            if (profiles[lastProfile]) {
                // 설정 적용
                applySettings(profiles[lastProfile]);

                // 프로필 선택기 업데이트
                updateProfileSelector(lastProfile);

                // 마지막 대본 로드
                const lastSrt = localStorage.getItem(`profile_${lastProfile}_last_srt`);
                const scriptInput = document.getElementById('scriptInput');
                if (scriptInput && lastSrt) {
                    scriptInput.value = lastSrt;
                }

                console.log(`마지막 프로필 로드됨: ${lastProfile}`);
            }
        }
    } catch (e) {
        console.error('마지막 프로필 로드 실패:', e);
    }
}

// 마지막 사용 프로필 저장
function saveLastUsedProfile() {
    const selector = document.getElementById('profileSelector');
    if (!selector) return;

    const profileName = selector.value;
    if (profileName) {
        localStorage.setItem('lastUsedProfile', profileName);
        console.log('마지막 사용 프로필 저장:', profileName);
    }
}

// 프로필 이벤트 설정
function setupProfileEvents() {
    console.log('프로필 이벤트 설정 중...');

    const saveBtn = document.getElementById('saveProfileBtn');
    const deleteBtn = document.getElementById('deleteProfileBtn');
    const selector = document.getElementById('profileSelector');

    if (saveBtn) {
        saveBtn.addEventListener('click', saveProfile);
        console.log('프로필 저장 버튼 이벤트 연결됨');
    }

    if (deleteBtn) {
        deleteBtn.addEventListener('click', deleteProfile);
        console.log('프로필 삭제 버튼 이벤트 연결됨');
    }

    if (selector) {
        selector.addEventListener('change', (e) => {
            console.log('프로필 선택 변경:', e.target.value);
            loadProfile();
            saveLastUsedProfile();
        });
        console.log('프로필 선택기 이벤트 연결됨');
    }

    // 설정 변경 시 자동 저장 (선택사항)
    const autoSaveElements = [
        'maleVoice', 'femaleVoice', 'speed', 'musicRandom',
        'voiceVolume', 'musicVolume', 'clientName', 'projectTitle',
        'brandName', 'phoneNumber', 'scriptInput'
    ];

    autoSaveElements.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', () => {
                // 현재 선택된 프로필이 있으면 마지막 사용 프로필 업데이트
                saveLastUsedProfile();
            });

            // input 이벤트는 디바운스 처리 (선택사항)
            if (id !== 'scriptInput') { // 대본은 저장하지 않음
                element.addEventListener('input', () => {
                    saveLastUsedProfile();
                });
            }
        }
    });
}

// =============================================================================
// 시작
// =============================================================================
document.addEventListener('DOMContentLoaded', init);


// =============================================================================
// 설정/프로필/프로젝트 상태 영구 저장 (localStorage + 프로젝트별 project.json)
// =============================================================================

const LS_SETTINGS_KEY = "slid_user_settings_v1";
const LS_PROFILES_KEY = "slid_profiles_v1";
const LS_SELECTED_PROFILE_KEY = "slid_selected_profile_v1";
let __saveTimer = null;

// 안전한 DOM getter
function _el(id){ return document.getElementById(id); }

function getActiveProjectKey(){
    const pv = _el("projectPreview");
    if (!pv) return "";
    return (pv.textContent || "").trim();
}

// 현재 UI 설정 수집
function collectAllSettings(){
    return {
        // 프로필(상단)
        brandName: _el("brandName")?.value || "",
        phoneNumber: _el("phoneNumber")?.value || "",

        // 음성/음악
        maleVoice: _el("maleVoice")?.value || "",
        femaleVoice: _el("femaleVoice")?.value || "",
        speed: _el("speed")?.value || "",
        voiceVolume: _el("voiceVolume")?.value || "",
        musicVolume: _el("musicVolume")?.value || "",
        musicRandom: !!_el("musicRandom")?.checked,

        // 슬라이드쇼 속도
        ssImageSec: _el("ssImageSec")?.value || "",
        ssTransitionSec: _el("ssTransitionSec")?.value || "",
        ssZoomIntensity: _el("ssZoomIntensity")?.value || "",

        // 자막
        subEnabled: !!_el("subEnabled")?.checked,
        subFontSize: _el("subFontSize")?.value || "",
        subMarginV: _el("subMarginV")?.value || "",

        // Mac mini 전용 보정
        mmSubBoost: _el("mmSubBoost")?.value || "0",
        mmSubLift: _el("mmSubLift")?.value || "70",
        mmSubWidth: _el("mmSubWidth")?.value || "72",
        mmSubSpacing: _el("mmSubSpacing")?.value || "8",
        mmWmLift: _el("mmWmLift")?.value || "0",
        mmWmGap: _el("mmWmGap")?.value || "25",

        // 워터마크(실제 생성에 쓰는 값)
        wmBrandName: _el("wmBrandName")?.value || "",
        wmPhoneNumber: _el("wmPhoneNumber")?.value || "",
        wmBrandSize: _el("wmBrandSize")?.value || "",
        wmPhoneSize: _el("wmPhoneSize")?.value || "",
        wmMarginBottom: _el("wmMarginBottom")?.value || "",
        wmBoxEnabled: !!_el("wmBoxEnabled")?.checked,
        wmStrokeEnabled: !!_el("wmStrokeEnabled")?.checked,
        wmShadowEnabled: !!_el("wmShadowEnabled")?.checked,
    };
}

function applyAllSettings(s){
    if (!s || typeof s !== "object") return;

    const setVal = (id, v) => { const e=_el(id); if(e!=null && v!==undefined && v!==null && v!==""){ e.value = String(v);} };
    const setChk = (id, v) => { const e=_el(id); if(e!=null && v!==undefined && v!==null){ e.checked = !!v; } };

    setVal("brandName", s.brandName);
    setVal("phoneNumber", s.phoneNumber);

    setVal("maleVoice", s.maleVoice);
    setVal("femaleVoice", s.femaleVoice);

    if (s.speed!==undefined && _el("speed")){
        _el("speed").value = String(s.speed);
        if (_el("speedValue")) _el("speedValue").textContent = String(s.speed);
    }
    if (s.voiceVolume!==undefined && _el("voiceVolume")){
        _el("voiceVolume").value = String(s.voiceVolume);
        if (_el("voiceVolumeValue")) _el("voiceVolumeValue").textContent = Number(s.voiceVolume).toFixed(2);
    }
    if (s.musicVolume!==undefined && _el("musicVolume")){
        _el("musicVolume").value = String(s.musicVolume);
        if (_el("musicVolumeValue")) _el("musicVolumeValue").textContent = Number(s.musicVolume).toFixed(2);
    }
    setChk("musicRandom", s.musicRandom);

    if (_el("ssImageSec") && s.ssImageSec!==undefined){
        _el("ssImageSec").value = String(s.ssImageSec);
        if (_el("ssImageSecValue")) _el("ssImageSecValue").textContent = `${s.ssImageSec}초`;
    }
    if (_el("ssTransitionSec") && s.ssTransitionSec!==undefined){
        _el("ssTransitionSec").value = String(s.ssTransitionSec);
        if (_el("ssTransitionSecValue")) _el("ssTransitionSecValue").textContent = `${s.ssTransitionSec}초`;
    }
    if (_el("ssZoomIntensity") && s.ssZoomIntensity!==undefined){
        _el("ssZoomIntensity").value = String(s.ssZoomIntensity);
        if (_el("ssZoomIntensityValue")) _el("ssZoomIntensityValue").textContent = String(s.ssZoomIntensity);
    }

    setChk("subEnabled", s.subEnabled);
    setVal("subFontSize", s.subFontSize);
    setVal("subMarginV", s.subMarginV);
    setVal("mmSubBoost", s.mmSubBoost);
    setVal("mmSubLift", s.mmSubLift);
    setVal("mmWmLift", s.mmWmLift);
    setVal("mmWmGap", s.mmWmGap);

    setVal("wmBrandName", s.wmBrandName);
    setVal("wmPhoneNumber", s.wmPhoneNumber);
    setVal("wmBrandSize", s.wmBrandSize);
    setVal("wmPhoneSize", s.wmPhoneSize);
    setVal("wmMarginBottom", s.wmMarginBottom);
    setChk("wmBoxEnabled", s.wmBoxEnabled);
    setChk("wmStrokeEnabled", s.wmStrokeEnabled);
    setChk("wmShadowEnabled", s.wmShadowEnabled);

    // 프로필값 -> 워터마크 자동 동기화(있으면)
    if (typeof updateWatermarkFromProfile === "function") {
        try { updateWatermarkFromProfile(); } catch(e){}
    }
}

function saveAllSettingsNow(){
    const s = collectAllSettings();
    try{ localStorage.setItem(LS_SETTINGS_KEY, JSON.stringify(s)); }catch(e){}
    // 프로젝트별 저장 (있으면)
    const key = getActiveProjectKey();
    if (key){
        fetch("/api/projects/save-settings", {
            method:"POST",
            headers:{ "Content-Type":"application/json" },
            body: JSON.stringify({ project_key: key, settings: s })
        }).catch(()=>{});
    }
}

function scheduleSaveAllSettings(){
    if (__saveTimer) clearTimeout(__saveTimer);
    __saveTimer = setTimeout(saveAllSettingsNow, 300);
}

function loadAllSettingsFromLocal(){
    try{
        const raw = localStorage.getItem(LS_SETTINGS_KEY);
        if (!raw) return;
        const s = JSON.parse(raw);
        applyAllSettings(s);
    }catch(e){}
}

// =============================================================================
// 프로필(프리셋) 저장/불러오기 - 상단 프로필 드롭다운 + 저장/삭제 버튼
// =============================================================================
function getProfiles(){
    try{
        return JSON.parse(localStorage.getItem(LS_PROFILES_KEY) || "{}");
    }catch(e){
        return {};
    }
}
function setProfiles(obj){
    try{ localStorage.setItem(LS_PROFILES_KEY, JSON.stringify(obj||{})); }catch(e){}
}
function refreshProfileSelector(){
    const sel = _el("profileSelector");
    if (!sel) return;

    const profiles = getProfiles();
    const selected = localStorage.getItem(LS_SELECTED_PROFILE_KEY) || "기본 프로필";

    // 옵션 초기화
    sel.innerHTML = "";
    const names = Object.keys(profiles).sort((a,b)=>a.localeCompare(b, "ko"));
    if (!names.includes("기본 프로필")) names.unshift("기본 프로필");
    names.forEach(name=>{
        const opt=document.createElement("option");
        opt.value=name;
        opt.textContent=name;
        sel.appendChild(opt);
    });

    sel.value = names.includes(selected) ? selected : "기본 프로필";
}

function saveCurrentAsProfile(){
    const sel = _el("profileSelector");
    let name = sel?.value || "기본 프로필";
    if (!name || name==="기본 프로필"){
        name = prompt("저장할 프로필 이름을 입력하세요", "") || "";
        name = name.trim();
        if (!name) return;
    }

    const profiles = getProfiles();
    profiles[name] = collectAllSettings();
    setProfiles(profiles);
    localStorage.setItem(LS_SELECTED_PROFILE_KEY, name);
    refreshProfileSelector();
}

function deleteCurrentProfile(){
    const sel = _el("profileSelector");
    const name = sel?.value || "";
    if (!name || name==="기본 프로필") return;

    if (!confirm(`프로필 '${name}'을 삭제할까요?`)) return;
    const profiles = getProfiles();
    delete profiles[name];
    setProfiles(profiles);
    localStorage.setItem(LS_SELECTED_PROFILE_KEY, "기본 프로필");
    refreshProfileSelector();
}

function applySelectedProfile(){
    const sel = _el("profileSelector");
    const name = sel?.value || "기본 프로필";
    localStorage.setItem(LS_SELECTED_PROFILE_KEY, name);

    const profiles = getProfiles();
    const s = profiles[name];
    if (s) applyAllSettings(s);

    // 즉시 저장(프로젝트/로컬)
    saveAllSettingsNow();
}

// =============================================================================
// 프로젝트 불러오기: 선택 시 폴더 열기 + 해당 설정 복원
// =============================================================================
async function refreshProjectsList(){
    const sel = _el("projectSelect");
    if (!sel) return;
    try{
        const r = await fetch("/api/projects/list");
        const j = await r.json();
        if (j.status!=="ok") return;

        const cur = sel.value;
        sel.innerHTML = '<option value="">프로젝트 선택</option>';

        (j.projects || []).forEach(p=>{
            const opt=document.createElement("option");
            opt.value=p.key;
            opt.textContent = `${p.key} (${p.mtime_str || ""})`;
            sel.appendChild(opt);
        });

        if (cur) sel.value = cur;
    }catch(e){}
}

async function loadProjectSettings(projectKey){
    if (!projectKey) return;
    try{
        const r = await fetch(`/api/projects/load-settings?project_key=${encodeURIComponent(projectKey)}`);
        const j = await r.json();
        if (j.status==="ok" && j.settings && j.settings.settings){
            applyAllSettings(j.settings.settings);
            // 로컬에도 반영
            try{ localStorage.setItem(LS_SETTINGS_KEY, JSON.stringify(j.settings.settings)); }catch(e){}
        }
    }catch(e){}
}

async function openProjectFolderAndRestore(){
    const sel = _el("projectSelect");
    const key = sel?.value || "";
    if (!key) return;

    // 선택 즉시 프로젝트 키를 미리보기로 반영
    const pv = _el("projectPreview");
    if (pv) pv.textContent = key;

    // 설정 복원
    await loadProjectSettings(key);

    // 폴더 열기(OUTPUT/<key>)
    try{
        await fetch("/api/open-folder", {
            method:"POST",
            headers:{ "Content-Type":"application/json" },
            body: JSON.stringify({ path: `I:\\SLID\\OUTPUT\\${key}` })
        });
    }catch(e){}
}

// =============================================================================
// 미디어 리스트: 즉시 갱신 + 검색 + 길이(재생시간) 표시 + SRT 팝업 버튼
// =============================================================================
const __durationCache = new Map();

function _fmtTime(sec){
    if (!isFinite(sec) || sec<=0) return "--:--";
    sec = Math.round(sec);
    const m = Math.floor(sec/60);
    const s = sec%60;
    return `${m}:${String(s).padStart(2,"0")}`;
}

function _probeDuration(url, type, cb){
    if (__durationCache.has(url)){ cb(__durationCache.get(url)); return; }
    const el = document.createElement(type==="mp4" ? "video" : "audio");
    el.preload = "metadata";
    el.src = url;
    el.addEventListener("loadedmetadata", ()=>{
        const d = el.duration;
        __durationCache.set(url, d);
        cb(d);
    });
    el.addEventListener("error", ()=>cb(null));
}

function showSrtPopup(title, text){
    let modal = document.querySelector(".srt-modal");
    if (!modal){
        modal = document.createElement("div");
        modal.className = "srt-modal";
        modal.innerHTML = `
            <div class="srt-modal-backdrop"></div>
            <div class="srt-modal-card">
                <div class="srt-modal-head">
                    <div class="srt-modal-title"></div>
                    <button class="srt-modal-close">닫기</button>
                </div>
                <pre class="srt-modal-body"></pre>
            </div>
        `;
        document.body.appendChild(modal);
        modal.querySelector(".srt-modal-backdrop").addEventListener("click", ()=>modal.classList.remove("open"));
        modal.querySelector(".srt-modal-close").addEventListener("click", ()=>modal.classList.remove("open"));
    }
    modal.querySelector(".srt-modal-title").textContent = title || "자막";
    modal.querySelector(".srt-modal-body").textContent = text || "";
    modal.classList.add("open");
}

async function fetchAndShowSrt(item){
    const srtUrl = item?.srt_url || (item?.url ? item.url.replace(/\/mp3$/, "/srt") : "");
    if (!srtUrl) return;
    try{
        const r = await fetch(srtUrl);
        const t = await r.text();
        showSrtPopup(item?.name || "자막", t);
    }catch(e){}
}

// 기존 renderHistory()가 있으면, 래핑해서 기능 추가
const __old_renderHistory = (typeof renderHistory === "function") ? renderHistory : null;
if (__old_renderHistory){
    renderHistory = function(list){
        __old_renderHistory(list);

        // 렌더 후: 각 항목에 길이 표시 + SRT 버튼 달기
        const items = document.querySelectorAll(".history-item");
        items.forEach(div=>{
            const url = div.dataset?.url || "";
            const type = div.dataset?.type || "";
            const name = div.dataset?.name || "";

            // 길이 표시 영역 만들기
            let badge = div.querySelector(".duration-badge");
            if (!badge){
                badge = document.createElement("span");
                badge.className = "duration-badge";
                badge.textContent = "--:--";
                const titleEl = div.querySelector(".history-name") || div.querySelector("strong");
                if (titleEl && titleEl.parentNode){
                    titleEl.parentNode.appendChild(badge);
                }else{
                    div.appendChild(badge);
                }
            }

            if (url && (type==="mp3" || type==="mp4")){
                _probeDuration(url, type, (d)=>{
                    if (d!=null) badge.textContent = _fmtTime(d);
                });
            }

            // MP3 옆에 SRT 버튼
            if (type==="mp3"){
                let sbtn = div.querySelector(".srt-btn");
                if (!sbtn){
                    sbtn = document.createElement("button");
                    sbtn.className = "small-btn srt-btn";
                    sbtn.textContent = "자막";
                    sbtn.addEventListener("click", (e)=>{
                        e.preventDefault();
                        e.stopPropagation();
                        const item = (window.__lastHistoryList || []).find(x=>x.name===name) || null;
                        if (item) fetchAndShowSrt(item);
                    });
                    const actions = div.querySelector(".history-actions") || div;
                    actions.appendChild(sbtn);
                }
            }
        });
    };
}

// 검색: currentHistory 기반으로 즉시 필터
function filterHistoryNow(){
    const input = _el("historySearch");
    if (!input) return;
    const term = (input.value || "").toLowerCase().trim();
    if (!term){
        if (typeof renderHistory==="function") renderHistory(window.__lastHistoryList || []);
        return;
    }
    const base = window.__lastHistoryList || [];
    const filtered = base.filter(x => (x.name||"").toLowerCase().includes(term));
    if (typeof renderHistory==="function") renderHistory(filtered);
}

// loadHistory 래핑: 마지막 리스트 저장 + 검색 반영
const __old_loadHistory = (typeof loadHistory === "function") ? loadHistory : null;
if (__old_loadHistory){
    loadHistory = async function(){
        const res = await __old_loadHistory();
        // __old_loadHistory 내부에서 currentHistory를 갱신한다고 가정, 혹시 못하면 DOM에서 복구 불가
        try{
            window.__lastHistoryList = (typeof currentHistory !== "undefined" && Array.isArray(currentHistory)) ? currentHistory : (window.__lastHistoryList||[]);
        }catch(e){}
        filterHistoryNow();
        return res;
    };
}

// =============================================================================
// 초기 바인딩
// =============================================================================
function bindPersistenceHandlers(){
    // 로컬 설정 불러오기
    loadAllSettingsFromLocal();

    // 자동 저장 대상들
    const ids = [
        "brandName","phoneNumber",
        "maleVoice","femaleVoice","speed","voiceVolume","musicVolume","musicRandom",
        "ssImageSec","ssTransitionSec","ssZoomIntensity",
        "subEnabled","subFontSize","subMarginV",
        "mmSubBoost","mmSubLift","mmWmLift","mmWmGap",
        "wmBrandName","wmPhoneNumber","wmBrandSize","wmPhoneSize","wmMarginBottom",
        "wmBoxEnabled","wmStrokeEnabled","wmShadowEnabled"
    ];
    ids.forEach(id=>{
        const e=_el(id);
        if (!e) return;
        e.addEventListener("change", scheduleSaveAllSettings);
        e.addEventListener("input", scheduleSaveAllSettings);
    });

    // 프로필 UI
    refreshProfileSelector();
    if (_el("saveProfileBtn")) _el("saveProfileBtn").addEventListener("click", (e)=>{ e.preventDefault(); saveCurrentAsProfile(); });
    if (_el("deleteProfileBtn")) _el("deleteProfileBtn").addEventListener("click", (e)=>{ e.preventDefault(); deleteCurrentProfile(); });
    if (_el("profileSelector")) _el("profileSelector").addEventListener("change", applySelectedProfile);

    // 프로젝트 목록 + 선택 시 복원 + 폴더 열기
    refreshProjectsList();
    if (_el("projectSelect")) _el("projectSelect").addEventListener("change", openProjectFolderAndRestore);
    if (_el("loadProjectBtn")) _el("loadProjectBtn").addEventListener("click", (e)=>{
        // 기존 "파일 선택" 대신, PROJEC 폴더를 바로 열어준다
        e.preventDefault();
        fetch("/api/projects/open-folder", {method:"POST"}).catch(()=>{});
    });

    // 미디어 검색
    if (_el("historySearch")){
        _el("historySearch").addEventListener("input", filterHistoryNow);
        _el("historySearch").addEventListener("keyup", filterHistoryNow);
    }

    // 미디어 리스트: 주기 갱신(새 파일 즉시 반영)
    setInterval(()=>{ if (document.visibilityState==="visible" && typeof loadHistory==="function") loadHistory(); }, 5000);
    window.addEventListener("focus", ()=>{ if (typeof loadHistory==="function") loadHistory(); });
}

document.addEventListener("DOMContentLoaded", ()=>{
    try{ bindPersistenceHandlers(); }catch(e){}
});
