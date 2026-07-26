# Supertonic3 StoryMaker API

## Authentication

`GET /health` is public. Every other HTTP endpoint requires:

```http
Authorization: Bearer <SUPERTONIC_API_KEY>
```

The service reads the key from the `SUPERTONIC_API_KEY` environment variable. Missing configuration and missing or invalid credentials return `401 Unauthorized`.

## Podcast workflow

### 1. Start generation

`POST /api/podcast/run` with `multipart/form-data`:

| Field | Required | Default |
|---|---:|---|
| `project_key` | yes | - |
| `script` | yes | - |
| `male_voice` | no | `ko-KR-InJoonNeural` |
| `female_voice` | no | `ko-KR-SunHiNeural` |
| `speed` | no | `1.0` |
| `music_random` | no | `true` |
| `music_volume` | no | `0.3` |
| `voice_volume` | no | `1.0` |

```bash
curl -X POST 'https://supertonic.example.com/api/podcast/run' \
  -H "Authorization: Bearer $SUPERTONIC_API_KEY" \
  -F 'project_key=storymaker_2026-06-25_demo' \
  -F 'script=남성: 안녕하세요.\n여성: StoryMaker 연동 테스트입니다.'
```

Response:

```json
{"job_id":"podcast_ab12cd34"}
```

### 2. Poll status

```bash
curl -H "Authorization: Bearer $SUPERTONIC_API_KEY" \
  'https://supertonic.example.com/api/jobs/podcast_ab12cd34'
```

`status` is `pending`, `running`, `completed`, or `failed`. On completion, `result.mp3_url` and `result.srt_url` contain relative download URLs. Send the same Authorization header when downloading them.

### 3. Download output

```bash
curl -OJ -H "Authorization: Bearer $SUPERTONIC_API_KEY" \
  'https://supertonic.example.com/media/podcast/storymaker_2026-06-25_demo/mp3'
```

Related endpoints:

- `GET /health` - public health check
- `GET /api/audio/list` - audio list
- `GET /api/jobs/{job_id}` - job status
- `GET /media/podcast/{filename}` - legacy podcast file
- `GET /media/podcast/{project_key}/mp3` - generated MP3
- `GET /media/podcast/{project_key}/srt` - generated subtitles

## systemd installation

The existing `.venv` currently has a Windows `Scripts/` layout. Create a Linux virtual environment with `.venv/bin/python` before enabling the service; preserve or move the Windows environment manually if it is still needed.

The existing `supertonic3.service` remains the TTS engine on port 7788. The API uses the separate `supertonic3-api.service` unit and port 8001. Its `ExecStart` reuses the working Linux Python environment without changing or restarting the TTS service.

```bash
sudo cp supertonic3-api.service /etc/systemd/system/supertonic3-api.service
sudo sh -c 'umask 077; printf "%s\n" "SUPERTONIC_API_KEY=replace-with-a-long-random-key" > /etc/supertonic3-api.env'
sudo systemctl daemon-reload
sudo systemctl enable --now supertonic3-api
```

## Caddy

Replace `supertonic.example.com` in `Caddyfile.example`, ensure its DNS record points to this server, copy the site block into the active Caddyfile, and reload Caddy. Caddy forwards the client Authorization header unchanged and provisions HTTPS automatically when ports 80/443 are reachable.

## Verification

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/api/audio/list                         # expected: 401
curl -H "Authorization: Bearer $SUPERTONIC_API_KEY" \
  http://127.0.0.1:8001/api/audio/list                            # expected: 200
systemctl status supertonic3 --no-pager
systemctl status supertonic3-api --no-pager
```
