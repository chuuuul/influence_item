#!/bin/bash
"""
매일 자동 채널 디스커버리를 위한 cron job 설정 스크립트
"""

# 프로젝트 디렉토리
PROJECT_DIR="/Users/chul/Documents/claude/influence_item"
SCRIPT_PATH="$PROJECT_DIR/scripts/daily_channel_discovery.py"
LOG_DIR="$PROJECT_DIR/logs"

# 로그 디렉토리 생성
mkdir -p "$LOG_DIR"

echo "🔧 매일 자동 채널 디스커버리 cron job 설정"
echo "=================================================="

# 현재 crontab 백업
echo "📄 현재 crontab 백업 중..."
crontab -l > crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || echo "기존 crontab 없음"

# 새 cron job 추가
echo "⚙️ 새 cron job 추가 중..."

# 매일 오전 9시에 실행하는 cron job
CRON_JOB="0 9 * * * cd $PROJECT_DIR && /opt/homebrew/bin/python3 $SCRIPT_PATH >> $LOG_DIR/cron_daily_discovery.log 2>&1"

# 기존 crontab에 새 job 추가
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job 설정 완료!"
echo ""
echo "📋 설정된 cron job:"
echo "$CRON_JOB"
echo ""
echo "🕘 실행 시간: 매일 오전 9시"
echo "📁 로그 파일: $LOG_DIR/cron_daily_discovery.log"
echo ""
echo "🔍 현재 crontab 확인:"
crontab -l
echo ""
echo "💡 수동 테스트 실행:"
echo "cd $PROJECT_DIR && python3 $SCRIPT_PATH"