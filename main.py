import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import json
import os
import re
from typing import List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv, set_key

# 1. AI 응답 구조 정의 (Pydantic)
class ExperienceAnalysis(BaseModel):
    is_sufficient: bool
    missing_elements: List[str]
    follow_up_question: str
    extracted_star: str
    future_roadmap_plan: str

# 2. AI 파이프라인 클래스
class CVAIProcessor:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.research_model = 'gemini-3.1-flash-lite-preview'
        self.analysis_model = 'gemma-4-31b-it'
        self.company_dir = "company"
        
        if not os.path.exists(self.company_dir):
            os.makedirs(self.company_dir)

    def get_safe_filename(self, name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "_", name)

    def ensure_company_data(self, company_name: str) -> str:
        """기업 정보가 로컬에 있는지 확인하고, 없으면 연구를 수행합니다."""
        safe_name = self.get_safe_filename(company_name)
        file_path = os.path.join(self.company_dir, f"{safe_name}.md")

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        # 정보가 없는 경우 연구 수행 (gemini-3.1-flash-lite-preview)
        prompt = f"'{company_name}'의 비전, 핵심 가치, 인재상, 최신 키워드를 검색하여 Markdown 형식으로 정리해 주세요."
        instruction = "전문 기업 분석가로서 최신 정보를 정확히 제공합니다."
        
        response = self.client.models.generate_content(
            model=self.research_model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=instruction)
        )
        
        content = f"# [기업 정보] {company_name}\n\n" + response.text
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return content

    def analyze_input(self, user_data: dict, company_info: str) -> ExperienceAnalysis:
        """Gemma 4 모델을 사용하여 기업 정보와 사용자의 경험을 정밀 분석합니다."""
        prompt = f"""
        [지원 기업 정보]
        {company_info}

        [지원자 정보]
        직무: {user_data['role']}
        경험 원문: {user_data['experience']}
        성격/장단점: {user_data['traits']}
        
        위 기업의 비전과 인재상을 바탕으로 지원자의 경험이 충분한지 분석하세요.
        특히 '입사 후 포부'를 위한 3단계 로드맵(적응-문제해결-비전)이 나올 수 있는지 확인하세요.
        """
        
        instruction = "당신은 냉철한 커리어 분석가(omg-analyst)입니다. 기업 정보와 지원자 경험의 정합성을 정밀 분석합니다."

        response = self.client.models.generate_content(
            model=self.analysis_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                response_schema=ExperienceAnalysis,
                temperature=0.2,
            ),
        )
        return ExperienceAnalysis.model_validate_json(response.text)

    def generate_draft(self, user_data: dict, analysis: ExperienceAnalysis, company_info: str) -> str:
        """Gemma 4 모델을 사용하여 최종 자소서 초안을 생성합니다."""
        prompt = f"""
        [기업 정보]
        {company_info}

        [분석 데이터]
        {analysis.extracted_star}
        포부 전략: {analysis.future_roadmap_plan}
        기업/직무: {user_data['company']} / {user_data['role']}
        
        다음 구조로 작성하세요:
        1. 주제 (소제목)
        2. STAR 본문 (기업의 인재상에 맞춘 키워드 강조)
        3. 입사 후 포부 (기업 비전과 연결된 3단계 로드맵)
        """
        instruction = "당신은 최고 수준의 자소서 전문가입니다. 사용자의 경험과 기업의 가치를 완벽하게 매칭합니다."

        response = self.client.models.generate_content(
            model=self.analysis_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.7,
            ),
        )
        return response.text

# 3. GUI 통합 클래스
class CVAutoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CV-Auto: 맞춤형 AI 자소서 컨설턴트")
        self.root.geometry("700x900")
        
        self.env_path = ".env"
        self.api_key = self.check_and_get_api_key()
        
        if self.api_key:
            self.processor = CVAIProcessor(self.api_key)
            self.setup_ui()
        else:
            self.root.destroy()

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
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.main_frame, text="1. 기본 정보 및 기업", font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        self.name_entry = self._create_field("이름", "홍길동")
        self.role_entry = self._create_field("지원 직무", "백엔드 개발자")
        self.company_entry = self._create_field("지원 기업", "삼성전자")

        ttk.Label(self.main_frame, text="2. 나의 경험 (자유 서술)", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(15, 0))
        self.exp_text = scrolledtext.ScrolledText(self.main_frame, height=10, font=("Malgun Gothic", 10))
        self.exp_text.pack(fill=tk.X, pady=5)

        ttk.Label(self.main_frame, text="3. 성격 및 장단점", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(15, 0))
        self.traits_text = scrolledtext.ScrolledText(self.main_frame, height=6, font=("Malgun Gothic", 10))
        self.traits_text.pack(fill=tk.X, pady=5)

        self.btn_analyze = ttk.Button(self.main_frame, text="🚀 AI 분석 및 초안 생성", command=self.process_cv)
        self.btn_analyze.pack(pady=25)

        ttk.Label(self.main_frame, text="4. AI 피드백 및 결과", font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        self.result_text = scrolledtext.ScrolledText(self.main_frame, height=12, background="#f8f9fa", font=("Malgun Gothic", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def _create_field(self, label, default):
        frame = ttk.Frame(self.main_frame)
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text=label, width=12).pack(side=tk.LEFT)
        entry = ttk.Entry(frame)
        entry.insert(0, default)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return entry

    def process_cv(self):
        user_data = {
            "name": self.name_entry.get(),
            "role": self.role_entry.get(),
            "company": self.company_entry.get(),
            "experience": self.exp_text.get("1.0", tk.END).strip(),
            "traits": self.traits_text.get("1.0", tk.END).strip()
        }

        if not user_data['experience'] or not user_data['traits']:
            messagebox.showwarning("입력 부족", "경험과 성격 정보를 모두 입력해 주세요.")
            return

        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, f"💎 {user_data['company']} 정보를 분석 중입니다...\n")
        self.root.update()

        try:
            # 1. 기업 정보 확보 (캐시 확인 또는 연구 수행)
            company_info = self.processor.ensure_company_data(user_data['company'])
            
            # 2. Gemma 4를 통한 정밀 분석
            analysis = self.processor.analyze_input(user_data, company_info)
            
            if not analysis.is_sufficient:
                self.result_text.insert(tk.END, f"\n[!] 추가 정보가 필요합니다.\n\n🧐 질문: {analysis.follow_up_question}\n")
                self.result_text.insert(tk.END, f"\n부족한 요소: {', '.join(analysis.missing_elements)}")
            else:
                self.result_text.insert(tk.END, f"\n[✔] 분석 완료! 기업 맞춤형 자소서를 작성합니다...\n")
                self.root.update()
                
                # 3. 최종 초안 생성
                draft = self.processor.generate_draft(user_data, analysis, company_info)
                self.result_text.insert(tk.END, f"\n--- ✨ 생성된 자기소개서 초안 ---\n\n{draft}")
                
                with open("draft.md", "w", encoding="utf-8") as f:
                    f.write(draft)
                messagebox.showinfo("성공", "자기소개서 초안이 draft.md로 저장되었습니다.")

        except Exception as e:
            messagebox.showerror("오류", f"처리 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = CVAutoApp(root)
    root.mainloop()
