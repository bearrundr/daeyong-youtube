# YouTube 인기 동영상 Streamlit 앱 (페이지당 30개)

간단한 YouTube Data API v3 예제 앱입니다. 지역 코드 기준 인기 동영상을 페이지당 30개씩 보여줍니다. 썸네일, 제목, 채널명, 조회수는 물론, 좋아요/댓글/동영상 길이/업로드 상대 시간까지 표시하며, 새로고침과 Prev/Next 페이지 이동, 에러 처리를 포함합니다.

## 기능
- 페이지당 30개 동영상 리스트(고정)
- 썸네일, 제목(유튜브 링크), 채널명, 조회수 표시
- 통계 확장 표시: 좋아요(👍), 댓글(💬), 동영상 길이(⏱️), 업로드 상대 시간(📅)
  
  예) `👍 1.2만 | 💬 234 | ⏱️ 5:32 | 📅 2일 전`
- 새로고침 버튼(캐시 무효화)
- Prev/Next 페이지 이동(YouTube API `pageToken` 사용)
- 기본적인 에러 처리(오류 메시지 / 상세 보기)
- 검색/필터링
  - 제목·채널명 텍스트 검색
  - 카테고리 멀티선택(YouTube `videoCategories.list`로 동적 로드)
  - 조회수 범위 슬라이더 (최소~최대)

## 파일 구성
```
html_vibe_ict/
├── streamlit_app.py   # 메인 앱
├── requirements.txt   # 의존성
└── .env.example       # 환경 변수 예시 (복사하여 .env 로 사용)
```

## 사전 준비 (환경 변수)
`.env.example`를 복사해 `.env` 파일을 만들고 API 키를 입력하세요.

```
YOUTUBE_API_KEY=your_youtube_api_key_here
REGION_CODE=KR   # 선택(기본 KR)
```

> 주의: 실제 키가 저장된 `.env` 파일은 깃에 커밋하지 마세요.

## 설치 및 실행
uv(권장) 사용 예시:

```bash
# 의존성 설치 (현재 디렉터리가 html_vibe_ict/가 아니면 경로를 맞춰주세요)
uv pip install -r html_vibe_ict/requirements.txt

# 앱 실행 (프로젝트 루트에서)
uv run streamlit run html_vibe_ict/streamlit_app.py

# 또는 html_vibe_ict 디렉터리로 이동한 상태라면
uv run streamlit run streamlit_app.py
```

pip 사용 예시:

```bash
pip install -r html_vibe_ict/requirements.txt
streamlit run html_vibe_ict/streamlit_app.py
```

## 사용 방법
- 사이드바에서 국가 코드(ISO, 기본 `KR`)를 입력합니다.
- 검색 / 필터
  - "검색어 (제목·채널)"에 텍스트를 입력하면 실시간으로 필터링됩니다.
  - "카테고리"는 YouTube API에서 동적으로 불러온 목록으로 멀티 선택 가능합니다(기본 전체 선택).
  - "조회수" 슬라이더로 표시 범위를 지정할 수 있습니다.
- 메인 상단의 버튼으로 새로고침(캐시 초기화), Prev/Next로 페이지 이동을 할 수 있습니다.
- 각 아이템은 썸네일과 함께 제목(유튜브로 링크), 채널명, 조회수 및 확장 통계를 표시합니다.

## 동작 원리 (요약)
- `videos.list` (chart=mostPopular) 엔드포인트를 호출하여 인기 동영상을 가져옵니다.
- `part=snippet,statistics,contentDetails`로 확장 정보를 함께 가져옵니다.
- `maxResults=30` 고정, `pageToken`으로 다음/이전 페이지를 탐색합니다.
- `@st.cache_data(ttl=60)`로 60초 캐시, 새로고침 버튼으로 캐시를 무효화합니다.

### 내부 포맷팅 도우미
- 숫자 축약(`1.2만`): `_format_count_kr()`
- ISO8601 길이 → `H:MM:SS`/`M:SS`: `_parse_duration_iso8601()`
- 업로드 상대 시간(한국어): `_time_ago_kr()`

### 검색/필터 동작
- 카테고리 목록은 `videoCategories.list`로 지역 코드에 맞춰 불러옵니다(캐시 6시간).
- 필터링은 현재 페이지(30개) 아이템에 대해 클라이언트에서 수행합니다.

### 버튼/페이지네이션 동작 변경
- Prev/Next 버튼은 API 응답을 받은 후에 표시되며, 가능한 경우에만 활성화됩니다.
- `nextPageToken`이 없으면 Next 버튼은 비활성화되고, 클릭 시 안내 메시지를 표시합니다.

### Streamlit 경고 대응
- `st.image(..., use_container_width=True)`는 경고가 있어 `width='stretch'`로 교체했습니다.

## 배포 환경(Secrets) 설정
로컬에서는 `.env`를 사용하고, 배포 시에는 Streamlit Secrets를 사용합니다.

1) 로컬 개발(.env)
```
YOUTUBE_API_KEY=your_youtube_api_key_here
REGION_CODE=KR
```

2) 배포(Secrets)
- `html_vibe_ict/.streamlit/secrets.toml` 파일을 생성하고 다음 키를 넣습니다.
```toml
YOUTUBE_API_KEY = "your_youtube_api_key_here"
REGION_CODE = "KR"
```
- Streamlit Cloud 사용 시 프로젝트 Settings의 Secrets에 동일 키를 추가하면 됩니다.

앱은 먼저 `st.secrets`에서 값을 읽고, 없으면 `.env`로 폴백하도록 구현되어 있습니다.

## 문제 해결
- API 키 오류: `.env`의 `YOUTUBE_API_KEY`가 정확한지 확인하세요.
- 쿼ота(Quota) 초과: 잠시 후 다시 시도하거나 API 콘솔에서 할당량을 확인하세요.
- 네트워크/HTTP 오류: 화면의 "오류 상세 보기"에서 응답 본문을 확인하세요.
- Next 버튼 클릭 시 오류:
  - 페이지 토큰이 더 이상 없으면(=마지막 페이지) Next 버튼이 비활성화됩니다. 활성화되지 않거나 안내 메시지가 나오면 정상 동작입니다.
  - 일시적 API 오류일 수 있으니 새로고침 한 뒤 다시 시도하세요.
