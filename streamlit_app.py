from __future__ import annotations

import os
import sys
from typing import Any, Dict, List
import re
from datetime import datetime, timezone

import requests
import streamlit as st
from dotenv import load_dotenv


# ---------------------------
# App / Config
# ---------------------------
st.set_page_config(page_title="YouTube 인기 동영상", page_icon="📺", layout="wide")
st.title("📺 YouTube 인기 동영상 (페이지당 30개)")
st.caption("YouTube Data API v3 · 썸네일 / 제목 / 채널명 / 조회수 · 새로고침 · 페이지 이동(Prev/Next)")

# Secrets / Env loading
# 1) Prefer Streamlit secrets (for deployment: .streamlit/secrets.toml or Cloud secrets)
# 2) Fallback to local .env for local development
try:
    # st.secrets is available inside Streamlit runtime
    YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY")  # type: ignore[attr-defined]
    DEFAULT_REGION = st.secrets.get("REGION_CODE", "KR")  # type: ignore[attr-defined]
except Exception:
    YOUTUBE_API_KEY = None
    DEFAULT_REGION = "KR"

if not YOUTUBE_API_KEY:
    load_dotenv()
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    DEFAULT_REGION = os.getenv("REGION_CODE", DEFAULT_REGION)

# ---------------------------
# Auth (Simple Login)
# ---------------------------
VALID_ID = "daeyong"
VALID_PW = "daeyong"


def require_login() -> None:
    if "authed" not in st.session_state:
        st.session_state.authed = False

    with st.sidebar:
        st.subheader("로그인")
        if not st.session_state.authed:
            with st.form("login_form", clear_on_submit=False):
                uid = st.text_input("ID")
                upw = st.text_input("Password", type="password")
                ok = st.form_submit_button("로그인")
            if ok:
                if uid == VALID_ID and upw == VALID_PW:
                    st.session_state.authed = True
                    st.success("로그인 성공")
                    st.rerun()
                else:
                    st.error("ID 또는 비밀번호가 올바르지 않습니다.")
        else:
            st.success("로그인됨")
            if st.button("로그아웃"):
                st.session_state.authed = False
                st.rerun()

    if not st.session_state.authed:
        st.info("로그인이 필요합니다. 사이드바에서 로그인해 주세요.")
        st.stop()


# Helper to describe where the API key came from
def _key_source() -> str:
    try:
        if "YOUTUBE_API_KEY" in st.secrets and (st.secrets.get("YOUTUBE_API_KEY") or "").strip():  # type: ignore[attr-defined]
            return "secrets.toml"
    except Exception:
        pass
    if os.getenv("YOUTUBE_API_KEY"):
        return ".env"
    return "(none)"
# ---------------------------
# Config Validation / Diagnostics
# ---------------------------
def validate_api_config() -> None:
    """Validate API key and provide helpful guidance.
    Stops the app with an error if key is missing or obviously invalid.
    """
    key = (YOUTUBE_API_KEY or "").strip()
    # Common placeholders to guard against
    placeholders = {"", "REPLACE_ME", "your_youtube_api_key_here"}
    if key in placeholders:
        st.error("유효한 YOUTUBE_API_KEY가 설정되지 않았습니다. 배포 환경에서는 .streamlit/secrets.toml, 로컬에서는 .env를 확인해 주세요.")
        with st.expander("설정 방법 보기"):
            st.markdown(
                """
                - 배포: `html_vibe_ict/.streamlit/secrets.toml`
                  ```toml
                  YOUTUBE_API_KEY = "YOUR_KEY"
                  REGION_CODE = "KR"
                  ```
                - 로컬: `html_vibe_ict/.env`
                  ```bash
                  YOUTUBE_API_KEY=YOUR_KEY
                  REGION_CODE=KR
                  ```
                - 참고: secrets가 존재하면 우선 사용되고, 값이 비어있으면 `.env`로 폴백합니다.
                """
            )
        st.stop()



# ---------------------------
# Helpers
# ---------------------------
API_URL = "https://www.googleapis.com/youtube/v3/videos"
CAT_API_URL = "https://www.googleapis.com/youtube/v3/videoCategories"


def _format_views(n: str | int) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _format_count_kr(n: str | int) -> str:
    """숫자를 한국식 축약 표기로 (만 단위) 표현. 예) 12500 -> '1.2만'"""
    try:
        num = int(n)
    except Exception:
        return str(n)
    if num >= 10000:
        val = num / 10000.0
        s = f"{val:.1f}만"
        return s.replace(".0만", "만")
    return f"{num:,}"


_DUR_RE = re.compile(r"PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?")


