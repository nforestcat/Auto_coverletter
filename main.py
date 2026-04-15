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

# 1. AI 응답 구조 정의 (Pydantic)
class ExperienceAnalysis(BaseModel):
    is_sufficient: bool = Field(description="정보가 충분한지 여부")
    follow_up_question: str = Field(description="사용자에게 던질 통합 보완 질문. 부족한 요소들을 자연스럽게 질문 속에 녹여서 친절하게 작성하세요. (반드시 한국어로 작성)")
    extracted_star: str = Field(description="추출된 STAR 구조 데이터 (반드시 한국어로 작성)")
    future_roadmap_plan: str = Field(description="입사 후 포부 전략 (반드시 한국어로 작성)")

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
            if not os.path.exists(directory):
                os.makedirs(directory)

    def log(self, message: str):
        if self.log_func:
            self.log_func(message)

    def get_safe_filename(self, name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "_", name)

    def ensure_company_data(self, company_name: str) -> str:
        safe_name = self.get_safe_filename(company_name)
        file_path = os.path.join(self.company_dir, f"{safe_name}.md")

        if os.path.exists(file_path):
            self.log(f"📦 로컬 캐시 발견: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        self.log(f"🔍 로컬 캐시 없음. {self.research_model} 모델로 실시간 검색 시작...")
        prompt = f"'{company_name}'의 공식 홈페이지와 최신 뉴스를 검색하여 비전, 핵심 가치, 인재상, 최근 사업 전략 키워드를 Markdown 형식으로 상세히 정리해 주세요. 모든 내용은 반드시 한국어로 작성하세요."
        instruction = "당신은 전문 기업 분석가입니다. 반드시 Google Search 도구를 사용하여 최신 정보를 확인하고 모든 내용을 한국어로 작성해야 합니다."
        
        # 구글 검색 도구 활성화
        google_search_tool = types.Tool(google_search=types.GoogleSearch())

        response = self.client.models.generate_content(
            model=self.research_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                tools=[google_search_tool]  # 실시간 검색 도구 추가
            )
        )
        
        content = f"# [기업 정보] {company_name}\n\n" + response.text
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        self.log(f"✅ 기업 정보 저장 완료: {file_path}")
        return content

    def _extract_json(self, text: str) -> str:
        """텍스트에서 JSON 블록만 추출합니다."""
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return match.group(1)
            
        return text

    def analyze_input(self, user_data: dict, company_info: str) -> ExperienceAnalysis:
        self.log(f"🧪 {self.analysis_model} 모델로 경험 분석 시작...")
        prompt = f"""
        [지원 기업 정보]
        {company_info}

        [지원자 정보]
        직무: {user_data['role']}
        경험 원문: {user_data['experience']}
        성격/장단점: {user_data['traits']}
        추가 보완 답변: {user_data.get('feedback_answer', '없음')}
        
        [지시 사항 - 분석 기준]
        1. 기업의 비전과 인재상을 바탕으로 지원자의 경험이 충분한지 정밀하게 분석하세요.
        2. **엔지니어적 관점 검수**:
           - '획기적으로', '빠르게', '많이' 같은 추상적 표현이 있다면 반드시 구체적인 수치(TPS, 응답속도 ms 등)를 요구하세요.
           - 재시도(Retry) 로직 같은 핵심 기술 구현 시, 단순히 '구현했다'가 아니라 '어떤 알고리즘(예: 지수 백오프)이나 라이브러리를 썼는지' 힌트를 요구하세요.
        3. 부족한 점을 사용자가 답변하기 쉬운 구체적이고 친절한 가이드형 질문으로 통합하여 `follow_up_question` 필드에 담으세요.
        4. 모든 응답은 반드시 한국어로만 작성하세요.
        """
        
        instruction = "당신은 냉철하지만 친절한 커리어 컨설턴트(omg-analyst)입니다. 반드시 JSON 형식으로만 응답하세요."

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
            
            try:
                data = json.loads(clean_json)
                self.log(f"✅ 분석 완료. 충분성 여부: {data.get('is_sufficient')}")
                return ExperienceAnalysis.model_validate(data)
            except json.JSONDecodeError as je:
                self.log(f"❌ JSON 파싱 실패. 원문: {raw_text}")
                raise ValueError(f"AI 응답이 올바른 JSON 형식이 아닙니다: {str(je)}")
                
        except Exception as e:
            self.log(f"❌ 분석 도중 오류 발생: {str(e)}")
            raise e

    def generate_draft(self, user_data: dict, analysis: ExperienceAnalysis, company_info: str) -> str:
        self.log(f"✍️ 최종 초안 생성 시작 ({self.analysis_model})...")
        prompt = f"""
        [기업 정보]
        {company_info}
        [최종 분석 데이터]
        {analysis.extracted_star}
        포부 전략: {analysis.future_roadmap_plan}
        기업/직무: {user_data['company']} / {user_data['role']}
        
        [지시 사항 - 작성 가이드]
        1. 소제목, STAR 본문, 입사 후 포부(3단계) 구조로 작성하세요.
        2. **엔지니어적 전문성 강화**:
           - 추상적인 성과(획기적 등)는 반드시 수치(Data)와 지표(TPS, ms 등)를 포함하여 기술하세요.
           - 기술적 디테일(예: 지수 백오프 기반 Retry 로직, 가용성 99.99% 보장 HA 아키텍처 등)을 문맥에 녹여내세요.
           - '제로 다운타임'과 같은 표현보다는 현실적이고 전문적인 '고가용성(High Availability)' 용어를 우선 사용하세요.
        3. 모든 내용은 한국어로만 작성하세요.
        """
        instruction = "당신은 최고 수준의 엔지니어 전문 자소서 전문가입니다. 기술적 깊이와 비즈니스 성과를 동시에 보여주세요."

        response = self.client.models.generate_content(
            model=self.analysis_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.7,
            ),
        )
        self.log(f"✅ 초안 생성 완료.")
        return response.text

