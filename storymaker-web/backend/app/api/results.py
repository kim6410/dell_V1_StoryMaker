# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 결과물 파서 API 라우터 (results.py)
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
import json
from app.services import StoryMakerService
from app.schemas import ResultParseRequest, ResultParseResponse, CommonResponse
from app.api.auth import get_optional_current_user
from app.db.models import User, ActivityLog
from app.db.database import get_db

router = APIRouter()

@router.post("/parse-result", response_model=CommonResponse)
def parse_result(
    req: ResultParseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user)
):
    """
    ChatGPT에서 생성되어 복사-붙여넣기한 통합 패키지 원문을 입력받아
    각 채널별 코드블록 태그([BLOCK:BLOG_POST] 등)를 기반으로 자동 분류하여 반환하며, 활동 로그를 남깁니다.
    """
    try:
        parsed = StoryMakerService.parse_result(req)
        
        if not current_user:
            data = ResultParseResponse(
                blocks=parsed["blocks"],
                cleaned_text=parsed["cleaned_text"]
            )
            return CommonResponse(ok=True, data=data, message="결과물 본문이 성공적으로 분류되었습니다.")
        
        # 활동 로그 기록
        ip_addr = request.client.host if request.client else "127.0.0.1"
        user_agt = request.headers.get("user-agent", "Unknown")
        now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        meta_data = {
            "parsed_channels": list(parsed["blocks"].keys()) if "blocks" in parsed else [],
            "raw_text_length": len(req.raw_result) if req.raw_result else 0
        }
        
        act_log = ActivityLog(
            user_id=current_user.id,
            action="result_parse",
            target_type="result",
            target_id=None,
            metadata_json=json.dumps(meta_data),
            ip_address=ip_addr,
            user_agent=user_agt,
            created_at=now_stamp
        )
        db.add(act_log)
        db.commit()
        
        data = ResultParseResponse(
            blocks=parsed["blocks"],
            cleaned_text=parsed["cleaned_text"]
        )
        return CommonResponse(ok=True, data=data, message="결과물 본문이 성공적으로 분류되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel
import re

class PreviewHtmlRequest(BaseModel):
    channel: str
    content: str

def generate_blog_html(content: str) -> str:
    """
    텍스트 본문을 파싱하여 제목, 본문 문단(P), 소제목(H2, H3), 태그로 정밀 구조화한 HTML5 문서를 반환합니다.
    """
    title = ""
    post = ""
    tags = ""
    
    title_match = re.search(r'(?:제목:|title:)\s*(.*?)(?=\n\s*(?:본문:|content:|태그:|tags:)|$)', content, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
        
    post_match = re.search(r'(?:본문:|content:)\s*(.*?)(?=\n\s*(?:태그:|tags:)|$)', content, re.IGNORECASE | re.DOTALL)
    if post_match:
        post = post_match.group(1).strip()
    else:
        # 폴백: 제목 영역을 제외한 나머지 부분을 본문으로 추출
        if title_match:
            post = content.replace(title_match.group(0), "").strip()
        else:
            post = content.strip()
            
    tags_match = re.search(r'(?:태그:|tags:)\s*(.*?)$', content, re.IGNORECASE | re.DOTALL)
    if tags_match:
        tags = tags_match.group(1).strip()
        # 본문 영역에서 태그 텍스트 부분 제거하여 중복 표출 차단
        post = post.replace(tags_match.group(0), "").strip()
        
    clean_title = title if title else "제목 없음"
    
    body_html = ""
    if post:
        paragraphs = re.split(r'\n\s*\n', post)
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if para.startswith('###'):
                text = para[3:].strip()
                body_html += f"<h3>{text}</h3>\n"
            elif para.startswith('##'):
                text = para[2:].strip()
                body_html += f"<h2>{text}</h2>\n"
            elif para.startswith('#'):
                text = para[1:].strip()
                body_html += f"<h1>{text}</h1>\n"
            elif para.startswith('**') and para.endswith('**') and len(para) < 100:
                text = para[2:-2].strip()
                body_html += f"<h3>{text}</h3>\n"
            elif para.startswith('[') and para.endswith(']') and len(para) < 60:
                text = para[1:-1].strip()
                body_html += f"<h3>{text}</h3>\n"
            elif para.startswith('■') or para.startswith('▶') or para.startswith('◆'):
                if '\n' not in para and len(para) < 80:
                    body_html += f"<h2>{para}</h2>\n"
                else:
                    body_html += f"<p>{para}</p>\n"
            else:
                body_html += f"<p>{para}</p>\n"
                
    tags_html = ""
    if tags:
        tag_matches = re.findall(r'#[^\s,]+', tags)
        if tag_matches:
            tags_html += '<div class="tags-container">\n'
            for tag in tag_matches:
                tags_html += f'  <span class="tag">{tag}</span>\n'
            tags_html += '</div>'
            
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{clean_title} - 네이버 블로그 미리보기</title>
  <style>
    body {{
      background-color: #f4f6f9;
      margin: 0;
      padding: 40px 20px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans KR", sans-serif;
      color: #333333;
      display: flex;
      justify-content: center;
    }}
    .container {{
      max-width: 720px;
      width: 100%;
      background-color: #ffffff;
      padding: 40px;
      box-sizing: border-box;
      border-radius: 12px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
      border: 1px solid #e1e4e6;
    }}
    h1 {{
      font-size: 26px;
      font-weight: 800;
      line-height: 1.4;
      margin-top: 10px;
      margin-bottom: 30px;
      color: #111111;
      border-bottom: 2px solid #00c73c;
      padding-bottom: 15px;
      word-break: keep-all;
    }}
    h2 {{
      font-size: 20px;
      font-weight: 700;
      line-height: 1.5;
      margin-top: 35px;
      margin-bottom: 15px;
      color: #222222;
      border-left: 4px solid #00c73c;
      padding-left: 12px;
    }}
    h3 {{
      font-size: 18px;
      font-weight: 700;
      line-height: 1.5;
      margin-top: 30px;
      margin-bottom: 12px;
      color: #333333;
    }}
    p {{
      font-size: 17px;
      line-height: 1.8;
      margin-top: 0;
      margin-bottom: 24px;
      color: #444444;
      word-break: break-all;
      white-space: pre-wrap;
    }}
    .tags-container {{
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px dashed #e1e4e6;
    }}
    .tag {{
      display: inline-block;
      background-color: #f1f3f5;
      color: #00c73c;
      padding: 6px 12px;
      font-size: 14px;
      border-radius: 20px;
      margin-right: 8px;
      margin-bottom: 8px;
      font-weight: 600;
    }}
    .seo-helper {{
      background-color: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 8px;
      padding: 15px;
      margin-bottom: 30px;
      font-size: 13px;
      color: #666;
    }}
    .seo-helper-title {{
      font-weight: 700;
      color: #333;
      margin-bottom: 5px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="seo-helper">
      <div class="seo-helper-title">💡 네이버 블로그 SEO 및 포스팅 가이드 (서버 미리보기)</div>
      본 미리보기는 글자 크기 17px, 줄간격 1.8의 모바일 가독성 최적화(최대 너비 720px)로 렌더링되었습니다.
    </div>
    <h1>{clean_title}</h1>
    {body_html}
    {tags_html}
  </div>
</body>
</html>"""
    return html

@router.post("/preview/html", response_model=CommonResponse)
def preview_html(
    req: PreviewHtmlRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user)
):
    """
    네이버 블로그의 미리보기용 구조화된 HTML 문서를 동적으로 렌더링 및 생성하고 활동 로그를 남깁니다.
    """
    try:
        html = generate_blog_html(req.content)
        
        if not current_user:
            return CommonResponse(ok=True, data={"html": html}, message="HTML 미리보기가 정상 생성되었습니다.")
        
        # 활동 로그 기록
        ip_addr = request.client.host if request.client else "127.0.0.1"
        user_agt = request.headers.get("user-agent", "Unknown")
        now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        act_log = ActivityLog(
            user_id=current_user.id,
            action="preview_open",
            target_type="result",
            target_id=None,
            metadata_json=json.dumps({"channel": req.channel, "source": "server_api"}),
            ip_address=ip_addr,
            user_agent=user_agt,
            created_at=now_stamp
        )
        db.add(act_log)
        db.commit()
        
        return CommonResponse(ok=True, data={"html": html}, message="HTML 미리보기가 정상 생성되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