def _parse_duration_iso8601(s: str | None) -> str:
    """ISO8601 duration (e.g., 'PT5M32S', 'PT1H2M') -> 'H:MM:SS' or 'M:SS'"""
    if not s:
        return "-"
    m = _DUR_RE.fullmatch(s)
    if not m:
        return s
    h = int(m.group("h") or 0)
    mi = int(m.group("m") or 0)
    se = int(m.group("s") or 0)
    if h > 0:
        return f"{h}:{mi:02d}:{se:02d}"
    return f"{mi}:{se:02d}"


def _time_ago_kr(iso_ts: str | None) -> str:
    """RFC3339/ISO 형식의 publishedAt를 받아 'n일 전' 등 한국어 상대 시간으로 표시"""
    if not iso_ts:
        return "-"
    try:
        # '2024-01-01T12:34:56Z' -> aware datetime
        if iso_ts.endswith("Z"):
            dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(iso_ts)
        now = datetime.now(timezone.utc)
        diff = now - dt.astimezone(timezone.utc)
        sec = int(diff.total_seconds())
        if sec < 60:
            return "방금 전"
        m = sec // 60
        if m < 60:
            return f"{m}분 전"
        h = m // 60
        if h < 24:
            return f"{h}시간 전"
        d = h // 24
        if d < 7:
            return f"{d}일 전"
        w = d // 7
        if w < 5:
            return f"{w}주 전"
        mo = d // 30
        if mo < 12:
            return f"{mo}달 전"
        y = d // 365
        return f"{y}년 전"
    except Exception:
        return iso_ts


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def fetch_categories(api_key: str, region: str = "KR") -> Dict[str, str]:
    """YouTube Data API v3: videoCategories.list -> {categoryId: title} (assignable만).
    실패 시 빈 dict 반환.
    """
    try:
        params = {
            "part": "snippet",
            "regionCode": region,
            "key": api_key,
        }
        resp = requests.get(CAT_API_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        cat_map: Dict[str, str] = {}
        for it in data.get("items", []):
            if not it.get("snippet"):
                continue
            if it.get("snippet", {}).get("assignable") is False:
                # 일부 지역에서는 assignable 키가 없을 수 있음 -> 기본 수용
                pass
            cat_id = it.get("id")
            title = it.get("snippet", {}).get("title")
            if cat_id and title:
                cat_map[str(cat_id)] = title
        return cat_map
    except Exception:
        return {}

@st.cache_data(show_spinner=False, ttl=60)
def fetch_popular_videos(api_key: str, region: str = "KR", page_token: str | None = None, max_results: int = 30) -> Dict[str, Any]:
    """YouTube Data API v3: videos.list (chart=mostPopular)

    Returns the parsed JSON or raises an Exception if the request fails.
    """
    params = {
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular",
        "maxResults": max_results,
        "regionCode": region,
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token
    resp = requests.get(API_URL, params=params, timeout=20)
    if resp.status_code != 200:
        # Attempt to show error payload if present
        try:
            payload = resp.json()
        except Exception:
            payload = resp.text
        raise RuntimeError(f"YouTube API 요청 실패 (HTTP {resp.status_code}): {payload}")
    data = resp.json()
    if "items" not in data:
        raise RuntimeError(f"API 응답에 'items'가 없습니다: {data}")
    return data


# Require login before showing the rest of the app
require_login()
validate_api_config()

# ---------------------------
# Sidebar Controls
# ---------------------------
st.sidebar.header("옵션")
region = st.sidebar.text_input("국가 코드(ISO)", value=DEFAULT_REGION, help="예: KR, US, JP …")
st.sidebar.info("페이지당 30개 고정 · Prev/Next 버튼으로 이동")

with st.sidebar.expander("환경 정보"):
    src = _key_source()
    st.write(f"API 키 소스: {src}")
    st.write(f"Region: {region}")

# Search & Filters
st.sidebar.header("검색 / 필터")
query = st.sidebar.text_input("검색어 (제목·채널)", value="")

# Categories (dynamic)
cat_map = fetch_categories(YOUTUBE_API_KEY or "", region.strip() or "KR") if YOUTUBE_API_KEY else {}
cat_titles = list(cat_map.values())
title_to_id = {v: k for k, v in cat_map.items()}
selected_cats = st.sidebar.multiselect(
    "카테고리",
    options=cat_titles,
    default=cat_titles,  # 기본 전체 선택
)

# Pagination state
if "page_token" not in st.session_state:
    st.session_state.page_token = None  # current page token (for request)
if "prev_tokens" not in st.session_state:
    st.session_state.prev_tokens: List[str] = []  # stack of previous page tokens

top_cols = st.columns([1, 3])
with top_cols[0]:
    refresh = st.button("🔄 새로고침", type="primary")

if refresh:
    fetch_popular_videos.clear()
    st.session_state.page_token = None
    st.session_state.prev_tokens = []

# ---------------------------
# Validation
# ---------------------------
if not YOUTUBE_API_KEY:
    st.error("환경변수 YOUTUBE_API_KEY 가 설정되지 않았습니다. .env 파일을 확인해 주세요.")
    st.stop()

# ---------------------------
# Fetch and Render
# ---------------------------
try:
    with st.spinner("인기 동영상을 불러오는 중…"):
        data = fetch_popular_videos(
            api_key=YOUTUBE_API_KEY,
            region=region.strip() or "KR",
            page_token=st.session_state.page_token,
            max_results=30,
        )
    items: List[Dict[str, Any]] = data.get("items", [])
    next_token = data.get("nextPageToken")

    # Prev/Next controls (now that we know tokens)
    nav_cols = st.columns([1, 2, 1])
    with nav_cols[0]:
        prev_click = st.button("⬅️ Prev", disabled=(len(st.session_state.prev_tokens) == 0))
    with nav_cols[2]:
        next_click = st.button("Next ➡️", disabled=(not bool(next_token)))

    # Handle clicks
    if prev_click and st.session_state.prev_tokens:
        st.session_state.page_token = st.session_state.prev_tokens.pop()
        st.rerun()
    if next_click:
        if next_token:
            if st.session_state.page_token:
                st.session_state.prev_tokens.append(st.session_state.page_token)
            st.session_state.page_token = next_token
            st.rerun()
        else:
            st.info("다음 페이지가 없습니다.")

    # Page indicator
    page_num = len(st.session_state.prev_tokens) + 1
    st.write(f"현재 페이지: {page_num}")

    # Prepare view count slider bounds
    view_counts = [int((it.get("statistics", {}) or {}).get("viewCount", 0) or 0) for it in items]
    vmin = min(view_counts) if view_counts else 0
    vmax = max(view_counts) if view_counts else 0
    vmin, vmax = int(vmin), int(vmax)
    if vmin > vmax:
        vmin, vmax = 0, 0
    st.sidebar.subheader("조회수 범위")
    sel_min, sel_max = st.sidebar.slider(
        "조회수",
        min_value=vmin,
        max_value=vmax if vmax > 0 else 0,
        value=(vmin, vmax) if vmax > 0 else (0, 0),
        step=max(1, (vmax - vmin) // 100 if vmax - vmin > 100 else 1),
        help="예: 1,000,000 ~ 10,000,000",
    )

    # Apply filters
    def _match_query(title: str, channel: str, q: str) -> bool:
        if not q:
            return True
        ql = q.lower()
        return (ql in (title or "").lower()) or (ql in (channel or "").lower())

    selected_cat_ids = {title_to_id[t] for t in selected_cats} if selected_cats else set()

    filtered: List[Dict[str, Any]] = []
    for it in items:
        snip = it.get("snippet", {})
        stats = it.get("statistics", {})
        cid = snip.get("categoryId")
        title = snip.get("title", "")
        channel = snip.get("channelTitle", "")
        v = int(stats.get("viewCount", 0) or 0)

        if selected_cat_ids and cid not in selected_cat_ids:
            continue
        if not _match_query(title, channel, query):
            continue
        if not (sel_min <= v <= sel_max):
            continue
        filtered.append(it)

    if not filtered:
        st.info("표시할 동영상이 없습니다.")
    else:
        for item in filtered:
            vid = item.get("id")
            snip = item.get("snippet", {})
            stats = item.get("statistics", {})
            details = item.get("contentDetails", {})
            title = snip.get("title", "(제목 없음)")
            channel = snip.get("channelTitle", "(채널 없음)")
            thumbs = snip.get("thumbnails", {})
            thumb_url = (
                thumbs.get("medium", {}).get("url")
                or thumbs.get("high", {}).get("url")
                or thumbs.get("default", {}).get("url")
            )
            views = _format_views(stats.get("viewCount") or 0)
            likes = _format_count_kr(stats.get("likeCount") or 0)
            comments = _format_count_kr(stats.get("commentCount") or 0)
            duration = _parse_duration_iso8601(details.get("duration"))
            published_ago = _time_ago_kr(snip.get("publishedAt"))
            video_url = f"https://www.youtube.com/watch?v={vid}" if vid else None

            with st.container(border=True):
                cols = st.columns([1, 3])
                with cols[0]:
                    if thumb_url:
                        st.image(thumb_url, width='stretch')
                with cols[1]:
                    if video_url:
                        st.markdown(f"**[{title}]({video_url})**")
                    else:
                        st.markdown(f"**{title}**")
                    st.write(f"채널: {channel}")
                    st.write(f"조회수: {views}")
                    # 이모지로 꾸민 통계 라인
                    st.write(f"👍 {likes} | 💬 {comments} | ⏱️ {duration} | 📅 {published_ago}")

except Exception as e:
    st.error("동영상 목록을 불러오는 중 오류가 발생했습니다.")
    with st.expander("오류 상세 보기"):
        st.exception(e)
