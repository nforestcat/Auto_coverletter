import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import json
import os
import re
import datetime
import traceback
import threading
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv, set_key

# 1. AI 응답 구조 정의 (Pydantic) - 면접관 관점 분석 데이터 추가
class ExperienceAnalysis(BaseModel):
    is_sufficient: bool = Field(description="정보가 충분한지 여부")
    fit_analysis: str = Field(description="Step 1: 문항 의도 및 기업 핏(Fit) 연결 분석 결과")
    evaluation_checklists: List[str] = Field(description="Step 2: 수립된 3가지 맞춤형 평가 기준 리스트")
    follow_up_question: str = Field(description="Step 3: 내용 평가에 따른 면접관의 부드러운 꼬리 질문")
    extracted_star: str = Field(description="추출된 STAR 구조 데이터")
    future_roadmap_plan: str = Field(description="입사 후 포부 전략")
    question_keyword: str = Field(description="파일명용 짧은 한국어 키워드")

# 2. AI 파이프라인 클래스
class CVAIProcessor:
    def __init__(self, api_key: str, log_func=None):
        self.client = genai.Client(api_key=api_key)
        self.research_model = 'gemma-4-26b-a4b-it'
        self.analysis_model = 'gemma-4-31b-it'
        self.company_dir = "company"
        self.draft_dir = "draft"
        self.log_func = log_func
        for directory in [self.company_dir, self.draft_dir]:
            if not os.path.exists(directory): os.makedirs(directory)

    def log(self, message: str):
        if self.log_func: self.log_func(message)

    def get_safe_filename(self, name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "_", name).strip()

    def ensure_company_data(self, company_name: str) -> str:
        safe_name = self.get_safe_filename(company_name)
        file_path = os.path.join(self.company_dir, f"{safe_name}.md")
        if os.path.exists(file_path):
            self.log(f"📦 로컬 캐시 발견: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f: return f.read()

        self.log(f"🔍 {self.research_model} 모델로 실시간 검색 시작...")
        prompt = f"""
        '{company_name}'에 대한 기업 정보를 다음 기준에 따라 검색하고 Markdown 형식으로 상세히 정리해 주세요.
        
        [검색 및 출처 기준 - 매우 중요]
        1. **공식 출처 최우선**: 반드시 해당 기업의 **공식 홈페이지** 및 **공식 채용 홈페이지(Recruit)**의 내용을 최우선으로 참고하세요.
        2. **비공식 정보 배제**: 나무위키, 개인 블로그, 카페, 커뮤니티 등 검증되지 않은 개인이 작성한 정보는 분석에서 철저히 제외하세요.
        3. **최신성 보장**: 최근 1년 이내의 공식 보도자료나 뉴스 기사를 통해 최신 사업 전략 키워드를 도출하세요.
        
        [정리 항목]
        - 기업의 비전 및 미션
        - 핵심 가치 (Core Values)
        - 인재상 (Ideal Candidate)
        - 최근 주요 사업 전략 및 기술 키워드
        """
        instruction = "당신은 전문 기업 분석가입니다. 반드시 Google Search 도구를 사용하여 공식적인 정보만을 선별하고 모든 내용을 한국어로 작성해야 합니다."
        google_search_tool = types.Tool(google_search=types.GoogleSearch())

        response = self.client.models.generate_content(
            model=self.research_model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=instruction, tools=[google_search_tool])
        )
        content = f"# [기업 정보] {company_name}\n\n" + response.text
        with open(file_path, "w", encoding="utf-8") as f: f.write(content)
        self.log(f"✅ 기업 정보 저장 완료.")
        return content

    def _extract_json(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match: return match.group(1)
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: return match.group(1)
        return text

    def analyze_input(self, user_data: dict, company_info: str) -> ExperienceAnalysis:
        self.log(f"🧪 {self.analysis_model} 모델로 정밀 진단 시작...")
        prompt = f"""
        [지원 기업 정보]
        {company_info}

        [자기소개서 문항]
        {user_data['question']}

        [지원자 자유 서술 경험]
        {user_data['experience']}

        [추가 답변]
        {user_data.get('feedback_answer', '없음')}
        
        당신은 **[{user_data['company']}]**의 채용을 담당하는 최고 수준의 실무 면접관이자 커리어 컨설턴트입니다.
        제공된 정보를 바탕으로 다음 프로세스에 따라 분석하고 반드시 JSON으로 응답하세요.

        Step 1: 문항 의도 및 기업 핏(Fit) 연결 분석
        - 문항의 요구 역량을 파악하고 기업의 인재상/핵심가치 중 가장 적합한 항목과 연결하세요.
        
        Step 2: 맞춤형 평가 기준 수립 (3가지 필수 체크리스트)
        1. 직무 관련 기술적 디테일(Action)이 구체적인가?
        2. 성과나 결과물(Result)이 객관적으로 증명되었는가?
        3. [핵심] 경험 전개 방식이 기업의 인재상/비전을 잘 드러내는가?

        Step 3: 내용 평가 및 꼬리 질문 생성
        - 사용자의 경험이 기준을 충족하는지 평가하고, 부족하다면 인터뷰하듯 친절하게 1~2개의 꼬리 질문을 던지세요.
        - 주의: 절대 부정적으로 평가하지 말고, "이 경험을 ~인재상과 연결하면 더 매력적일 것 같습니다. ~했던 사례를 더 들려주시겠어요?"와 같이 유도하세요.
        """
        
        instruction = "당신은 냉철하지만 따뜻한 커리어 컨설턴트(omg-analyst)입니다. 모든 응답은 한국어로, JSON 형식으로만 하세요."

        try:
            response = self.client.models.generate_content(
                model=self.analysis_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    response_schema=ExperienceAnalysis,
                    temperature=0.2,
                    max_output_tokens=2048,
                ),
            )
            raw_text = response.text
            clean_json = self._extract_json(raw_text)
            data = json.loads(clean_json)
            return ExperienceAnalysis.model_validate(data)
        except Exception as e:
            self.log(f"❌ 분석 오류: {str(e)}")
            raise e

    def generate_draft(self, user_data: dict, analysis: ExperienceAnalysis, company_info: str) -> str:
        self.log(f"✍️ 최종 초안 생성 시작...")
        prompt = f"""
        [기업/문항 정보]
        회사: {user_data['company']} / 직무: {user_data['role']}
        문항: {user_data['question']}

        [분석 결과]
        인재상 연결: {analysis.fit_analysis}
        추출 STAR: {analysis.extracted_star}
        포부 전략: {analysis.future_roadmap_plan}
        
        [지시 사항]
        1. **블라인드 채용 원칙 준수**: 이름, 학교명, 성별 등 인적 사항을 절대 기재하지 마세요.
        2. **분석 결과 반영**: 수립된 기업 핏과 기술적 디테일을 바탕으로 답변을 완성하세요.
        3. **수치 기반**: 성과는 반드시 객관적 지표(TPS, % 등)를 포함하세요.
        4. 한국어로 정중하고 전문적인 문체로 작성하세요.
        """
        instruction = "당신은 최고 수준의 엔지니어 전문 자소서 전문가입니다."
        response = self.client.models.generate_content(
            model=self.analysis_model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=instruction, temperature=0.7)
        )
        return response.text

