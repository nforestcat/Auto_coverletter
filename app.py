import streamlit as st
import os
import traceback
import datetime
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
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'company_info' not in st.session_state:
    st.session_state.company_info = ""
if 'draft' not in st.session_state:
    st.session_state.draft = None
# 폼 입력을 위한 세션 (위젯 key와 충돌 방지용)
if 'reset_counter' not in st.session_state:
    st.session_state.reset_counter = 0

def clear_inputs():
    """기업/직무 정보를 제외한 모든 결과와 상태를 초기화합니다."""
    st.session_state.analysis_result = None
    st.session_state.company_info = ""
    st.session_state.draft = None
    # 위젯들을 강제 리렌더링하기 위해 카운터 증가
    st.session_state.reset_counter += 1
    logger.info("🧹 사용자 요청으로 입력 내용 및 결과 초기화됨")

def clear_company_cache(cache_mgr, company_name):
    """특정 기업의 로컬 캐시를 삭제하고 세션을 리셋합니다."""
    if cache_mgr.delete_company_cache(company_name):
        st.session_state.company_info = ""
        st.success(f"✅ '{company_name}'의 캐시 파일이 삭제되었습니다.")
        logger.info(f"🔄 '{company_name}' 캐시 강제 삭제 완료")
    else:
        st.warning("삭제할 캐시 파일이 없습니다.")

