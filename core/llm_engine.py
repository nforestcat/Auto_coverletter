import json
import re
from typing import List
from pydantic import BaseModel, Field, ValidationError
from google.genai import types
from prompts.templates import (
    EXPERIENCE_ANALYSIS_PROMPT, 
    EXPERIENCE_ANALYSIS_INSTRUCTION,
    DRAFT_GEN_PROMPT,
    DRAFT_GEN_INSTRUCTION
)
from core.logger import get_logger

# 로거 설정
logger = get_logger("LLMEngine")

# AI 응답 구조 정의
class ExperienceAnalysis(BaseModel):
    is_sufficient: bool = Field(description="정보가 충분한지 여부")
    fit_analysis: str = Field(description="Step 1: 문항 의도 및 기업 핏(Fit) 연결 분석 결과")
    evaluation_checklists: List[str] = Field(description="Step 2: 수립된 3가지 맞춤형 평가 기준 리스트")
    follow_up_question: str = Field(description="Step 3: 내용 평가에 따른 면접관의 부드러운 꼬리 질문")
    extracted_star: str = Field(description="추출된 STAR 구조 데이터")
    future_roadmap_plan: str = Field(description="입사 후 포부 전략")
    question_keyword: str = Field(description="파일명용 짧은 한국어 키워드")

class LLMEngine:
    def __init__(self, client, model_name='gemma-4-31b-it'): # Gemini 모델 사용 권장 (예: gemini-1.5-flash)
        self.client = client
        self.model_name = model_name

    def _extract_json(self, text: str) -> str:
        """응답 텍스트에서 순수 JSON 부분만 안전하게 추출합니다."""
        text = text.replace("```json", "").replace("```", "").strip()
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: 
            return match.group(1)
        return text

    def analyze_experience(self, user_data: dict, company_info: str) -> ExperienceAnalysis:
        """실무 면접관 관점에서 경험을 정밀 분석합니다."""
        logger.info(f"📡 API 호출 시작 (모델: {self.model_name})")
        
        prompt = EXPERIENCE_ANALYSIS_PROMPT.format(
            company_name=user_data['company'],
            company_info=company_info,
            question=user_data['question'],
            experience=user_data['experience'],
            feedback_answer=user_data.get('feedback_answer', '없음')
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=EXPERIENCE_ANALYSIS_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ExperienceAnalysis,
                    temperature=0.2, # 온도는 낮게 유지하는 것이 좋습니다
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=2048, # 4096에서 조금 줄여서 빠른 실패 유도
                ),
            )
            
            # response.text가 비어있거나 None인 경우를 방어
            if not response or not response.text:
                raise ValueError("API 응답이 비어있습니다.")
                
            logger.info(f"📥 API 응답 수신 완료. (텍스트 길이: {len(response.text)}자)")
            
            clean_json = self._extract_json(response.text)
            
            if len(clean_json) > 100:
                logger.info(f"🔍 파싱된 JSON 요약: {clean_json[:100]}...")
            else:
                logger.info(f"🔍 파싱된 JSON: {clean_json}")
            
            # Pydantic 파싱 시도
            return ExperienceAnalysis.model_validate_json(clean_json)

        # 🚨 [핵심 개선] 파싱 실패 또는 API 에러 시 안전한 기본(Fallback) 객체 반환
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"❌ JSON 파싱 실패 또는 응답 끊김: {str(e)}")
            return self._get_fallback_analysis()
        except Exception as e:
            logger.error(f"❌ 치명적인 API 오류 발생: {str(e)}")
            return self._get_fallback_analysis()

    def _get_fallback_analysis(self) -> ExperienceAnalysis:
        """API 호출 실패 시 프로그램 다운을 막기 위한 기본 응답 객체입니다."""
        return ExperienceAnalysis(
            is_sufficient=False,
            fit_analysis="⚠️ AI가 분석 중 일시적인 혼란을 겪었습니다. (글자 수 한도 초과 또는 복잡도 문제)",
            evaluation_checklists=[
                "내용이 너무 길지 않은지 확인해 주세요.",
                "하나의 핵심 에피소드에 집중했는지 확인해 주세요.",
                "AI의 일시적 오류일 수 있으니 '다시 시도'를 눌러주세요."
            ],
            follow_up_question="작성해주신 내용이 훌륭하지만, 정보가 너무 방대하여 AI가 분석을 완료하지 못했습니다. 핵심 내용(문제 해결 과정 1가지)만 간추려서 다시 입력해 보시겠어요?",
            extracted_star="분석 보류",
            future_roadmap_plan="분석 보류",
            question_keyword="오류_재시도필요"
        )

    def generate_draft(self, user_data: dict, analysis: ExperienceAnalysis) -> str:
        """분석 결과를 바탕으로 최종 자기소개서 초안을 작성합니다."""
        prompt = DRAFT_GEN_PROMPT.format(
            company_name=user_data['company'],
            role=user_data['role'],
            question=user_data['question'],
            fit_analysis=analysis.fit_analysis,
            extracted_star=analysis.extracted_star,
            future_roadmap_plan=analysis.future_roadmap_plan
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=DRAFT_GEN_INSTRUCTION,
                temperature=0.7,
            ),
        )
        return response.text