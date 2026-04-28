import streamlit as st
import os
import traceback
import datetime
import json
from google import genai
from dotenv import load_dotenv
from core.llm_engine import LLMEngine
from core.search_utils import SearchUtils
from core.cache_manager import CacheManager
from core.pdf_parser import PDFParser
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
    st.session_state.company_info = {}
if 'draft' not in st.session_state:
    st.session_state.draft = None
if 'reset_counter' not in st.session_state:
    st.session_state.reset_counter = 0
if 'classified_type' not in st.session_state:
    st.session_state.classified_type = "분류 중..."
if 'resume_text' not in st.session_state:
    st.session_state.resume_text = ""
if 'master_profile' not in st.session_state:
    st.session_state.master_profile = None

def clear_inputs():
    st.session_state.analysis_result = None
    st.session_state.company_info = {}
    st.session_state.draft = None
    st.session_state.reset_counter += 1
    st.session_state.classified_type = "분류 중..."
    st.session_state.resume_text = ""
    st.session_state.master_profile = None
    logger.info("🧹 사용자 요청으로 입력 내용 및 결과 초기화됨")

def clear_company_cache(cache_mgr, company_name):
    if cache_mgr.delete_company_cache(company_name):
        st.session_state.company_info = {}
        st.success(f"✅ '{company_name}'의 캐시 파일이 삭제되었습니다.")
        logger.info(f"🔄 '{company_name}' 캐시 강제 삭제 완료")
    else:
        st.warning("삭제할 캐시 파일이 없습니다.")