# 3. GUI 통합 클래스
class CVAutoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CV-Auto: 맞춤형 AI 자소서 컨설턴트")
        self.root.geometry("1000x950")
        
        self.env_path = ".env"
        self.log_file = "app_log.log"
        self.api_key = self.check_and_get_api_key()
        
        self.log_enabled = tk.BooleanVar(value=True)
        
        if self.api_key:
            self.processor = CVAIProcessor(self.api_key, log_func=self.write_log)
            self.setup_ui()
            self.write_log("--- 🏁 프로그램 초기화 완료 ---")
        else:
            self.root.destroy()

    def write_log(self, message: str):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{now}] {message}\n"
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except:
            pass
            
        if self.log_enabled.get():
            try:
                self.log_text.insert(tk.END, log_entry)
                self.log_text.see(tk.END)
                self.root.update_idletasks()
            except:
                pass

    def check_and_get_api_key(self):
        load_dotenv(self.env_path)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            new_key = simpledialog.askstring("API 키 입력", "Gemini API Key를 입력해 주세요:", show='*')
            if new_key:
                with open(self.env_path, "w") as f:
                    f.write(f"GEMINI_API_KEY={new_key}\n")
                load_dotenv(self.env_path)
                return new_key
            return None
        return api_key

    def setup_ui(self):
        top_bar = ttk.Frame(self.root, padding="10")
        top_bar.pack(fill=tk.X)
        ttk.Checkbutton(top_bar, text="⚙️ 화면 로그 표시", variable=self.log_enabled).pack(side=tk.LEFT)
        ttk.Button(top_bar, text="🧹 화면 로그 지우기", command=lambda: self.log_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=10)
        ttk.Label(top_bar, text=f"📂 로그 파일: {os.path.abspath(self.log_file)}", foreground="gray").pack(side=tk.RIGHT)

        paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        left_container = ttk.Frame(paned_window)
        paned_window.add(left_container, weight=2)
        
        canvas = tk.Canvas(left_container)
        scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=canvas.yview)
        self.main_frame = ttk.Frame(canvas, padding="20")
        self.main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(self.main_frame, text="1. 기본 정보 및 기업", font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        self.name_entry = self._create_field("이름", "홍길동")
        self.role_entry = self._create_field("지원 직무", "백엔드 개발자")
        self.company_entry = self._create_field("지원 기업", "삼성전자")

        ttk.Label(self.main_frame, text="2. 나의 경험 (자유 서술)", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(15, 0))
        self.exp_text = scrolledtext.ScrolledText(self.main_frame, height=8, font=("Malgun Gothic", 10))
        self.exp_text.pack(fill=tk.X, pady=5)

        ttk.Label(self.main_frame, text="3. 성격 및 장단점", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(15, 0))
        self.traits_text = scrolledtext.ScrolledText(self.main_frame, height=5, font=("Malgun Gothic", 10))
        self.traits_text.pack(fill=tk.X, pady=5)

        ttk.Label(self.main_frame, text="💡 AI 질문에 대한 보완 답변", font=("Helvetica", 12, "bold"), foreground="#007bff").pack(anchor=tk.W, pady=(15, 0))
        self.feedback_answer = scrolledtext.ScrolledText(self.main_frame, height=5, font=("Malgun Gothic", 10), background="#fffdf0")
        self.feedback_answer.pack(fill=tk.X, pady=5)

        self.btn_analyze = ttk.Button(self.main_frame, text="🚀 분석 및 초안 생성 (데이터 업데이트)", command=self.process_cv)
        self.btn_analyze.pack(pady=20)

        ttk.Label(self.main_frame, text="4. AI 가이드 및 분석 결과", font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        self.result_text = scrolledtext.ScrolledText(self.main_frame, height=15, background="#f8f9fa", font=("Malgun Gothic", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True, pady=5)

        right_container = ttk.Frame(paned_window)
        paned_window.add(right_container, weight=1)
        ttk.Label(right_container, text="📜 실시간 로그", font=("Helvetica", 10, "bold")).pack(anchor=tk.W, padx=5, pady=5)
        self.log_text = scrolledtext.ScrolledText(right_container, background="#1e1e1e", foreground="#d4d4d4", font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _create_field(self, label, default):
        frame = ttk.Frame(self.main_frame)
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text=label, width=12).pack(side=tk.LEFT)
        entry = ttk.Entry(frame)
        entry.insert(0, default)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return entry

    def process_cv(self):
        """버튼 클릭 시 호출: 쓰레드를 생성하여 분석 프로세스 시작"""
        user_data = {
            "name": self.name_entry.get(),
            "role": self.role_entry.get(),
            "company": self.company_entry.get(),
            "experience": self.exp_text.get("1.0", tk.END).strip(),
            "traits": self.traits_text.get("1.0", tk.END).strip(),
            "feedback_answer": self.feedback_answer.get("1.0", tk.END).strip()
        }

        if not user_data['experience'] or not user_data['traits']:
            messagebox.showwarning("입력 부족", "경험과 성격 정보를 모두 입력해 주세요.")
            return

        self.btn_analyze.config(state=tk.DISABLED)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, f"💎 {user_data['company']} 정보를 분석 중입니다 (UI는 멈추지 않습니다)...\n")
        self.write_log(f"--- 🚀 프로세스 시작: {user_data['company']} / {user_data['role']} ---")
        
        threading.Thread(target=self._run_analysis_pipeline, args=(user_data,), daemon=True).start()

    def _run_analysis_pipeline(self, user_data: dict):
        """백그라운드 쓰레드에서 실행되는 실제 AI 로직"""
        try:
            company_info = self.processor.ensure_company_data(user_data['company'])
            analysis = self.processor.analyze_input(user_data, company_info)
            
            if not analysis.is_sufficient:
                self.result_text.insert(tk.END, f"\n[!] 추가 정보 보완 가이드\n\n🧐 질문: {analysis.follow_up_question}\n")
                self.result_text.insert(tk.END, f"\n\n👉 위 '보완 답변' 칸에 내용을 적고 다시 버튼을 눌러주세요!")
                self.write_log("⚠️ 정보 부족으로 보완 질문 생성됨.")
            else:
                self.result_text.insert(tk.END, f"\n[✔] 분석 완료! 기업 맞춤형 자소서를 작성합니다...\n")
                
                draft_content = self.processor.generate_draft(user_data, analysis, company_info)
                self.result_text.insert(tk.END, f"\n--- ✨ 생성된 자기소개서 초안 ---\n\n{draft_content}")
                
                safe_company = self.processor.get_safe_filename(user_data['company'])
                draft_path = os.path.join(self.processor.draft_dir, f"{safe_company}_draft.md")
                with open(draft_path, "w", encoding="utf-8") as f:
                    f.write(draft_content)
                self.write_log(f"💾 초안 파일 저장 완료: {draft_path}")
                messagebox.showinfo("성공", f"자기소개서 초안이 '{draft_path}'로 저장되었습니다.")

        except Exception as e:
            error_msg = f"에러 발생: {str(e)}"
            tb = traceback.format_exc()
            self.write_log(f"❌ {error_msg}")
            self.write_log(f"📝 상세 스택트레이스:\n{tb}")
            messagebox.showerror("오류", error_msg)
        
        finally:
            self.btn_analyze.config(state=tk.NORMAL)
            self.write_log("--- 🏁 프로세스 종료 ---")

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = CVAutoApp(root)
    root.mainloop()
