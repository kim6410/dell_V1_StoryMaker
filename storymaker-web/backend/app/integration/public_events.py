# -*- coding: utf-8 -*-
"""Korea Tourism Organization TourAPI integration for StoryMaker local SEO context."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
DEFAULT_BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
DEFAULT_APP_NAME = "StoryMaker"


class PublicEventsError(RuntimeError):
    pass


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    root = payload.get("response") if isinstance(payload.get("response"), dict) else payload
    header = root.get("header") or {}
    result_code = str(header.get("resultCode") or "").strip()
    if result_code and result_code not in {"0000", "00"}:
        raise PublicEventsError(str(header.get("resultMsg") or result_code))
    body = root.get("body") or {}
    items = body.get("items") or {}
    if not items:
        return []
    rows = items.get("item") if isinstance(items, dict) else items
    if rows is None:
        return []
    if isinstance(rows, dict):
        return [rows]
    return [row for row in rows if isinstance(row, dict)]


def _body(payload: dict[str, Any]) -> dict[str, Any]:
    root = payload.get("response") if isinstance(payload.get("response"), dict) else payload
    return root.get("body") or {}


def _parse_yyyymmdd(value: str) -> str:
    raw = re.sub(r"[^0-9]", "", str(value or ""))[:8]
    if len(raw) != 8:
        return ""
    try:
        return datetime.strptime(raw, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _region_key(value: str) -> str:
    text = re.sub(r"\s+", "", str(value or "")).lower()
    for suffix in ("특별자치도", "특별자치시", "특별시", "광역시"):
        text = text.replace(suffix, "")
    return text


@dataclass
class TourAPIClient:
    service_key: str | None = None
    base_url: str | None = None
    mobile_app: str | None = None
    timeout: float = 8.0

    def __post_init__(self) -> None:
        self.service_key = (self.service_key or os.getenv("TOUR_API_KEY") or os.getenv("TOUR_API_SERVICE_KEY") or "").strip()
        self.base_url = (self.base_url or os.getenv("TOUR_API_BASE") or DEFAULT_BASE_URL).rstrip("/")
        self.mobile_app = (self.mobile_app or os.getenv("TOUR_API_MOBILE_APP") or DEFAULT_APP_NAME).strip() or DEFAULT_APP_NAME
        self.cache_dir = Path(os.getenv("STORYMAKER_PUBLIC_EVENTS_CACHE_DIR", "/data/public_events_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        return bool(self.service_key)

    def _cache_path(self, endpoint: str, params: dict[str, Any]) -> Path:
        raw = endpoint + "|" + json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{endpoint}_{digest}.json"

    def _read_cache(self, path: Path, ttl: int) -> dict[str, Any] | None:
        try:
            stat = path.stat()
            if time.time() - stat.st_mtime > ttl:
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_cache(self, path: Path, data: dict[str, Any]) -> None:
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except Exception:
            pass

    def request(self, endpoint: str, params: dict[str, Any] | None = None, ttl: int = 1800) -> dict[str, Any]:
        if not self.configured:
            raise PublicEventsError("TOUR_API_KEY is not configured")
        payload_params: dict[str, Any] = {
            "MobileOS": "WEB",
            "MobileApp": self.mobile_app,
            "_type": "json",
            **(params or {}),
        }
        cache_path = self._cache_path(endpoint, payload_params)
        cached = self._read_cache(cache_path, ttl)
        if cached is not None:
            return cached

        query = urllib.parse.urlencode(payload_params, doseq=True, quote_via=urllib.parse.quote)
        safe_key = urllib.parse.quote(str(self.service_key), safe="%")
        url = f"{self.base_url}/{endpoint}?serviceKey={safe_key}&{query}"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "StoryMaker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise PublicEventsError(f"TourAPI HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise PublicEventsError(f"TourAPI connection failed: {exc.reason}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PublicEventsError("TourAPI returned invalid JSON") from exc
        # Validate API-level errors before caching.
        _items(data)
        self._write_cache(cache_path, data)
        return data

    def regions(self) -> list[dict[str, str]]:
        rows = _items(self.request("ldongCode2", {"numOfRows": 100, "pageNo": 1}, ttl=86400))
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in rows:
            code = str(row.get("lDongRegnCd") or row.get("ldongregncd") or "").strip()
            name = _clean_text(row.get("lDongRegnNm") or row.get("ldongregnnm") or row.get("name"))
            signgu = str(row.get("lDongSignguCd") or row.get("ldongsigngucd") or "").strip()
            if code and name and not signgu and code not in seen:
                out.append({"code": code, "name": name})
                seen.add(code)
        return out

    def districts(self, region_code: str) -> list[dict[str, str]]:
        rows = _items(self.request("ldongCode2", {
            "numOfRows": 300,
            "pageNo": 1,
            "lDongRegnCd": region_code,
        }, ttl=86400))
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in rows:
            code = str(row.get("lDongSignguCd") or row.get("ldongsigngucd") or "").strip()
            name = _clean_text(row.get("lDongSignguNm") or row.get("ldongsigngunm") or row.get("name"))
            if code and name and code not in seen:
                out.append({"code": code, "name": name})
                seen.add(code)
        return out

    def resolve_region(self, region_text: str) -> tuple[dict[str, str] | None, dict[str, str] | None]:
        target = _region_key(region_text)
        if not target:
            return None, None
        regions = self.regions()
        matched_region = None
        for item in regions:
            key = _region_key(item["name"])
            short = re.sub(r"(도|시)$", "", key)
            if key and (key in target or short in target or target.startswith(short)):
                matched_region = item
                break
        if not matched_region:
            return None, None
        matched_district = None
        try:
            for item in self.districts(matched_region["code"]):
                dkey = _region_key(item["name"])
                if dkey and dkey in target:
                    matched_district = item
                    break
        except PublicEventsError:
            pass
        return matched_region, matched_district

    def festivals(
        self,
        start_date: date,
        end_date: date,
        region_code: str = "",
        district_code: str = "",
        page: int = 1,
        rows: int = 30,
        arrange: str = "Q",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "numOfRows": max(1, min(int(rows), 100)),
            "pageNo": max(1, int(page)),
            "arrange": arrange if arrange in {"A", "C", "D", "O", "Q", "R"} else "Q",
            "eventStartDate": start_date.strftime("%Y%m%d"),
            "eventEndDate": end_date.strftime("%Y%m%d"),
        }
        if region_code:
            params["lDongRegnCd"] = region_code
        if district_code and region_code:
            params["lDongSignguCd"] = district_code
        payload = self.request("searchFestival2", params, ttl=1800)
        body = _body(payload)
        normalized = [self._normalize_festival(row) for row in _items(payload)]
        return {
            "items": normalized,
            "total_count": int(body.get("totalCount") or len(normalized) or 0),
            "page": int(body.get("pageNo") or page),
            "rows": int(body.get("numOfRows") or rows),
        }

    def places(
        self,
        region_code: str = "",
        district_code: str = "",
        page: int = 1,
        rows: int = 30,
        arrange: str = "Q",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "numOfRows": max(1, min(int(rows), 100)),
            "pageNo": max(1, int(page)),
            "arrange": arrange if arrange in {"A", "C", "D", "O", "Q", "R"} else "Q",
        }
        if region_code:
            params["lDongRegnCd"] = region_code
        if district_code and region_code:
            params["lDongSignguCd"] = district_code
        payload = self.request("areaBasedList2", params, ttl=3600)
        body = _body(payload)
        normalized = [self._normalize_place(row) for row in _items(payload)]
        return {
            "items": normalized,
            "total_count": int(body.get("totalCount") or len(normalized) or 0),
            "page": int(body.get("pageNo") or page),
            "rows": int(body.get("numOfRows") or rows),
        }

    def festival_detail(self, content_id: str, content_type_id: str = "15") -> dict[str, Any]:
        common = _items(self.request("detailCommon2", {
            "contentId": content_id,
            "defaultYN": "Y",
            "firstImageYN": "Y",
            "areacodeYN": "Y",
            "catcodeYN": "Y",
            "addrinfoYN": "Y",
            "mapinfoYN": "Y",
            "overviewYN": "Y",
        }, ttl=21600))
        intro = _items(self.request("detailIntro2", {
            "contentId": content_id,
            "contentTypeId": content_type_id,
        }, ttl=21600))
        info = _items(self.request("detailInfo2", {
            "contentId": content_id,
            "contentTypeId": content_type_id,
        }, ttl=21600))
        images = _items(self.request("detailImage2", {
            "contentId": content_id,
            "imageYN": "Y",
            "subImageYN": "Y",
            "numOfRows": 30,
            "pageNo": 1,
        }, ttl=21600))
        common_row = common[0] if common else {}
        intro_row = intro[0] if intro else {}
        return {
            "content_id": str(content_id),
            "content_type_id": str(content_type_id),
            "title": _clean_text(common_row.get("title")),
            "address": " ".join(x for x in [_clean_text(common_row.get("addr1")), _clean_text(common_row.get("addr2"))] if x),
            "overview": _clean_text(common_row.get("overview")),
            "homepage": _clean_text(common_row.get("homepage")),
            "tel": _clean_text(common_row.get("tel")),
            "mapx": str(common_row.get("mapx") or ""),
            "mapy": str(common_row.get("mapy") or ""),
            "first_image": str(common_row.get("firstimage") or ""),
            "event_start_date": _parse_yyyymmdd(intro_row.get("eventstartdate")),
            "event_end_date": _parse_yyyymmdd(intro_row.get("eventenddate")),
            "event_place": _clean_text(intro_row.get("eventplace")),
            "sponsor": _clean_text(intro_row.get("sponsor1") or intro_row.get("sponsor2")),
            "playtime": _clean_text(intro_row.get("playtime")),
            "use_time": _clean_text(intro_row.get("usetimefestival")),
            "programs": [_clean_text(row.get("infotext") or row.get("infoname")) for row in info if _clean_text(row.get("infotext") or row.get("infoname"))],
            "images": [
                {
                    "url": str(row.get("originimgurl") or row.get("smallimageurl") or ""),
                    "thumbnail": str(row.get("smallimageurl") or ""),
                    "copyright_code": str(row.get("cpyrhtDivCd") or ""),
                    "serial": str(row.get("serialnum") or ""),
                }
                for row in images
                if row.get("originimgurl") or row.get("smallimageurl")
            ],
            "source": "한국관광공사 TourAPI",
        }

    @staticmethod
    def _normalize_festival(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "content_id": str(row.get("contentid") or ""),
            "content_type_id": str(row.get("contenttypeid") or "15"),
            "title": _clean_text(row.get("title")),
            "address": " ".join(x for x in [_clean_text(row.get("addr1")), _clean_text(row.get("addr2"))] if x),
            "tel": _clean_text(row.get("tel")),
            "start_date": _parse_yyyymmdd(row.get("eventstartdate")),
            "end_date": _parse_yyyymmdd(row.get("eventenddate")),
            "image": str(row.get("firstimage") or ""),
            "thumbnail": str(row.get("firstimage2") or ""),
            "mapx": str(row.get("mapx") or ""),
            "mapy": str(row.get("mapy") or ""),
            "region_code": str(row.get("lDongRegnCd") or row.get("areacode") or ""),
            "district_code": str(row.get("lDongSignguCd") or row.get("sigungucode") or ""),
            "festival_type": _clean_text(row.get("festivaltype")),
            "progress_type": _clean_text(row.get("progresstype")),
            "copyright_code": str(row.get("cpyrhtDivCd") or ""),
            "modified_time": str(row.get("modifiedtime") or ""),
            "source": "한국관광공사 TourAPI",
        }

    @staticmethod
    def _normalize_place(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "content_id": str(row.get("contentid") or ""),
            "content_type_id": str(row.get("contenttypeid") or ""),
            "title": _clean_text(row.get("title")),
            "address": " ".join(x for x in [_clean_text(row.get("addr1")), _clean_text(row.get("addr2"))] if x),
            "image": str(row.get("firstimage") or ""),
            "thumbnail": str(row.get("firstimage2") or ""),
            "mapx": str(row.get("mapx") or ""),
            "mapy": str(row.get("mapy") or ""),
            "region_code": str(row.get("lDongRegnCd") or row.get("areacode") or ""),
            "district_code": str(row.get("lDongSignguCd") or row.get("sigungucode") or ""),
            "source": "한국관광공사 TourAPI",
        }


def fetch_public_event_context_for_prompt(region_text: str, now: datetime | None = None, limit: int = 3) -> str:
    """Build a factual local SEO context block for Gemini. Never breaks generation."""
    client = TourAPIClient()
    if not client.configured or not str(region_text or "").strip():
        return ""
    now = now or datetime.now(KST)
    try:
        region, district = client.resolve_region(region_text)
        if not region:
            return ""

        start = now.date()
        end = start + timedelta(days=45)
        festivals = client.festivals(
            start_date=start,
            end_date=end,
            region_code=region["code"],
            district_code=(district or {}).get("code", ""),
            rows=max(limit * 4, 12),
            arrange="Q",
        ).get("items") or []
        festivals = [item for item in festivals if item.get("title")][:limit]

        places = client.places(
            region_code=region["code"],
            district_code=(district or {}).get("code", ""),
            rows=max(limit * 4, 12),
            arrange="Q",
        ).get("items") or []
        places = [item for item in places if item.get("title")][:limit]

        if not festivals and not places:
            return ""

        region_label = region.get("name") or str(region_text).strip()
        if district:
            region_label = f"{region_label} {district.get('name')}".strip()

        lines = [
            "### [한국관광공사 공공데이터 기반 지역 SEO 컨텍스트]",
            f"- 기준 지역: {region_label}",
            f"- 기준일: {start.isoformat()}",
            f"- 행사 조회 범위: {start.isoformat()} ~ {end.isoformat()}",
            "- 데이터 출처: 한국관광공사 TourAPI KorService2",
            "- 목적: 지역 생활 맥락과 검색 의도를 이해하기 위한 보조 데이터이며, 업체가 해당 행사와 직접 관계 있다는 뜻이 아닙니다.",
        ]

        if festivals:
            lines.append("")
            lines.append("#### 현재/예정 지역 축제·행사")
            for idx, event in enumerate(festivals, 1):
                period = " ~ ".join(x for x in [event.get("start_date"), event.get("end_date")] if x)
                parts = [event.get("title"), period, event.get("address")]
                detail = " / ".join(str(x) for x in parts if x)
                lines.append(f"{idx}. {detail}")

        if places:
            lines.append("")
            lines.append("#### 지역 관광·생활권 참고 장소")
            for idx, place in enumerate(places, 1):
                parts = [place.get("title"), place.get("address")]
                detail = " / ".join(str(x) for x in parts if x)
                lines.append(f"{idx}. {detail}")

        lines += [
            "",
            "#### Gemini 활용 지침",
            "1. 위 데이터는 '지역 분위기와 생활권을 이해하는 참고자료'입니다. 업체가 행사에 참여·후원·협찬·납품·시공했다는 사실은 입력자료에 명시되어 있지 않으면 절대 만들지 않습니다.",
            "2. 게시물의 실제 주제와 지역 행사가 자연스럽게 이어질 때만 1건 정도를 가볍게 언급합니다. 연관성이 낮으면 행사명은 본문에 넣지 않고 지역명·동네명만 SEO에 활용합니다.",
            "3. 축제명을 넣을 경우 날짜와 지역이 맞는지 확인하고, '요즘 ○○축제가 열리는 ○○ 일대', '주말 행사를 찾는 분들이 많은 시기'처럼 생활 맥락으로 연결합니다.",
            "4. 행사 자체를 소개하는 콘텐츠가 아니라면 행사 정보를 글의 중심으로 만들지 않습니다. 업체 서비스/사용자 입력내용이 항상 주인공입니다.",
            "5. 검색 노출을 위해 지역명 + 업종/서비스명 + 실제 문제/작업명을 제목·첫 문단·소제목·해시태그에 자연스럽게 분산합니다. 동일 키워드를 기계적으로 반복하지 않습니다.",
            "6. 지역 관광명소는 상권·생활권·방문객 흐름을 설명하는 참고로만 사용합니다. '관광객이 많다', '유명하다' 같은 단정은 데이터나 입력자료에 근거가 없으면 피합니다.",
            "7. 기간이 지난 행사는 현재 진행 중인 것처럼 쓰지 않습니다. 예정 행사는 '예정', 진행 기간 안이면 '열리는 기간' 정도로만 표현합니다.",
            "8. 공공데이터에 없는 가격, 방문객 수, 후기, 순위, 인기도, 주차 가능 여부, 참가업체 정보는 지어내지 않습니다.",
            "9. 이미지 URL은 콘텐츠 맥락 참고용입니다. 이미지 사용 시 별도 저작권/공공누리 조건을 확인해야 하므로 글 생성 단계에서는 사용 권한이 확보됐다고 단정하지 않습니다.",
            "10. 지역 SEO는 사람에게 자연스럽게 읽히는 문장을 우선합니다. 검색어 나열, 같은 지명 반복, 관련 없는 축제 끼워넣기는 금지합니다.",
        ]
        return "\n".join(lines)
    except Exception:
        return ""
