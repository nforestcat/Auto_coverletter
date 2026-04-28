import json
import re
from google.genai import types
from prompts.templates import COMPANY_SEARCH_PROMPT, COMPANY_SEARCH_INSTRUCTION

class SearchUtils:
    def __init__(self, client, model_name='gemma-4-26b-a4b-it'):
        self.client = client
        self.model_name = model_name

    def _extract_json(self, text: str) -> str:
        """응답 텍스트에서 순수 JSON 부분만 안전하게 추출합니다."""
        text = text.replace("```json", "").replace("```", "").strip()
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: 
            return match.group(1)
        return text

    def search_company_info(self, company_name: str) -> dict:
        """실시간 구글 검색을 통해 기업 정보를 수집하여 JSON 객체로 반환합니다."""
        prompt = COMPANY_SEARCH_PROMPT.format(company_name=company_name)
        
        google_search_tool = types.Tool(google_search=types.GoogleSearch())

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=COMPANY_SEARCH_INSTRUCTION,
                tools=[google_search_tool],
                response_mime_type="application/json"
            )
        )
        
        try:
            clean_json = self._extract_json(response.text)
            company_data = json.loads(clean_json)
            # 수동으로 필드 보강 (프롬프트에서 생성하지만 명시적 보장)
            if "last_updated" not in company_data or company_data["last_updated"] == "YYYY-MM-DD":
                import datetime
                company_data["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d")
            return company_data
        except Exception as e:
            # 파싱 실패 시 최소한의 구조 반환
            import datetime
            return {
                "company_name": company_name,
                "vision_mission": "정보를 불러오는 중 오류가 발생했습니다.",
                "core_values": [],
                "ideal_candidate": [],
                "business_strategy": [],
                "tech_roadmap": [],
                "last_updated": datetime.datetime.now().strftime("%Y-%m-%d"),
                "raw_text": response.text
            }
