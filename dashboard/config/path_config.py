"""
중앙화된 경로 관리 시스템
PRD v1.0 기반 프로젝트 구조 표준화

이 모듈은 프로젝트 전체에서 사용되는 모든 경로를 중앙화하여 관리합니다.
DRY 원칙을 준수하고 확장성을 보장합니다.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional
import logging

class PathManager:
    """프로젝트 경로 관리자"""
    
    def __init__(self):
        # 현재 파일 기준으로 프로젝트 루트 설정
        self._current_file = Path(__file__).absolute()
        self._config_dir = self._current_file.parent  # config 폴더
        self._dashboard_root = self._config_dir.parent  # dashboard 폴더
        self._project_root = self._dashboard_root.parent  # influence_item 폴더
        
        # Python path 설정
        self._setup_python_path()
        
        # 로깅 설정
        self._setup_logging()
        
        # 경로 검증
        self._validate_paths()
    
    def _setup_python_path(self):
        """Python 경로 설정"""
        paths_to_add = [
            str(self._project_root),
            str(self._dashboard_root),
            str(self._config_dir)
        ]
        
        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)
    
    def _setup_logging(self):
        """로깅 설정"""
        log_dir = self._dashboard_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "path_manager.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _validate_paths(self):
        """중요 경로 존재 확인"""
        critical_paths = [
            self._project_root,
            self._dashboard_root,
            self._config_dir
        ]
        
        for path in critical_paths:
            if not path.exists():
                raise FileNotFoundError(f"Critical path does not exist: {path}")
        
        self.logger.info("모든 중요 경로가 확인되었습니다.")
    
    # === 기본 디렉토리 경로 ===
    @property
    def project_root(self) -> Path:
        """프로젝트 루트 디렉토리"""
        return self._project_root
    
    @property
    def dashboard_root(self) -> Path:
        """대시보드 루트 디렉토리"""
        return self._dashboard_root
    
    @property
    def config_dir(self) -> Path:
        """설정 파일 디렉토리"""
        return self._config_dir
    
    @property
    def components_dir(self) -> Path:
        """컴포넌트 디렉토리"""
        return self._dashboard_root / "components"
    
    @property
    def views_dir(self) -> Path:
        """뷰 디렉토리"""
        return self._dashboard_root / "views"
    
    @property
    def utils_dir(self) -> Path:
        """유틸리티 디렉토리"""
        return self._dashboard_root / "utils"
    
    @property
    def static_dir(self) -> Path:
        """정적 파일 디렉토리"""
        return self._dashboard_root / "static"
    
    @property
    def screenshot_dir(self) -> Path:
        """스크린샷 디렉토리"""
        screenshot_path = self._dashboard_root / "screenshot"
        screenshot_path.mkdir(exist_ok=True)
        return screenshot_path
    
    @property
    def logs_dir(self) -> Path:
        """로그 디렉토리"""
        logs_path = self._dashboard_root / "logs"
        logs_path.mkdir(exist_ok=True)
        return logs_path
    
    # === 데이터베이스 및 데이터 파일 ===
    @property
    def database_file(self) -> Path:
        """SQLite 데이터베이스 파일"""
        return self._dashboard_root / "influence_item.db"
    
    @property
    def prd_file(self) -> Path:
        """PRD 문서 파일"""
        return self.views_dir / "prd.md"
    
    # === 설정 파일들 ===
    @property
    def responsive_config(self) -> Path:
        """반응형 설정 파일"""
        return self.config_dir / "responsive_config.json"
    
    @property
    def css_file(self) -> Path:
        """메인 CSS 파일"""
        return self.static_dir / "improved_dashboard.css"
    
    # === Google Sheets 관련 파일들 ===
    @property
    def google_credentials_dir(self) -> Path:
        """Google 인증 파일 디렉토리"""
        creds_path = self._dashboard_root / "credentials"
        creds_path.mkdir(exist_ok=True)
        return creds_path
    
    @property
    def google_service_account_file(self) -> Path:
        """Google Service Account JSON 파일"""
        return self.google_credentials_dir / "service_account.json"
    
    @property
    def google_oauth_credentials(self) -> Path:
        """Google OAuth 인증 파일"""
        return self.google_credentials_dir / "oauth_credentials.json"
    
    @property
    def google_token_file(self) -> Path:
        """Google 토큰 파일"""
        return self.google_credentials_dir / "token.json"
    
    # === 메인 애플리케이션 파일들 ===
    @property
    def main_dashboard_file(self) -> Path:
        """메인 대시보드 파일"""
        return self._dashboard_root / "main_dashboard.py"
    
    # === 유틸리티 메서드 ===
    def get_component_path(self, component_name: str) -> Path:
        """컴포넌트 파일 경로 가져오기"""
        if not component_name.endswith('.py'):
            component_name += '.py'
        return self.components_dir / component_name
    
    def get_view_path(self, view_name: str) -> Path:
        """뷰 파일 경로 가져오기"""
        if not view_name.endswith('.py'):
            view_name += '.py'
        return self.views_dir / view_name
    
    def get_utils_path(self, util_name: str) -> Path:
        """유틸리티 파일 경로 가져오기"""
        if not util_name.endswith('.py'):
            util_name += '.py'
        return self.utils_dir / util_name
    
    def ensure_directory_exists(self, directory_path: Path) -> Path:
        """디렉토리 존재 확인 및 생성"""
        directory_path.mkdir(parents=True, exist_ok=True)
        return directory_path
    
    def get_relative_path(self, target_path: Path, base_path: Optional[Path] = None) -> str:
        """상대 경로 계산"""
        if base_path is None:
            base_path = self._dashboard_root
        
        try:
            return str(target_path.relative_to(base_path))
        except ValueError:
            # 상대 경로로 만들 수 없는 경우 절대 경로 반환
            return str(target_path)
    
    def create_import_path(self, module_path: Path) -> str:
        """모듈 import용 경로 생성"""
        # dashboard_root 기준으로 상대 경로 계산
        relative_path = self.get_relative_path(module_path, self._dashboard_root)
        
        # .py 확장자 제거
        if relative_path.endswith('.py'):
            relative_path = relative_path[:-3]
        
        # 슬래시를 점으로 변경
        import_path = relative_path.replace('/', '.').replace('\\', '.')
        
        return import_path
    
    # === 환경별 설정 ===
    def is_development(self) -> bool:
        """개발 환경 여부 확인"""
        return os.getenv('STREAMLIT_ENV', 'development') == 'development'
    
    def is_production(self) -> bool:
        """운영 환경 여부 확인"""
        return os.getenv('STREAMLIT_ENV') == 'production'
    
    # === 정보 출력 ===
    def get_path_summary(self) -> Dict[str, str]:
        """경로 정보 요약"""
        return {
            "프로젝트 루트": str(self.project_root),
            "대시보드 루트": str(self.dashboard_root),
            "설정 디렉토리": str(self.config_dir),
            "컴포넌트 디렉토리": str(self.components_dir),
            "뷰 디렉토리": str(self.views_dir),
            "유틸리티 디렉토리": str(self.utils_dir),
            "정적 파일 디렉토리": str(self.static_dir),
            "스크린샷 디렉토리": str(self.screenshot_dir),
            "데이터베이스 파일": str(self.database_file),
            "PRD 파일": str(self.prd_file)
        }
    
    def print_path_summary(self):
        """경로 정보 출력"""
        print("\n=== 프로젝트 경로 구조 ===")
        for key, value in self.get_path_summary().items():
            print(f"{key}: {value}")
        print("=" * 50)


# 전역 인스턴스 생성
_path_manager_instance = None

def get_path_manager() -> PathManager:
    """PathManager 싱글톤 인스턴스 반환"""
    global _path_manager_instance
    if _path_manager_instance is None:
        _path_manager_instance = PathManager()
    return _path_manager_instance

# 편의 함수들
def get_project_root() -> Path:
    """프로젝트 루트 경로"""
    return get_path_manager().project_root

def get_dashboard_root() -> Path:
    """대시보드 루트 경로"""
    return get_path_manager().dashboard_root

def get_component_path(component_name: str) -> Path:
    """컴포넌트 파일 경로"""
    return get_path_manager().get_component_path(component_name)

def get_view_path(view_name: str) -> Path:
    """뷰 파일 경로"""
    return get_path_manager().get_view_path(view_name)

def get_utils_path(util_name: str) -> Path:
    """유틸리티 파일 경로"""
    return get_path_manager().get_utils_path(util_name)

def ensure_directory_exists(directory_path: Path) -> Path:
    """디렉토리 존재 확인 및 생성"""
    return get_path_manager().ensure_directory_exists(directory_path)


if __name__ == "__main__":
    # 테스트 실행
    pm = get_path_manager()
    pm.print_path_summary()
    
    # 중요 디렉토리들 존재 확인
    important_dirs = [
        pm.components_dir,
        pm.views_dir,
        pm.utils_dir,
        pm.static_dir,
        pm.screenshot_dir,
        pm.google_credentials_dir
    ]
    
    print("\n=== 디렉토리 존재 확인 ===")
    for directory in important_dirs:
        exists = "✅" if directory.exists() else "❌"
        print(f"{exists} {directory}")