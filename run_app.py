import streamlit.web.cli as stcli
import os, sys, threading, time, webview, signal, socket

# 시그널 핸들러 에러 방지를 위한 패치
def patch_signal():
    signal.signal = lambda *args, **kwargs: None

def resolve_path(path):
    """PyInstaller 환경에서도 경로를 올바르게 찾도록 도와줍니다."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, path)
    return os.path.join(os.path.abspath("."), path)

def get_free_port():
    """사용 가능한 빈 포트를 시스템에서 자동 할당받습니다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))  # 0을 지정하면 OS가 빈 포트를 자동 할당
        return s.getsockname()[1]

def run_streamlit(port):
    patch_signal() # 스레드 내부에서 시그널 함수를 가짜 함수로 대체
    app_path = resolve_path("app.py")
    # --server.headless=true 를 설정하여 브라우저가 별도로 뜨지 않게 합니다.
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        f"--server.port={port}",
        "--server.headless=true",
    ]
    stcli.main()

if __name__ == "__main__":
    # 1. 빈 포트 동적 할당
    port = get_free_port()
    print(f"[INFO] 빈 포트를 찾았습니다. Port: {port} 에서 Streamlit 서버를 시작합니다...")

    # 2. Streamlit을 백그라운드 스레드에서 실행
    t = threading.Thread(target=run_streamlit, args=(port,))
    t.daemon = True
    t.start()

    # 3. Streamlit 서버가 뜰 때까지 대기
    time.sleep(5)

    # 4. 전용 윈도우 창 생성
    webview.create_window("CV-Auto: 실무 면접관 AI 컨설턴트", f"http://localhost:{port}", width=1280, height=800)
    webview.start()
    
    # 창을 닫으면 프로세스 강제 종료
    os._exit(0)
