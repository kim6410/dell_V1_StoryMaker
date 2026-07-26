# StoryMaker Google 로그인 설정

1. Google Cloud Console에서 OAuth 동의 화면을 구성합니다.
2. 사용자 인증 정보에서 `OAuth client ID`의 애플리케이션 유형을 `Web application`으로 생성합니다.
3. 아래 값을 등록합니다.

   - Authorized JavaScript origins: `https://mystorymaker.duckdns.org`
   - Authorized redirect URIs: `https://mystorymaker.duckdns.org`

4. 프로젝트 루트의 `.env`에 발급받은 Client ID를 넣습니다.

   ```dotenv
   STORYMAKER_GOOGLE_CLIENT_ID=000000000000-example.apps.googleusercontent.com
   ```

5. 서비스를 다시 빌드하고 실행합니다.

   ```bash
   docker compose up --build -d
   ```

Client ID가 비어 있으면 기존 아이디/비밀번호 로그인은 그대로 동작하며 Google 로그인 버튼은 비활성 상태와 설정 안내를 표시합니다. Client secret은 이 GIS ID 토큰 로그인 방식에 필요하지 않으며 저장하면 안 됩니다.