# 3. GUI 통합 클래스
class CVAutoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CV-Auto: 실무 면접관 AI 컨설턴트")
        self.root.geometry("1100x950")
        self.env_path = ".env"
        self.log_file = "app_log.log"
        self.api_key = self.check_and_get_api_key()
        self.log_enabled = tk.BooleanVar(value=True)
        
        if self.api_key:
            self.processor = CVAIProcessor(self.api_key, log_func=self.write_log)
            self.setup_ui()
        else: self.root.destroy()

    def write_log(self, message: str):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{now}] {message}\n"
        try:
            with open(self.log_file, "a", encoding="utf-8") as f: f.write(log_entry)
        except: pass
        if self.log_enabled.get():
            try:
                self.log_text.insert(tk.END, log_entry)
                self.log_text.see(tk.END)
                self.root.update_idletasks()
            except: pass

    def check_and_get_api_key(self):
        load_dotenv(self.env_path)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            new_key = simpledialog.askstring("API 키 입력", "Gemini API Key를 입력해 주세요:", show='*')
            if new_key:
                with open(self.env_path, "w") as f: f.write(f"GEMINI_API_KEY={new_key}\n")
                load_dotenv(self.env_path)
                return new_key
            return None
        return api_key

    def setup_ui(self):
        top_bar = ttk.Frame(self.root, padding="10")
        top_bar.pack(fill=tk.X)
        ttk.Checkbutton(top_bar, text="⚙️ 화면 로그 표시", variable=self.log_enabled).pack(side=tk.LEFT)
        ttk.Button(top_bar, text="🧹 로그 지우기", command=lambda: self.log_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=10)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding="15")
        paned.add(left, weight=2)
        
        # 기본 정보
        ttk.Label(left, text="1. 지원 정보", font=("Helvetica", 11, "bold")).pack(anchor=tk.W)
        self.role_entry = self._create_field(left, "지원 직무", "백엔드 개발자")
        
        company_f = ttk.Frame(left)
        company_f.pack(fill=tk.X, pady=2)
        ttk.Label(company_f, text="지원 기업", width=12).pack(side=tk.LEFT)
        self.company_entry = ttk.Entry(company_f)
        self.company_entry.insert(0, "삼성전자")
        self.company_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(company_f, text=" 문항 번호", width=10).pack(side=tk.LEFT)
        self.q_num_entry = ttk.Entry(company_f, width=5)
        self.q_num_entry.insert(0, "1")
        self.q_num_entry.pack(side=tk.LEFT)

        # 문항 및 경험
        ttk.Label(left, text="2. 자기소개서 문항", font=("Helvetica", 11, "bold"), foreground="#e67e22").pack(anchor=tk.W, pady=(15, 0))
        self.question_text = scrolledtext.ScrolledText(left, height=3, font=("Malgun Gothic", 10), background="#fff5e6")
        self.question_text.pack(fill=tk.X, pady=5)

        ttk.Label(left, text="3. 나의 경험 (자유 서술)", font=("Helvetica", 11, "bold"), foreground="#2980b9").pack(anchor=tk.W, pady=(15, 0))
        self.exp_text = scrolledtext.ScrolledText(left, height=10, font=("Malgun Gothic", 10))
        self.exp_text.pack(fill=tk.X, pady=5)

        ttk.Label(left, text="💡 면접관 질문에 대한 보완 답변", font=("Helvetica", 11, "bold"), foreground="#007bff").pack(anchor=tk.W, pady=(15, 0))
        self.feedback_answer = scrolledtext.ScrolledText(left, height=4, font=("Malgun Gothic", 10), background="#fffdf0")
        self.feedback_answer.pack(fill=tk.X, pady=5)

        self.btn_analyze = ttk.Button(left, text="🚀 실무 면접관 정밀 분석 및 초안 생성", command=self.process_cv)
        self.btn_analyze.pack(pady=15)

        self.result_text = scrolledtext.ScrolledText(left, height=15, background="#f8f9fa", font=("Malgun Gothic", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True)

        right = ttk.Frame(paned, padding="5")
        paned.add(right, weight=1)
        self.log_text = scrolledtext.ScrolledText(right, background="#1e1e1e", foreground="#d4d4d4", font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _create_field(self, parent, label, default):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, pady=2)
        ttk.Label(f, text=label, width=12).pack(side=tk.LEFT)
        e = ttk.Entry(f)
        e.insert(0, default); e.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return e

    def process_cv(self):
        user_data = {
            "role": self.role_entry.get(),
            "company": self.company_entry.get(),
            "q_num": self.q_num_entry.get().strip(),
            "question": self.question_text.get("1.0", tk.END).strip(),
            "experience": self.exp_text.get("1.0", tk.END).strip(),
            "feedback_answer": self.feedback_answer.get("1.0", tk.END).strip()
        }
        if not user_data['experience'] or not user_data['question']:
            messagebox.showwarning("입력 부족", "문항과 경험을 모두 입력해 주세요."); return

        self.btn_analyze.config(state=tk.DISABLED)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, f"🕵️ [{user_data['company']}] 실무 면접관이 서류를 검토 중입니다...\n")
        threading.Thread(target=self._run_pipeline, args=(user_data,), daemon=True).start()

    def _run_pipeline(self, user_data: dict):
        try:
            info = self.processor.ensure_company_data(user_data['company'])
            analysis = self.processor.analyze_input(user_data, info)
            
            # 분석 결과 표시
            self.result_text.insert(tk.END, f"\n[Step 1: 기업 핏 분석]\n{analysis.fit_analysis}\n")
            self.result_text.insert(tk.END, f"\n[Step 2: 평가 체크리스트]\n" + "\n".join([f"- {c}" for c in analysis.evaluation_checklists]) + "\n")
            
            if not analysis.is_sufficient:
                self.result_text.insert(tk.END, f"\n[Step 3: 면접관의 추가 질문]\n🧐 {analysis.follow_up_question}\n")
                self.write_log("⚠️ 정보 보완 필요.")
            else:
                self.result_text.insert(tk.END, f"\n[Step 3: 합격 수준 도달] 초안을 작성합니다...\n")
                draft = self.processor.generate_draft(user_data, analysis, info)
                self.result_text.insert(tk.END, f"\n--- ✨ 최종 자기소개서 초안 ---\n\n{draft}")
                
                # 저장
                safe_company = self.processor.get_safe_filename(user_data['company'])
                safe_role = self.processor.get_safe_filename(user_data['role'])
                target_dir = os.path.join(self.processor.draft_dir, f"{safe_company}_{safe_role}")
                if not os.path.exists(target_dir): os.makedirs(target_dir)
                filename = f"{user_data['q_num']}_{self.processor.get_safe_filename(analysis.question_keyword)}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md"
                with open(os.path.join(target_dir, filename), "w", encoding="utf-8") as f: f.write(draft)
                messagebox.showinfo("성공", "초안 저장 완료!")
        except Exception as e:
            self.write_log(f"❌ 오류: {str(e)}"); messagebox.showerror("오류", str(e))
        finally:
            self.btn_analyze.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    CVAutoApp(root)
    root.mainloop()
