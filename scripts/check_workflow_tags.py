import json

workflows_to_check = [
    'master_automation_pipeline_v2.json',
    'google-sheets-sync-workflow.json',
    'notification-routing-workflow.json'
]

for workflow in workflows_to_check:
    filepath = f'/Users/chul/Documents/claude/influence_item/n8n/workflows/{workflow}'
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        print(f"\n=== {workflow} ===")
        print(f"태그: {data.get('tags', 'No tags field')}")
        
        # tags 필드가 문제가 될 수 있으므로 제거하고 저장
        if 'tags' in data:
            # 백업 생성
            with open(filepath + '.backup', 'w') as f:
                json.dump(data, f, indent=2)
            
            # tags 제거
            del data['tags']
            
            # 다시 저장
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"✅ {workflow} - tags 필드 제거됨")
        else:
            print(f"ℹ️ {workflow} - tags 필드 없음")
            
    except Exception as e:
        print(f"❌ {workflow} - 에러: {str(e)}")