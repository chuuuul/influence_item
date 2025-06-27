#\!/bin/bash

# n8n이 실제로 사용하는 경로 설정
export N8N_USER_FOLDER=/Users/chul

echo "워크플로우 import 시작..."

workflows=(
    'master_automation_pipeline_v2.json'
    '01_daily_rss_collection.json'
    '02_channel_discovery.json'
    '03_ai_analysis_pipeline.json'
    'google-sheets-sync-workflow.json'
    'notification-routing-workflow.json'
)

for wf in "${workflows[@]}"; do
    filepath="/Users/chul/Documents/claude/influence_item/n8n/workflows/$wf"
    if [ -f "$filepath" ]; then
        n8n import:workflow --input="$filepath"
        echo "✅ $wf imported"
    else
        echo "❌ $wf not found"
    fi
done

echo "Import 완료\!"
