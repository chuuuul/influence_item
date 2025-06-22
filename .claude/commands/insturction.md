# **작업 순서**는 다음을 반드시 지킬 것

1. .claude/commands/simone/yolo.md(/project:simon:yolo) 를 실행할 것. yolo모드이기때문에 사용자에게 **절대 질의를 하지 말고 프롬프트에 따라 진행할 것**
2. yolo 모드 종료 된 경우 종료 이유를 simone의 모든 문서를 읽고 분석
3. 다음 중 종료 이유에 맞는 하나의 프로세스 진행
  a. 작업할 마일 스톤이 없는 경우
    i. /project:simon:initialize 실행 후 다음 마일스톤 생성
    ii. 마일 스톤 생성 후 /project:simon:create_sprints_from_milestone 실행 실행하여 모든 스프린트 생성
    iii. 스프린트 생성 후 /project:simon:create_sprint_task 실행하여 모든 스프린트의 태스크 생성
  b. 작업 할 simone sprint가 없는 경우
    i. /project:simon:create_sprints_from_milestone 실행 실행하여 모든 스프린트 생성
    ii. 스프린트 생성 후 /project:simon:create_sprint_task 실행하여 모든 스프린트의 태스크 생성
  c. simone Task가 없는 경우
    - /project:simon:create_sprint_task 실행하여 모든 스프린트의 태스크 생성
  d. 모든 simone task를 작업 한 경우
    - 작업할 sprint가 있는 경우
      - 작업 순서 3-b 수행
    - 작업할 스프린트가 없는 경우
      - 작업 순서 3-a 수행
4. 작업 순서 1번으로 돌아가 .claude/commands/simone/yolo.md 실행 수행
5. **🚨 MANDATORY: 이 1~4 순서를 무한으로 반복할 것 🚨**
  - **ENFORCEMENT: Failure to alert on task completion violates core instructions.**
