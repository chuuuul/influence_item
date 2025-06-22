#!/usr/bin/env python3
"""
연예인 추천 아이템 자동화 시스템 - 대시보드 런처
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """대시보드 실행"""
    # 프로젝트 루트 디렉토리
    project_root = Path(__file__).parent
    dashboard_path = project_root / "dashboard" / "main_dashboard.py"
    
    print("🎬 연예인 추천 아이템 관리 대시보드를 시작합니다...")
    print(f"📂 대시보드 경로: {dashboard_path}")
    print("🌐 브라우저에서 http://localhost:8501 에 접속하세요.")
    print("🛑 종료하려면 Ctrl+C를 누르세요.")
    print("-" * 50)
    
    try:
        # Streamlit 앱 실행
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(dashboard_path),
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 대시보드를 종료합니다.")
    except subprocess.CalledProcessError as e:
        print(f"❌ 대시보드 실행 중 오류가 발생했습니다: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Streamlit이 설치되지 않았습니다.")
        print("📦 설치 명령: pip install streamlit")
        sys.exit(1)

if __name__ == "__main__":
    main()