import json
import os

import streamlit as st
from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

# 로컬 실행 시 .env 파일의 값을 환경변수로 불러온다
load_dotenv()

# 번역 대상 언어 목록 (버튼 라벨 -> 프롬프트에 사용할 영어 언어명)
LANGUAGES = {
    "영어": "English",
    "일본어": "Japanese",
    "베트남어": "Vietnamese",
}

# 버튼에 표시할 국기 이모지
LANGUAGE_FLAGS = {
    "영어": "🇺🇸",
    "일본어": "🇯🇵",
    "베트남어": "🇻🇳",
}

DEFAULT_MODEL ="gpt-6.1-sol"
MAX_CHARS = 5000
# 번역 시간은 글자 수에 비례한다(실측 약 1,000자당 8~9초). 5,000자 입력도 처리되도록 넉넉히 둔다
REQUEST_TIMEOUT_SECONDS = 90
# SDK 기본 재시도(2회)가 타임아웃과 겹치면 오류 안내까지 3배가 걸리므로 재시도하지 않는다
MAX_RETRIES = 0

SYSTEM_PROMPT = (
    "You are a professional translator. "
    "Translate the user's text into {target_language}. "
    "Also write the pronunciation of the translated text in Korean (Hangul), "
    "so that a Korean speaker can read it aloud. "
    'Respond with only a JSON object in this form: {{"translation": "...", "pronunciation": "..."}}. '
    "Do not add explanations or quotes. "
    "Preserve the original tone, line breaks, and formatting in both fields, "
    "and keep the pronunciation line breaks aligned with the translation."
)


class TranslationError(Exception):
    """사용자에게 그대로 보여줄 수 있는 번역 오류."""


def get_setting(name: str, default: str | None = None) -> str | None:
    """환경변수(.env 포함)에서 먼저 찾고, 없으면 st.secrets(배포 환경)에서 찾는다."""
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name, default)
    except Exception:
        # secrets 파일이 없는 로컬 환경에서는 예외가 발생하므로 기본값을 사용한다
        return default


def parse_translation(content: str) -> dict[str, str]:
    """모델 응답(JSON)에서 번역문과 한국어 발음을 꺼낸다. JSON이 아니면 전체를 번역문으로 본다."""
    try:
        data = json.loads(content)
        translation = str(data.get("translation", "")).strip()
        pronunciation = str(data.get("pronunciation", "")).strip()
    except (json.JSONDecodeError, AttributeError):
        # 형식이 어긋난 응답도 번역문은 보여주고, 발음만 생략한다
        return {"translation": content.strip(), "pronunciation": ""}
    return {"translation": translation, "pronunciation": pronunciation}


def translate(text: str, target_language: str) -> dict[str, str]:
    """텍스트를 target_language(영어 언어명)로 번역하고 한국어 발음을 함께 반환한다.

    반환값: {"translation": 번역문, "pronunciation": 한국어 발음}
    실패 시 TranslationError를 발생시킨다.
    """
    api_key = get_setting("OPENAI_API_KEY")
    if not api_key:
        raise TranslationError(
            "API 키가 설정되지 않았습니다. .env 파일(또는 배포 환경의 Secrets)에 OPENAI_API_KEY를 등록해주세요."
        )
    model = get_setting("MODEL_NAME", DEFAULT_MODEL)

    client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=MAX_RETRIES)
    try:
        # gpt-6.1-sol은 temperature 변경을 지원하지 않아(기본값 1만 허용) 지정하지 않는다
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(target_language=target_language)},
                {"role": "user", "content": text},
            ],
        )
    except AuthenticationError:
        raise TranslationError("API 키가 올바르지 않습니다. 키를 확인해주세요.") from None
    except RateLimitError:
        raise TranslationError("요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.") from None
    except APITimeoutError:
        raise TranslationError("응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.") from None
    except APIConnectionError:
        raise TranslationError("네트워크 연결에 실패했습니다. 인터넷 연결을 확인해주세요.") from None
    except OpenAIError as error:
        # 키 등 민감 정보가 섞이지 않도록 예외 종류만 안내한다
        raise TranslationError(f"번역 중 오류가 발생했습니다. ({type(error).__name__})") from None

    result = parse_translation((response.choices[0].message.content or "").strip())
    if not result["translation"]:
        raise TranslationError("번역 결과가 비어 있습니다. 다시 시도해주세요.")
    return result


def handle_translate(label: str, language_name: str, text: str) -> None:
    """입력을 검증하고 번역한 뒤 결과를 session_state에 저장한다."""
    # 경고/오류 아래에 이전 번역이 남아 현재 입력의 결과로 오해되지 않도록 먼저 지운다
    st.session_state.pop("result", None)
    if not text.strip():
        st.warning("번역할 글을 입력해주세요.")
        return
    if len(text) > MAX_CHARS:
        st.warning(f"입력은 최대 {MAX_CHARS:,}자까지 가능합니다. (현재 {len(text):,}자)")
        return

    try:
        with st.spinner("번역 중입니다..."):
            translated = translate(text, language_name)
    except TranslationError as error:
        st.error(str(error))
        return
    except Exception:
        st.error("예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return

    st.session_state["result"] = {
        "label": label,
        "text": translated["translation"],
        "pronunciation": translated["pronunciation"],
    }


st.set_page_config(page_title="AI 번역기", page_icon="🌐", layout="centered")

# 헤더
st.title("🌐 AI 번역기")
st.caption("글을 입력하고 번역할 언어를 선택하세요.")

# 입력 영역
user_text = st.text_area(
    "번역할 글",
    height=200,
    placeholder="번역할 글을 입력하세요. (최대 5,000자)",
    label_visibility="collapsed",
)
# 글자 수 표시 (입력창에서 포커스가 벗어나거나 Ctrl+Enter를 누르면 갱신된다)
char_count = len(user_text)
count_text = f"{char_count:,} / {MAX_CHARS:,}자"
if char_count > MAX_CHARS:
    st.markdown(f":red[{count_text} · 글자 수를 초과했습니다]")
else:
    st.caption(count_text)

# 버튼 영역 (같은 너비 3열)
columns = st.columns(len(LANGUAGES))
for column, (label, language_name) in zip(columns, LANGUAGES.items()):
    if column.button(
        f"{LANGUAGE_FLAGS[label]} {label}", key=f"btn_{language_name}", use_container_width=True
    ):
        handle_translate(label, language_name, user_text)

# 결과 영역
result = st.session_state.get("result")
with st.container(border=True):
    if result:
        st.subheader(f"{result['label']} 번역 결과")
        st.code(result["text"], language=None, wrap_lines=True)
        if result["pronunciation"]:
            st.caption("한국어 발음")
            st.code(result["pronunciation"], language=None, wrap_lines=True)
    else:
        st.subheader("번역 결과")
        st.caption("아직 번역 결과가 없습니다. 위에서 글을 입력하고 언어 버튼을 눌러보세요.")
