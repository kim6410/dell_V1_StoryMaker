StoryMaker static cleanup note

Current global header structure:

1) header-nav.html
- Shared header markup only.

2) common_nav_unified.js
- Loads header/footer.
- Handles auth slot, mypage/admin buttons, active menu state, and mobile hamburger open/close.

3) storymaker_nav_unified.css
- Owns all global header, logo, mobile hamburger menu, and unified nav styling.

Rules:
- Do not reintroduce common_nav.js.
- Do not put global header CSS back into index.css or index.html inline style.
- index.css should handle StoryMaker app body UI only.
- index.html inline style should stay minimal for overflow/modal safety only.

Cleanup date: 2026-07-04
