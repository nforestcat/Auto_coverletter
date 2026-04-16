import streamlit as st
import os
import traceback
from google import genai
from dotenv import load_dotenv
from core.llm_engine import LLMEngine
from core.search_utils import SearchUtils
from core.cache_manager import CacheManager
from core.logger import get_logger

# 로거 초기화
logger = get_logger("StreamlitApp")

# 페이지 기본 설정
st.set_page_config(
    page_title="CV-Auto: 실무 면접관 AI 컨설턴트",
    page_icon="🕵️",
    layout="wide"
)

# 세션 상태 초기화
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'company_info' not in st.session_state:
    st.session_state.company_info = ""

def main():
    load_dotenv()
    cache = CacheManager()
    
    st.title("🕵️ CV-Auto: 실무 면접관 AI 컨설턴트")
    st.markdown("---")

    # 사이드바 설정
    with st.sidebar:
        st.header("⚙️ 설정")
        api_key = st.text_input("Gemini API Key", type="password", value=os.getenv("GEMINI_API_KEY", ""))
        if not api_key:
            st.warning("API Key를 입력해 주세요.")
            return
            
        client = genai.Client(api_key=api_key)
        llm = LLMEngine(client)
        searcher = SearchUtils(client)
        
        st.info("💡 모델 정보\n- 검색: Gemma 4 26B\n- 분석: Gemma 4 31B")

    # 메인 레이아웃: 좌측(입력), 우측(결과/로그)
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 지원 정보")
        c_col1, c_col2 = st.columns([3, 1])
        with c_col1:
            company = st.text_input("지원 기업", value="삼성전자")
        with c_col2:
            q_num = st.text_input("문항 번호", value="1")
        role = st.text_input("지원 직무", value="백엔드 개발자")
        
        st.subheader("2. 자기소개서 문항")
        question = st.text_area("지원 항목을 입력하세요", height=100, placeholder="예: 지원 동기와 입사 후 포부를 기술해 주십시오.")
        
        st.subheader("3. 나의 경험 (자유 서술)")
        experience = st.text_area("자신의 경험을 자유롭게 적어주세요", height=300, placeholder="당시 상황, 내가 한 행동, 결과 등을 자유롭게 서술하세요.", key="exp_input")
        
        st.subheader("💡 면접관 추가 질문 답변")
        feedback_answer = st.text_area("AI 면접관의 질문이 있을 경우 여기에 보완 내용을 적어주세요.", height=150, key="fb_input")

        btn_analyze = st.button("🚀 실무 면접관 정밀 분석 및 초안 생성", use_container_width=True, type="primary")

    with col2:
        st.subheader("📊 분석 결과 및 피드백")
        
        if btn_analyze:
            if not experience or not question:
                st.error("문항과 경험을 모두 입력해 주세요.")
            else:
                logger.info(f"--- 🚀 프로세스 시작: {company} ({q_num}번 문항) ---")
                with st.spinner(f"🕵️ [{company}] 실무 면접관이 서류를 검토 중입니다..."):
                    try:
                        # 1. 기업 정보 확보
                        comp_info = cache.load_company_data(company)
                        if not comp_info:
                            logger.info(f"🔍 기업 정보 실시간 검색 시작: {company}")
                            comp_info = searcher.search_company_info(company)
                            cache.save_company_data(company, comp_info)
                        else:
                            logger.info(f"📦 로컬 캐시 사용: {company}")
                        
                        st.session_state.company_info = comp_info
                        
                        # 2. 분석 실행
                        user_data = {
                            "company": company,
                            "role": role,
                            "q_num": q_num,
                            "question": question,
                            "experience": experience,
                            "feedback_answer": feedback_answer
                        }
                        logger.info("🧪 AI 경험 분석 및 진단 중...")
                        result = llm.analyze_experience(user_data, comp_info)
                        st.session_state.analysis_result = result
                        
                        # 3. 충분할 경우 초안 자동 생성
                        if result.is_sufficient:
                            logger.info("✨ 분석 완료. 초안 생성 단계 진입.")
                            draft = llm.generate_draft(user_data, result)
                            st.session_state.draft = draft
                            # 저장
                            file_path = cache.save_draft(company, role, q_num, result.question_keyword, draft)
                            st.session_state.file_path = file_path
                            logger.info(f"💾 초안 저장 완료: {file_path}")
                        else:
                            logger.warning(f"⚠️ 정보 부족. 꼬리 질문 생성됨: {result.follow_up_question[:50]}...")
                            
                    except Exception as e:
                        logger.error(f"❌ 오류 발생: {str(e)}\n{traceback.format_exc()}")
                        st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
                
                logger.info("--- 🏁 프로세스 종료 ---")

        # 결과 렌더링
        if st.session_state.analysis_result:
            res = st.session_state.analysis_result
            
            with st.expander("✅ Step 1: 기업 핏(Fit) 분석 결과", expanded=True):
                st.write(res.fit_analysis)
            
            with st.expander("📋 Step 2: 평가 체크리스트", expanded=True):
                for item in res.evaluation_checklists:
                    st.markdown(f"- {item}")
            
            if not res.is_sufficient:
                st.warning(f"🧐 **면접관의 꼬리 질문**\n\n{res.follow_up_question}")
                st.info("왼쪽 하단 '보완 답변' 칸에 내용을 채운 후 다시 버튼을 눌러주세요.")
            else:
                st.success("🎉 **축하합니다! 합격 수준의 정보가 확보되었습니다.**")
                if 'draft' in st.session_state:
                    st.markdown("---")
                    st.subheader("✨ 최종 자기소개서 초안")
                    st.markdown(st.session_state.draft)
                    st.caption(f"💾 저장 완료: {st.session_state.file_path}")
                    st.download_button("📝 마크다운 파일 다운로드", st.session_state.draft, file_name=os.path.basename(st.session_state.file_path))

if __name__ == "__main__":
    main()
