import os
import sys
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

def get_safe_filename(name: str) -> str:
    """파일명으로 사용할 수 없는 특수문자를 제거하거나 대체합니다."""
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def research_company(company_name: str):
    """
    특정 기업의 정보를 검색하여 company/{기업명}.md에 저장합니다.
    이미 존재하면 검색을 건너뛰고 로컬 데이터를 사용합니다.
    """
    # 1. 폴더 및 파일 경로 설정
    company_dir = "company"
    if not os.path.exists(company_dir):
        os.makedirs(company_dir)
    
    safe_name = get_safe_filename(company_name)
    file_path = os.path.join(company_dir, f"{safe_name}.md")

    # 2. 로컬 데이터 체크 (캐싱)
    if os.path.exists(file_path):
        print(f"📦 '{company_name}'의 정보가 이미 로컬에 존재합니다: {file_path}")
        print("로컬 데이터를 사용하여 분석을 진행합니다.")
        return file_path

    # 3. API 키 로드 및 검색 진행
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
        return None

    client = genai.Client(api_key=api_key)
    model_id = 'gemini-3.1-flash-lite-preview'

    print(f"🔍 '{company_name}'에 대한 정보를 새로 검색하고 분석 중입니다...")

    prompt = f"""
    '{company_name}'의 최신 기업 정보를 검색하여 다음 항목을 한국어로 상세히 정리해 주세요.
    
    1. 비전 및 미션 (Vision & Mission)
    2. 핵심 가치 (Core Values)
    3. 인재상 (Ideal Talent)
    4. 최근 주요 키워드 및 뉴스 (Main Keywords)
    
    결과는 반드시 Markdown 형식으로 작성해 주세요.
    """

    instruction = f"당신은 전문 기업 분석가입니다. '{company_name}'의 공식 홈페이지와 신뢰할 수 있는 뉴스 자료를 바탕으로 가장 정확하고 최신 정보를 제공합니다."

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.2,
            ),
        )
        
        # 4. 개별 마크다운 파일 저장
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# [기업 정보] {company_name}\n\n")
            f.write(response.text)
        
        print(f"✅ 분석 완료! 결과가 '{file_path}'에 저장되었습니다.")
        return file_path

    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        company = input("분석할 기업명을 입력하세요: ")
    else:
        company = sys.argv[1]
    
    research_company(company)
