import json
import os
import subprocess

# PRD 기반 핵심 워크플로우 목록
core_workflows = [
    'master_automation_pipeline_v2.json',  # 메인 자동화 파이프라인 (매일 7시 실행)
    '01_daily_rss_collection.json',        # RSS 피드 수집
    '02_channel_discovery.json',           # 채널 탐색
    '03_ai_analysis_pipeline.json',        # AI 2-Pass 분석
    'google-sheets-sync-workflow.json',    # Google Sheets 연동
    'notification-routing-workflow.json'   # Slack 알림
]

workflow_dir = '/Users/chul/Documents/claude/influence_item/n8n/workflows'
successful_imports = []
failed_imports = []

print("PRD 기반 n8n 워크플로우 import 시작...")
print("=" * 50)

for workflow_file in core_workflows:
    filepath = os.path.join(workflow_dir, workflow_file)
    
    if not os.path.exists(filepath):
        print(f"⚠️  {workflow_file} - 파일이 존재하지 않음")
        failed_imports.append((workflow_file, "File not found"))
        continue
    
    # JSON 유효성 검사
    try:
        with open(filepath, 'r') as f:
            json.load(f)
        print(f"✓ {workflow_file} - JSON 유효성 검사 통과")
        
        # n8n import 실행
        result = subprocess.run(
            ['n8n', 'import:workflow', f'--input={filepath}'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {workflow_file} - Import 성공!")
            successful_imports.append(workflow_file)
        else:
            print(f"❌ {workflow_file} - Import 실패: {result.stderr}")
            failed_imports.append((workflow_file, result.stderr))
            
    except json.JSONDecodeError as e:
        print(f"❌ {workflow_file} - JSON 파싱 오류: {str(e)}")
        failed_imports.append((workflow_file, str(e)))
    
    print("-" * 50)

# 결과 요약
print("\n\n=== Import 결과 요약 ===")
print(f"✅ 성공: {len(successful_imports)}개")
for wf in successful_imports:
    print(f"   - {wf}")

print(f"\n❌ 실패: {len(failed_imports)}개")
for wf, error in failed_imports:
    print(f"   - {wf}: {error[:100]}...")

print("\n💡 다음 단계:")
print("1. http://localhost:5678 에서 n8n 웹 인터페이스에 접속")
print("2. Owner 계정 생성 후 로그인")
print("3. Workflows 메뉴에서 import된 워크플로우 확인")
print("4. 각 워크플로우의 Credentials 설정 필요")