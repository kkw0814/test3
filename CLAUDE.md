# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
텍스트를 입력하고 [영어/일본어/베트남어] 버튼을 누르면 AI가 번역문과 한국어 발음(한글 표기)을 보여주는 Streamlit 웹 앱입니다. 코드는 전부 `app.py` 한 파일이며, 요구사항은 `PRD.md`, 단계별 개발 프롬프트는 `PROMPTS.md`에 있습니다.

## 명령어
Windows 기준이며, 가상환경은 프로젝트 안의 `.venv`를 사용합니다.
- 설치: `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- 실행: `.venv\Scripts\python.exe -m streamlit run app.py` (기본 http://localhost:8501)
- 린트/테스트 체계는 없습니다. 동작 검증은 `streamlit.testing.v1.AppTest`(Streamlit 내장)나 Playwright로 합니다.
  - `AppTest.from_file()`은 호출한 스크립트 기준 상대경로로 찾으므로 `app.py`의 절대경로를 넘겨야 합니다.
  - `load_dotenv()`도 호출한 파일 위치에서 `.env`를 찾습니다. 임시 스크립트에서 직접 호출하면 경로를 명시해야 합니다.

## 아키텍처
`app.py`는 위에서 아래로 실행되는 단일 Streamlit 스크립트입니다.
- `translate(text, target_language)`: OpenAI Chat Completions를 호출하고 `{"translation", "pronunciation"}`를 반환합니다. 시스템 프롬프트가 JSON 응답을 강제하고, `response_format=json_object`를 사용합니다. `parse_translation()`이 파싱하며, JSON이 아니면 전체를 번역문으로 취급하고 발음만 생략합니다.
- 모든 사용자 노출 오류는 `TranslationError`로 변환됩니다(키 누락/오류, 한도 초과, 타임아웃, 네트워크, 그 외). `handle_translate()`가 입력 검증(빈 입력, 5,000자 초과)과 예외 처리를 맡고, 성공 시 `st.session_state["result"]`에 저장합니다. 결과 영역은 이 값을 읽어 그립니다.
- 설정(`OPENAI_API_KEY`, `MODEL_NAME`)은 `get_setting()`이 환경변수(`.env`)를 먼저, 없으면 `st.secrets`(배포 환경)를 봅니다. `MODEL_NAME` 기본값은 `gpt-6.1-sol`입니다.
- 테마와 툴바 설정은 `.streamlit/config.toml`에 있습니다. 라이트/다크를 `[theme.light]`/`[theme.dark]`로 따로 정의해야 시스템 설정을 따릅니다(`[theme]` 하나만 쓰면 다크 모드가 적용되지 않음). `base` 키는 유효하지 않습니다.

## 주의할 점
- `gpt-6.1-sol`은 `temperature`를 지원하지 않습니다(기본값 1만 허용, 지정하면 400 오류). 파라미터를 추가하지 마세요.
- `.env`에는 API 키가 있습니다. 내용을 출력하거나 읽지 말고, 필요하면 항목 이름만 확인하세요.
- 글자 수 표시는 입력창에서 포커스를 벗어나거나 Ctrl+Enter를 눌러야 갱신됩니다. 입력 중 실시간 갱신이 필요하다고 `max_chars`를 쓰면 5,000자 초과 붙여넣기가 조용히 잘리니 쓰지 마세요.
- Windows 크롬은 국기 이모지를 `US`/`JP`/`VN` 글자로 표시합니다.
- 번역 시간은 글자 수에 비례합니다(실측 1,000자당 약 8~9초, 5,000자는 약 53초). 그래서 타임아웃은 90초이고 SDK 자동 재시도는 끄고(`MAX_RETRIES = 0`) 있습니다. 타임아웃을 줄이거나 재시도를 켜면 긴 입력이 실패하거나 오류 안내가 크게 늦어집니다.
- `handle_translate()`는 시작할 때 이전 결과를 지웁니다. 경고/오류 아래에 이전 번역이 남지 않게 하려는 것이므로 없애지 마세요.
- 의존성 버전은 `requirements.txt`에 고정되어 있습니다(streamlit 1.67.0, openai 3.52.0, python-dotenv 1.2.4).

## 언어 규칙
응답, 코드 주석, 커밋 메시지, 문서는 한국어로 작성하고, 변수명/함수명은 영어를 사용합니다.
