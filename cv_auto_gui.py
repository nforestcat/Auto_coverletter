import tkinter as tk
from tkinter import ttk, messagebox
import os

class CVAutoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CV-Auto: 맞춤형 자기소개서 컨설팅 데이터 입력")
        self.root.geometry("600x900")

        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. 기본 정보 섹션
        ttk.Label(self.main_frame, text="1. 기본 정보", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        self.name_var = self._create_label_entry("이름", "홍길동")
        self.role_var = self._create_label_entry("지원 직무", "백엔드 개발자")
        self.edu_var = self._create_label_entry("학력/전공", "컴퓨터공학 학사")
        self.cert_var = self._create_label_entry("자격증 (쉼표로 구분)", "정보처리기사, SQLD")

        # 2. 기업 정보 섹션
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        ttk.Label(self.main_frame, text="2. 지원 기업", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        self.company_var = self._create_label_entry("기업명", "삼성전자")

        # 3. 자유 경험 서술 섹션
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        ttk.Label(self.main_frame, text="3. 나의 핵심 경험 (자유 서술)", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.exp_text = tk.Text(self.main_frame, height=10, width=70, undo=True)
        self.exp_text.pack(fill=tk.X, pady=(0, 10))

        # 4. 성격 및 장단점 서술 섹션 (추가됨)
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        ttk.Label(self.main_frame, text="4. 나의 성격 및 장단점 (자유 서술)", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(self.main_frame, text="본인의 성격적 특징, 생활 신조, 장점과 단점을 자유롭게 적어주세요.", 
                  foreground="gray", font=("Helvetica", 9)).pack(anchor=tk.W, pady=(0, 5))
        self.traits_text = tk.Text(self.main_frame, height=8, width=70, undo=True)
        self.traits_text.pack(fill=tk.X, pady=(0, 10))

        # 저장 버튼
        ttk.Button(self.main_frame, text="데이터 저장 및 분석 시작", command=self.save_data).pack(pady=20)

    def _create_label_entry(self, label_text, placeholder):
        frame = ttk.Frame(self.main_frame)
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text=f"{label_text}:", width=15).pack(side=tk.LEFT)
        var = tk.StringVar(value=placeholder)
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return var

    def save_data(self):
        name = self.name_var.get()
        role = self.role_var.get()
        edu = self.edu_var.get()
        cert = self.cert_var.get()
        company = self.company_var.get()
        experience_raw = self.exp_text.get("1.0", tk.END).strip()
        traits_raw = self.traits_text.get("1.0", tk.END).strip()

        if not experience_raw or not traits_raw:
            messagebox.showwarning("입력 부족", "경험 내용과 성격 정보를 모두 입력해 주세요.")
            return

        # 1. 개인 정보 저장 (user_profile.md)
        user_content = f"""# [개인 정보] {name}
## 지원 직무
- {role}

## 주요 스펙
- 학력/전공: {edu}
- 자격증: {cert}

## 핵심 경험 (원문)
{experience_raw}

## 성격 및 장단점 (원문)
{traits_raw}

---
## [분석 결과]
(omg-analyst가 분석 중...)
"""
        with open("user_profile.md", "w", encoding="utf-8") as f:
            f.write(user_content)

        # 2. 기업 정보 저장 (company_info.md)
        company_content = f"""# [기업 정보] {company}
## 상태: 분석 대기 중...
"""
        with open("company_info.md", "w", encoding="utf-8") as f:
            f.write(company_content)
        
        messagebox.showinfo("완료", "모든 데이터가 저장되었습니다.\n전문 분석가(omg-analyst)가 성격과 경험을 매칭합니다.")
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CVAutoGUI(root)
    root.mainloop()
