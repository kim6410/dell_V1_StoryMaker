# 2026-08-30 StoryMaker V1 VoiceBox TTS/SRT 영상 설정 부모 팝업 최종 업무일지

## 1. 작업 목적
StoryMaker V1/Beta 숏폼 영상 제작에서 VoiceBox가 생성한 TTS 음성 파일과 SRT 자막을 사용자가 직접 선택하여, 기존 StoryMaker 영상 제작 흐름의 음성/SRT만 대체하고 기존 이미지·BGM·자막·워터마크·전환·렌더링 설정은 그대로 재사용하도록 구성했다.

## 2. 최종 사용자 흐름
1. StoryMaker V1에서 Beta 숏폼 제작 화면 진입
2. 영상 제작 설정 버튼 선택
3. V1 최상위 화면에 독립 설정 팝업 표시
4. `나레이션 소스`에서 VoiceBox TTS 음성과 VoiceBox SRT 자막 선택
5. 외부 TTS/SRT가 있으면 기존 StoryMaker 음성/SRT 대신 사용
6. 이후 기존 BGM, 자막, 워터마크, 이미지, 전환, MP4 렌더링 흐름 그대로 진행

## 3. VoiceBox TTS/SRT 적용
- 외부 나레이션 음성 입력 지원
- 외부 SRT 입력 지원
- 브라우저 렌더 경로와 Dell 서버 폴백 렌더 경로 모두 외부 나레이션 전달
- 외부 파일 미선택 시 기존 StoryMaker 음성/SRT 사용
- 기존 음원/BGM/워터마크/자막/영상 설정을 별도 시스템으로 복제하지 않고 기존 설정을 그대로 사용

## 4. 영상 설정 UI 문제와 최종 해결
초기에는 Beta iframe 내부 모달로 설정창을 표시했다. 그러나 V1 부모 문서, 긴 Beta iframe, iframe 내부 스크롤, 모달 내부 스크롤이 중첩되어 다음 문제가 반복됐다.

- 설정 하단이 잘림
- 스크롤바가 있어도 휠/트랙패드 스크롤이 잠김
- iframe 전체 높이를 기준으로 모달이 아래로 밀림
- 현재 보이는 iframe 높이를 기준으로 계산하면 모달 자체가 지나치게 짧아짐
- 부모 화면 자동 스크롤 보정 과정에서 설정창이 열리지 않는 회귀 발생

최종적으로 iframe 내부 위치 계산 방식을 폐기하고, 설정 버튼을 누르면 기존 설정 DOM 자체를 V1 부모 document.body로 이동해 독립 팝업으로 표시하는 구조로 변경했다.

최종 구조:
`Beta 설정 버튼 -> V1 부모 화면 독립 팝업 -> 기존 설정 DOM 이동 -> 팝업 내부 단일 스크롤`

이 구조는 설정값을 복제하지 않으므로 기존 input/change 이벤트, 자동저장, VoiceBox File 객체, 음악/자막/워터마크 설정이 그대로 유지된다. 닫으면 설정 DOM을 원래 Beta 위치로 돌려놓는다.

## 5. 최종 핵심 커밋
- `c43d074` 외부 TTS/SRT 나레이션 소스 기반 작업
- `2409b45` 숏폼 설정창 높이/스크롤 확장
- `3561505` Beta 실제 화면 VoiceBox 나레이션 업로드 연결
- `ccb7795` 복사출력전문점 프롬프트/날씨 검증 정리
- `bd1d82b` VoiceBox GPU 배치 및 Studio 제작 흐름 정리
- `ffc1469` 런타임 DB/임시 Compose 백업 Git 제외
- `405590d` Beta 설정 모달 스크롤 잠금 근본 개선 시도
- `e67e178` 실제 표시 영역 기준 모달 배치 시도
- `7ecec63` 설정 모달 가용 높이 자동 확보 시도
- `037dc90` 설정 모달 열기 회귀 복구
- `65b6d61` 최종: 영상 설정을 V1 부모 팝업으로 분리

최종 기능 기준 커밋: `65b6d61af048cb6de80cecfd79e650a1d8e70fe4`

## 6. 최종 수정 핵심 파일
- `StoryMaker_beta/static/beta-shortform-inline.js`
  - VoiceBox 나레이션 설정 연결
  - 설정 팝업 열기/닫기
  - 기존 설정 DOM을 V1 부모 document.body로 이동/복귀
  - 부모 팝업 전용 스타일 주입 및 stale popup 정리
- `StoryMaker_beta/static/production.html`
  - 나레이션 입력 UI
  - 설정 UI 구조
  - JS 캐시 버전 갱신
- 관련 백엔드/렌더 경로에는 외부 `narration_audio`, `narration_srt` 전달 지원이 반영되어 있음.

## 7. 백업
주요 수정 전 타임머신 성격의 백업을 생성했다. 최종 부모 팝업 전환 직전 백업:

`Backup/V1_WORKING_20260830_073720_Settings_Parent_Popup`

그 외 스크롤/모달 수정 단계별 백업도 Backup 아래에 보존되어 있다.

## 8. 운영 검증
최종 부모 팝업 반영 후 운영 HTTP 확인:
- `/v1/beta/production` HTTP 200
- `beta-shortform-inline.js` HTTP 200
- 캐시 버전 `20260830-settings-parent-popup-1` 반영 확인
- VoiceBox TTS 입력 존재 확인
- VoiceBox SRT 입력 존재 확인
- 부모 `document.body`로 설정 모달 이동 코드 확인
- 이전 stale popup 정리 코드 확인

사용자 실제 브라우저 확인 결과: iframe 내부 모달 방식보다 부모 독립 팝업 방식이 정상 사용 가능하며 최종 구조로 채택함.

## 9. Git/배포 최종 기준
업무일지 작성 직전 확인:
- `HEAD = 65b6d61af048cb6de80cecfd79e650a1d8e70fe4`
- `origin/main = 65b6d61af048cb6de80cecfd79e650a1d8e70fe4`
- Modified 0
- Untracked 0

이 업무일지는 최종 마감 기록이므로 이 파일만 별도 커밋·Push한 뒤 HEAD/origin/GitHub main 일치와 clean 상태를 다시 확인한다.

## 10. 다음 작업자 주의사항
- 영상 설정은 다시 iframe 내부 모달 방식으로 되돌리지 않는다.
- 설정 항목이 늘어나도 V1 부모 팝업 내부에서 확장한다.
- VoiceBox는 독립 영상 제작 엔진이 아니라 `나레이션 입력 소스`로 취급한다.
- VoiceBox에서 BGM을 믹싱하지 않는다. BGM 및 기존 Fade In/Fade Out은 StoryMaker 영상 제작 단계에서 처리한다.
- 외부 TTS/SRT를 선택하지 않은 경우 기존 StoryMaker 음성/SRT 흐름을 보존한다.
- 다른 작업자의 dirty 변경이 있을 경우 전체 stage/commit/clean 금지. 항상 정확한 파일만 지정한다.

## 11. 결론
VoiceBox TTS/SRT를 기존 StoryMaker 영상 제작 흐름에 최소 침습 방식으로 연결했고, 반복적으로 발생했던 iframe 모달 높이/스크롤 문제는 V1 부모 독립 팝업 구조로 최종 해결했다. 이 부모 팝업 구조를 앞으로 영상 설정 UI의 기준 구조로 유지한다.
