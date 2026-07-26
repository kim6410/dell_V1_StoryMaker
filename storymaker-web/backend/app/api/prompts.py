# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 프롬프트 생성 API 라우터 (prompts.py)
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
import json
from app.services import StoryMakerService
from app.schemas import PromptRequest, PromptResponse, CommonResponse
from app.api.auth import get_optional_current_user
from app.db.models import User, ActivityLog
from app.db.database import get_db

router = APIRouter()

@router.post("/generate-prompt", response_model=CommonResponse)
def generate_prompt(
    req: PromptRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user)
):
    """
    입력된 마케팅 기본 데이터(업체명, 페르소나, 기초 내용, 참고 자료, 키워드 및 작성 옵션)를 조립하여
    최종 ChatGPT용 13개 채널 콘텐츠 통합 마크다운 프롬프트 템플릿을 생성합니다.
    로그인 사용자는 활동 로그를 남기고, 비회원은 로그 없이 생성만 허용합니다.
    """
    try:
        timing = {"pc_prompt_request_at": datetime.now().isoformat(timespec="milliseconds")}
        prompt_text = StoryMakerService.generate_prompt(req)
        timing["pc_prompt_ready_at"] = datetime.now().isoformat(timespec="milliseconds")
        timing["pc_prompt_length"] = len(prompt_text)
        
        # 로그인 사용자만 활동 로그 기록
        if current_user:
            ip_addr = request.client.host if request.client else "127.0.0.1"
            user_agt = request.headers.get("user-agent", "Unknown")
            now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 민감 정보(초대코드, 패스워드 등)는 원천 배제한 무해한 메타데이터만 기입
            meta_data = {
                "company": req.company,
                "style": req.style,
                "ai_preset": req.ai_preset,
                "keyword_count": len(req.keywords) if req.keywords else 0
            }
            
            act_log = ActivityLog(
                user_id=current_user.id,
                action="prompt_generate",
                target_type="prompt",
                target_id=None,
                metadata_json=json.dumps(meta_data),
                ip_address=ip_addr,
                user_agent=user_agt,
                created_at=now_stamp
            )
            db.add(act_log)
            db.commit()
        
        data = PromptResponse(generated_prompt=prompt_text, timing=timing)
        return CommonResponse(ok=True, data=data, message="프롬프트가 성공적으로 빌드되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
