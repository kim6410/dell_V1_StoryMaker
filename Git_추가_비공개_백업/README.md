# StoryMaker V1 + Beta Git 추가 비공개 백업

## 2026-07-26 전체 복구 확장

기본 실행 스크립트는 `backup_storymaker_complete_private.py`입니다.

날짜별 `Full_Private` 스냅샷에는 V1·Beta DB, Beta jobs·Gemini queue, 서버 로컬 환경설정, 실제 systemd 설정과 런타임 상태를 저장합니다.

`Recovery_Mirror/current`에는 V1 output_results, 브라우저 TTS ONNX 모델, 백엔드 글꼴, 음악 라이브러리, Supertonic3 실행 환경을 압축 없이 증분 복사합니다.

기존 파일은 자동 삭제하지 않습니다.

최근 전체 복구 백업은 다음 파일에서 확인합니다.

```bash
cat /mnt/lms_ssd/StoryMaker_Backup/LATEST_FULL_RECOVERY_BACKUP.txt
```

---

# 이전 Beta 전용 백업 설명

이 폴더는 GitHub에 올리지 않는 StoryMaker Beta 운영 데이터를 자동 백업하기 위한 관리 폴더입니다.

백업 대상:

- `/home/bourne/StoryMaker_1/StoryMaker_beta/data/storymaker_beta.db`
- `/home/bourne/StoryMaker_1/StoryMaker_beta/data/jobs/`

백업 위치:

- Dell 서버: `/mnt/lms_ssd/StoryMaker_Backup/Beta_Private/`
- Windows 공유: `\\192.168.0.32\DellMusic\StoryMaker_Backup\Beta_Private\`

백업 형식:

- 압축하지 않음
- 날짜별 폴더
- 시간별 폴더
- DB와 jobs를 각각 원본 폴더 구조로 저장

예시:

```text
Beta_Private/
└─ 2026-07-26/
   └─ 033000/
      ├─ database/
      │  └─ storymaker_beta.db
      ├─ jobs/
      │  ├─ beta_20260726_...
      │  └─ beta_20260725_...
      └─ backup_manifest.json
```

자동 실행:

- systemd timer: `storymaker-beta-private-backup.timer`
- 실행 시각: 매일 새벽 03:30
- 기존 백업 자동 삭제 없음

수동 실행:

```bash
/usr/bin/python3 /home/bourne/StoryMaker_1/Git_추가_비공개_백업/backup_beta_private.py
```

상태 확인:

```bash
systemctl status storymaker-beta-private-backup.timer
systemctl list-timers storymaker-beta-private-backup.timer
journalctl -u storymaker-beta-private-backup.service -n 100 --no-pager
```

최근 백업 위치:

```bash
cat /mnt/lms_ssd/StoryMaker_Backup/Beta_Private/LATEST_BACKUP.txt
```

복구할 때는 실행 중인 Beta 서비스를 먼저 중지하고, 백업 DB와 필요한 jobs 폴더를 원래 위치로 복사한 뒤 DB integrity를 확인해야 합니다.

백업 스크립트는 원본 DB와 jobs를 삭제하거나 이동하지 않습니다.
