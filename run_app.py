import streamlit.web.cli as stcli
import os, sys, threading, time, webview, signal, socket
import urllib.request

def patch_signal():
    """시그널 핸들러 에러 방지를 위한 패치"""
    signal.signal = lambda *args, **kwargs: None

def resolve_path(path):
    """PyInstaller 환경에서도 경로를 올바르게 찾도록 도와줍니다."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, path)
    return os.path.join(os.path.abspath("."), path)

def get_free_port(start_port=8501, max_port=8599):
    """127.0.0.1(로컬) 전용으로 빈 포트를 찾습니다. (방화벽 경고 방지)"""
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # '' 대신 '127.0.0.1'을 사용하여 외부 접근을 막고 방화벽 충돌을 피합니다.
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    
    # 지정 범위를 모두 실패하면 OS 자동 할당으로 최후 시도
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def run_streamlit(port):
    patch_signal() 
    app_path = resolve_path("app.py")
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        f"--server.port={port}",
        "--server.address=127.0.0.1",  # 방화벽 충돌을 막기 위해 필수 추가!
        "--server.headless=true",
    ]
    stcli.main()

def wait_for_server(port, timeout=30):
    """Streamlit 서버가 완전히 뜰 때까지 기다립니다 (최대 30초)."""
    start_time = time.time()
    url = f"http://127.0.0.1:{port}"
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen(url)
            return True # 서버가 응답하면 즉시 통과
        except:
            time.sleep(0.5) # 0.5초 대기 후 다시 시도
    return False

if __name__ == "__main__":
    # 1. 안전한 로컬 빈 포트 할당
    port = get_free_port()
    print(f"[INFO] 127.0.0.1:{port} 에서 Streamlit 서버를 준비합니다...")

    # 2. Streamlit을 백그라운드 스레드에서 실행
    t = threading.Thread(target=run_streamlit, args=(port,))
    t.daemon = True
    t.start()

    # 3. Streamlit 서버가 응답할 때까지 스마트하게 대기 (기존 time.sleep(5) 대체)
    if wait_for_server(port):
        print("[INFO] 서버 시작 완료! 윈도우 창을 띄웁니다.")
        # 4. 전용 윈도우 창 생성
        webview.create_window("CV-Auto: 실무 면접관 AI 컨설턴트", f"http://127.0.0.1:{port}", width=1280, height=800)
        webview.start()
    else:
        print("[ERROR] Streamlit 서버를 띄우는 데 실패했거나 응답 시간이 초과되었습니다.")
    
    # 창을 닫으면 프로세스 강제 종료
    os._exit(0)