def render_company_info(info: dict):
    """JSON 형식의 기업 정보를 예쁘게 렌더링합니다."""
    if not info:
        return
    
    st.markdown(f"### 🏢 {info.get('company_name', '기업 정보')}")
    st.info(f"📅 **최종 업데이트**: {info.get('last_updated', '-')}")
    
    st.markdown("**🎯 비전 및 미션**")
    st.write(info.get('vision_mission', '-'))
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**💎 핵심 가치 (Core Values)**")
        for val in info.get('core_values', []):
            st.markdown(f"- {val}")
    with col2:
        st.markdown("**👤 인재상 (Ideal Candidate)**")
        for val in info.get('ideal_candidate', []):
            st.markdown(f"- {val}")
            
    st.markdown("**🚀 주요 사업 전략**")
    for strategy in info.get('business_strategy', []):
        with st.expander(f"🔹 {strategy.get('title', '전략')}"):
            st.write(strategy.get('description', '-'))
            
    st.markdown("**🛠️ 기술 로드맵**")
    st.write(", ".join(info.get('tech_roadmap', [])))

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
        
        st.info("💡 **모델 정보**\n- 검색: Gemma 4 26B\n- 분류: Gemma 3 12B\n- 분석/작성: Gemma 4 31B")
        
        st.markdown("---")
        st.subheader("📄 이력서 관리")
        
        if st.session_state.master_profile:
            st.success("✅ 이력서 분석 완료")
            with st.expander("📝 마스터 프로필 보기"):
                mp = st.session_state.master_profile
                st.markdown(f"**요약**: {mp.candidate_summary}")
                st.markdown(f"**기술 스택**: {', '.join(mp.tech_stack)}")
                st.markdown(f"**학력 및 자격**: {', '.join(mp.education_and_certs)}")
            if st.button("❌ 이력서 초기화"):
                st.session_state.resume_text = ""
                st.session_state.master_profile = None
                st.rerun()
        else:
            uploaded_file = st.file_uploader("이력서 업로드 (PDF, TXT)", type=["pdf", "txt"])
            if uploaded_file:
                if uploaded_file.type == "application/pdf":
                    with open("temp_resume.pdf", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.session_state.resume_text = PDFParser.extract_text("temp_resume.pdf")
                    os.remove("temp_resume.pdf")
                else:
                    st.session_state.resume_text = uploaded_file.read().decode("utf-8")
                
                if st.button("🔍 이력서 구조화 분석 시작", use_container_width=True, type="primary"):
                    with st.spinner("이력서를 분석하여 마스터 프로필을 생성 중입니다..."):
                        st.session_state.master_profile = llm.parse_resume(st.session_state.resume_text)
                        st.rerun()

        st.markdown("---")
        st.subheader("📋 작성 옵션")
        st.caption("✨ **AI 자동 분류 적용됨**")
        
        target_length = st.select_slider(
            "목표 글자 수 (공백 포함)",
            options=[300, 500, 700, 800, 1000, 1200, 1500],
            value=1000,
            help="AI가 이 글자 수의 80~85% 수준을 목표로 보수적으로 작성하여 수정할 여유 공간을 남깁니다. (글자 수 초과 방지)"
        )

        st.markdown("---")
        st.subheader("🧹 데이터 관리")
        if st.button("🔄 현재 진행 상태 초기화", use_container_width=True):
            clear_inputs()
            st.rerun()

    col_left, col_right = st.columns([1.1, 1.3], gap="large")

    with col_left:
        st.subheader("1. 🎯 타겟 정보")
        with st.container(border=True):
            c_col1, c_col2, c_col3 = st.columns([2, 2, 1])
            with c_col1:
                company = st.text_input("🏢 지원 기업", value="삼성전자")
            with c_col2:
                role = st.text_input("💻 지원 직무", value="백엔드 개발자")
            with c_col3:
                q_num = st.text_input("🔢 문항 번호", value="1")
            
            col_btn1, col_btn2 = st.columns([3, 1])
            with col_btn1:
                if st.button(f"🔍 '{company}' 기업 정보 불러오기", use_container_width=True):
                    with st.spinner(f"'{company}' 정보를 확인 중입니다..."):
                        comp_info = cache.load_company_data(company)
                        if not comp_info:
                            comp_info = searcher.search_company_info(company)
                            cache.save_company_data(company, comp_info)
                            st.toast(f"✅ '{company}' 정보를 새로 검색하여 저장했습니다.", icon="✨")
                        else:
                            st.toast(f"✅ 로컬에 저장된 '{company}' 정보를 불러왔습니다.", icon="📦")
                        st.session_state.company_info = comp_info
            with col_btn2:
                if st.button("🔄 강제 새로고침", help="기존 캐시를 삭제하고 최신 정보를 다시 검색합니다.", use_container_width=True):
                    clear_company_cache(cache, company)
                    st.toast(f"'{company}' 캐시가 삭제되었습니다. 다시 불러오기를 눌러주세요.", icon="🗑️")
            
            if st.session_state.company_info:
                with st.expander(f"🏢 {company} 분석 데이터 (클릭하여 확인)", expanded=False):
                    render_company_info(st.session_state.company_info)

        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("2. ✍️ 자기소개서 작성")
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
        
        if st.session_state.analysis_result is not None and not st.session_state.analysis_result.is_sufficient:
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("3. 💬 면접관 추가 질문 답변")
            
            feedback_answer = st.text_area(
                "우측 '분석 및 피드백' 탭의 면접관 질문을 확인하고 보완 내용을 적어주세요.", 
                height=120, 
                key=f"fb_input_{st.session_state.reset_counter}"
            )
        else:
            feedback_answer = ""

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
                        draft_type = llm.classify_question(question)
                        st.session_state.classified_type = draft_type
                        
                        comp_info_dict = st.session_state.company_info
                        if not comp_info_dict:
                            comp_info_dict = cache.load_company_data(company)
                            if not comp_info_dict:
                                comp_info_dict = searcher.search_company_info(company)
                                cache.save_company_data(company, comp_info_dict)
                            st.session_state.company_info = comp_info_dict
                        
                        # 💡 기업 정보 최적화 (Token Targeting)
                        # 문항 유형에 따라 필요한 정보만 선별하여 텍스트로 변환
                        optimized_comp_info = ""
                        if draft_type == "지원동기":
                            optimized_comp_info = f"비전: {comp_info_dict.get('vision_mission')}\n핵심가치: {', '.join(comp_info_dict.get('core_values', []))}\n인재상: {', '.join(comp_info_dict.get('ideal_candidate', []))}"
                        elif draft_type in ["산업/사회이슈", "직무경험", "직무전문성"]:
                            strategies = "\n".join([f"- {s.get('title')}: {s.get('description')}" for s in comp_info_dict.get('business_strategy', [])])
                            optimized_comp_info = f"사업전략:\n{strategies}\n기술로드맵: {', '.join(comp_info_dict.get('tech_roadmap', []))}"
                        else:
                            optimized_comp_info = f"인재상: {', '.join(comp_info_dict.get('ideal_candidate', []))}\n핵심가치: {', '.join(comp_info_dict.get('core_values', []))}"

                        exp_to_analyze = experience
                        if st.session_state.master_profile:
                            mp = st.session_state.master_profile
                            context_info = f"[지원자 기본 정보]\n요약: {mp.candidate_summary}\n기술스택: {', '.join(mp.tech_stack)}\n\n[선택된 경험 원문]\n"
                            exp_to_analyze = context_info + experience

                        user_data = {
                            "company": company, "role": role, "q_num": q_num,
                            "question": question, "experience": exp_to_analyze,
                            "feedback_answer": feedback_answer
                        }
                        
                        logger.info("🧪 AI 경험 분석 및 진단 중...")
                        result = llm.analyze_experience(user_data, optimized_comp_info)
                        st.session_state.analysis_result = result
                        
                        if result.is_sufficient:
                            logger.info(f"✨ 분석 완료. 초안 생성 단계 진입")
                            draft = llm.generate_draft(user_data, result, draft_type, target_length)
                            st.session_state.draft = draft
                            file_path = cache.save_draft(company, role, q_num, result.question_keyword, draft)
                            st.session_state.file_path = file_path
                        else:
                            st.session_state.draft = None 
                            
                    except Exception as e:
                        logger.error(f"❌ 오류 발생: {str(e)}\n{traceback.format_exc()}")
                        st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
                        return
                
                logger.info("--- 🏁 프로세스 종료 ---")
                st.rerun()

        if st.session_state.analysis_result:
            res = st.session_state.analysis_result
            tab1, tab2, tab3 = st.tabs(["📝 분석 및 피드백", "✨ 최종 초안", "🏢 참고한 기업 정보"])
            
            with tab1:
                st.subheader("📊 역량 진단 리포트")
                st.info(f"🔍 AI 문항 성격 판단: **{st.session_state.classified_type}**")
                
                if not res.is_sufficient:
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
                        total_chars = len(st.session_state.draft)
                        st.info(f"📊 현재 초안 분량: **공백 포함 {total_chars}자** (목표: {target_length}자)")
                        st.caption(f"💾 자동 저장 위치: `{st.session_state.file_path}`")
                    with col_dl2:
                        st.download_button(
                            label="📝 마크다운(.md) 파일 다운로드", 
                            data=st.session_state.draft, 
                            file_name=os.path.basename(st.session_state.file_path),
                            use_container_width=True, type="primary"
                        )
                else:
                    st.info("아직 정보가 부족하여 초안이 생성되지 않았습니다. 피드백을 보고 내용을 보완해 주세요!")
                    
            with tab3:
                st.subheader(f"🏢 {company} 분석 데이터")
                if st.session_state.company_info:
                    st.info("AI가 아래 수집된 정보를 바탕으로 분석을 진행했습니다.")
                    render_company_info(st.session_state.company_info)
        else:
            st.info("👈 좌측에 정보를 입력하고 **[정밀 분석 및 초안 생성]** 버튼을 누르면 이 곳에 결과가 나타납니다.")
            with st.container(border=True):
                st.markdown("""
                **💡 이용 가이드**
                1. 타겟 기업과 직무를 명확히 적어주세요.
                2. 자소서 문항을 입력하면 **AI가 문항의 성격(지원동기/경험/인성)을 자동으로 분류**합니다.
                3. AI가 부족한 부분을 찾아 꼬리 질문을 던지면, 핑퐁 대화하듯 답변을 추가해 주세요.
                4. 내용이 충분해지면 선택한 **목표 글자 수**에 맞춰 자소서가 자동 생성됩니다!
                """)

if __name__ == "__main__":
    main()
