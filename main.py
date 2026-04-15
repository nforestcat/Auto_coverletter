import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import json
import os
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
        self.model_id = 'gemma-4-31b-it'

    def analyze_input(self, user_data: dict) -> ExperienceAnalysis:
        prompt = f"""
        지원 직무: {user_data['role']}
        지원 기업: {user_data['company']}
        경험 원문: {user_data['experience']}
        성격/장단점: {user_data['traits']}
        
        대기업 자소서 작성을 위한 정보의 충분성을 분석하세요.
        특히 '입사 후 포부'를 위한 3단계 로드맵(적응-문제해결-비전)이 나올 수 있는지 확인하세요.
        """
        
        instruction = "당신은 냉철한 커리어 분석가입니다. 정보를 정밀 분석하고 부족한 부분을 찾아냅니다."

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                response_schema=ExperienceAnalysis,
                temperature=0.2,
            ),
        )
        return ExperienceAnalysis.model_validate_json(response.text)

    def generate_draft(self, user_data: dict, analysis: ExperienceAnalysis) -> str:
        prompt = f"""
        분석 데이터: {analysis.extracted_star}
        포부 전략: {analysis.future_roadmap_plan}
        기업/직무: {user_data['company']} / {user_data['role']}
        
        다음 구조로 작성하세요:
        1. 주제 (소제목)
        2. STAR 본문
        3. 입사 후 포부 (3단계 시간대별 로드맵)
        """
        instruction = "당신은 최고 수준의 자소서 전문가입니다. 사용자의 경험과 기업의 가치를 완벽하게 매칭합니다."

        response = self.client.models.generate_content(
            model=self.model_id,
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
        """ .env에서 키를 찾고 없으면 입력을 요청합니다. """
        load_dotenv(self.env_path)
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            # 키 입력 팝업창
            new_key = simpledialog.askstring("API 키 입력", 
                "Gemini API Key가 발견되지 않았습니다.\nGoogle AI Studio에서 발급받은 키를 입력해 주세요:",
                show='*')
            
            if new_key:
                # .env 파일 생성 및 저장
                with open(self.env_path, "w") as f:
                    f.write(f"GEMINI_API_KEY={new_key}\n")
                load_dotenv(self.env_path)
                return new_key
            else:
                return None
        return api_key

    def setup_ui(self):
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # UI 요소 (기존과 동일하되 디자인 소폭 개선)
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
        self.result_text.insert(tk.END, "💎 AI 분석가가 당신의 커리어를 검토 중입니다...\n")
        self.root.update()

        try:
            analysis = self.processor.analyze_input(user_data)
            
            if not analysis.is_sufficient:
                self.result_text.insert(tk.END, f"\n[!] 추가 정보가 필요합니다.\n\n🧐 질문: {analysis.follow_up_question}\n")
                self.result_text.insert(tk.END, f"\n부족한 요소: {', '.join(analysis.missing_elements)}")
            else:
                self.result_text.insert(tk.END, f"\n[✔] 분석 완료! {user_data['company']} 최적화 자소서를 작성합니다...\n")
                self.root.update()
                
                draft = self.processor.generate_draft(user_data, analysis)
                self.result_text.insert(tk.END, f"\n--- ✨ 생성된 자기소개서 초안 ---\n\n{draft}")
                
                with open("draft.md", "w", encoding="utf-8") as f:
                    f.write(draft)
                messagebox.showinfo("성공", "자기소개서 초안이 draft.md로 저장되었습니다.")

        except Exception as e:
            messagebox.showerror("오류", f"처리 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    # 폰트 깨짐 방지 (Windows용 가독성 개선)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = CVAutoApp(root)
    root.mainloop()
