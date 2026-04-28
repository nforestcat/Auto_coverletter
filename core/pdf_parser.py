import pdfplumber

class PDFParser:
    @staticmethod
    def extract_text(file_path: str) -> str:
        """pdfplumber를 사용하여 PDF 파일에서 텍스트를 정밀하게 추출합니다."""
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            return f"PDF 추출 오류 (pdfplumber): {str(e)}"