def main():
    load_dotenv()
    cache = CacheManager()
    
    st.title("🕵️ CV-Auto: 실무 면접관 AI 컨설턴트")
    st.markdown("지원 기업의 인재상을 분석하고, 내 경험을 STAR 기법으로 정밀 진단받아 보세요.")
    st.markdown("---")

    # 사이드바 설정
    with st.sidebar:
        st.header("⚙️ 시스템 설정")
        api_key = st.text_input("Gemini API Key", type="password", value=os.getenv("GEMINI_API_KEY", ""))
        
        if not api_key:
            st.warning("👈 서비스를 시작하려면 API Key를 입력해 주세요.")
            return
            
        client = genai.Client(api_key=api_key)
        llm = LLMEngine(client)
        searcher = SearchUtils(client)
        
        st.info("💡 **모델 정보**\n- 검색: Gemma 4 26B\n- 분석: Gemma 4 31B")
        
        st.markdown("---")
        st.subheader("🧹 캐시 및 데이터 관리")
        
        if st.button("🔄 현재 진행 상태 초기화", use_container_width=True, help="작성 중인 내용과 분석 결과를 모두 지웁니다."):
            clear_inputs()
            st.rerun()

    # 메인 레이아웃: 좌측(입력), 우측(결과/로그)
    col_left, col_right = st.columns([1.1, 1.3], gap="large")

    with col_left:
        # 1. 지원 기본 정보 (눈에 띄게 박스 처리)
        st.subheader("1. 🎯 타겟 정보")
        with st.container(border=True):
            c_col1, c_col2, c_col3 = st.columns([2, 2, 1])
            with c_col1:
                company = st.text_input("🏢 지원 기업", value="삼성전자")
            with c_col2:
                role = st.text_input("💻 지원 직무", value="백엔드 개발자")
            with c_col3:
                q_num = st.text_input("🔢 문항 번호", value="1")
            
            # 기업 캐시 삭제 버튼을 해당 기업 이름 아래에 작게 배치
            if st.button(f"'{company}' 데이터 새로 고침", key="refresh_cache", help="인터넷에서 최신 기업 정보를 다시 검색합니다."):
                clear_company_cache(cache, company)

        st.markdown("<br>", unsafe_allow_html=True)

        # 2. 자소서 내용 입력란
        st.subheader("2. ✍️ 자기소개서 작성")
        # reset_counter를 key에 포함시켜 초기화 버튼 클릭 시 폼이 비워지도록 유도
        question = st.text_area(
            "지원 항목 (문항 전체를 붙여넣으세요)", 
            height=100, 
            placeholder="예: 삼성전자에 지원한 이유와 입사 후 회사에서 이루고 싶은 꿈을 기술하십시오.", 
            key=f"q_input_{st.session_state.reset_counter}"
        )
        
        experience = st.text_area(
            "나의 경험 (자유 서술)", 
            height=250, 
            placeholder="어떤 프로젝트였나요? 무슨 문제가 있었고, 어떻게 해결했는지 편하게 적어주세요.", 
            key=f"exp_input_{st.session_state.reset_counter}"
        )
        
        # 3. AI 피드백 핑퐁 영역 (채팅 느낌)
        st.subheader("3. 💬 면접관 추가 질문 답변")
        st.info("우측 탭에서 AI 면접관의 꼬리 질문을 확인하고 이곳에 추가 답변을 적어주세요.")
        feedback_answer = st.text_area(
            "보완 내용 입력", 
            height=120, 
            placeholder="면접관의 질문에 대한 답변을 편하게 적어주세요.", 
            key=f"fb_input_{st.session_state.reset_counter}"
        )

        st.markdown("<br>", unsafe_allow_html=True)
        btn_analyze = st.button("🚀 실무 면접관 정밀 분석 및 초안 생성", use_container_width=True, type="primary")

    with col_right:
        if btn_analyze:
            if not experience or not question:
                st.error("⚠️ 문항과 경험 내용을 모두 입력해 주세요.")
            else:
                logger.info(f"--- 🚀 프로세스 시작: {company} ({q_num}번 문항) ---")
                with st.spinner(f"🕵️ [{company}] 맞춤형 AI 면접관이 서류를 검토 중입니다..."):
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
                            # 파일 저장
                            file_path = cache.save_draft(company, role, q_num, result.question_keyword, draft)
                            st.session_state.file_path = file_path
                            logger.info(f"💾 초안 저장 완료: {file_path}")
                        else:
                            logger.warning(f"⚠️ 정보 부족. 꼬리 질문 생성됨.")
                            # 충분하지 않을 때는 초안 제거
                            st.session_state.draft = None 
                            
                    except Exception as e:
                        logger.error(f"❌ 오류 발생: {str(e)}\n{traceback.format_exc()}")
                        st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
                
                logger.info("--- 🏁 프로세스 종료 ---")

        # 📊 우측 영역: 결과 렌더링 (Tabs 활용)
        if st.session_state.analysis_result:
            res = st.session_state.analysis_result
            
            # 탭 구조로 변경하여 화면을 깔끔하게 유지
            tab1, tab2, tab3 = st.tabs(["📝 분석 및 피드백", "✨ 최종 초안", "🏢 참고한 기업 정보"])
            
            with tab1:
                st.subheader("📊 역량 진단 리포트")
                
                if not res.is_sufficient:
                    # 정보 부족 시: 챗봇 형태의 UI로 꼬리질문 강조
                    with st.chat_message("assistant", avatar="🕵️"):
                        st.markdown("**면접관의 피드백 및 꼬리 질문**")
                        st.warning(res.follow_up_question)
                        st.caption("💡 좌측 '3. 면접관 추가 질문 답변' 란에 위 질문에 대한 답을 적고 다시 분석 버튼을 눌러주세요!")
                else:
                    st.success("🎉 **합격 수준의 정보가 모두 확보되었습니다! '최종 초안' 탭을 확인하세요.**")

                with st.expander("✅ Step 1: 기업 핏(Fit) 분석 결과", expanded=True):
                    st.write(res.fit_analysis)
                
                with st.expander("📋 Step 2: 평가 체크리스트", expanded=True):
                    for item in res.evaluation_checklists:
                        st.markdown(f"- {item}")
                        
            with tab2:
                if st.session_state.draft:
                    st.subheader("✨ 최종 자기소개서 초안")
                    st.markdown(st.session_state.draft)
                    
                    st.markdown("---")
                    col_dl1, col_dl2 = st.columns([1, 1])
                    with col_dl1:
                        st.caption(f"💾 자동 저장 위치: `{st.session_state.file_path}`")
                    with col_dl2:
                        st.download_button(
                            label="📝 마크다운(.md) 파일 다운로드", 
                            data=st.session_state.draft, 
                            file_name=os.path.basename(st.session_state.file_path),
                            use_container_width=True,
                            type="primary"
                        )
                else:
                    st.info("아직 정보가 부족하여 초안이 생성되지 않았습니다. 피드백을 보고 내용을 보완해 주세요!")
                    
            with tab3:
                st.subheader(f"🏢 {company} 분석 데이터")
                if st.session_state.company_info:
                    st.info("AI가 아래 수집된 정보를 바탕으로 분석을 진행했습니다.")
                    with st.container(height=400): # 긴 텍스트 스크롤 처리
                        st.text(st.session_state.company_info)
                else:
                    st.write("캐시된 기업 정보가 없습니다.")
        else:
            # 분석 전 초기 상태일 때 보여줄 가이드 화면
            st.info("👈 좌측에 정보를 입력하고 **[정밀 분석 및 초안 생성]** 버튼을 누르면 이 곳에 결과가 나타납니다.")
            
            with st.container(border=True):
                st.markdown("""
                **💡 이용 가이드**
                1. 타겟 기업과 직무를 명확히 적어주세요. (AI가 해당 기업의 인재상을 자동 검색합니다.)
                2. 자소서 문항과 본인의 경험을 의식의 흐름대로 편하게 적어주세요.
                3. AI가 부족한 부분을 찾아 꼬리 질문을 던지면, 핑퐁 대화하듯 답변을 추가해 주세요.
                4. 내용이 충분해지면 완벽한 구조의 자소서 초안이 자동 생성됩니다!
                """)

if __name__ == "__main__":
    main()