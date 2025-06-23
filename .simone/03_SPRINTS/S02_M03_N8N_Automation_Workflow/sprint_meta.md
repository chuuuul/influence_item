---
sprint_folder_name: S02_M03_N8N_Automation_Workflow
sprint_sequence_id: S02
milestone_id: M03
title: N8N Automation Workflow - 24/7 자동화 워크플로우 구축
status: in_progress
goal: n8n 기반 24/7 자동화 시스템을 구축하여 매일 새 영상 수집, 분석, 알림까지 완전 무인 운영이 가능하도록 한다.
last_updated: 2025-06-23T21:15:00Z
---

# Sprint: N8N Automation Workflow (S02)

## Sprint Goal
n8n 기반 24/7 자동화 시스템을 구축하여 매일 새 영상 수집, 분석, 알림까지 완전 무인 운영이 가능하도록 한다.

## Scope & Key Deliverables
- n8n 서버 설치 및 기본 구성
- 매일 오전 7시 자동 영상 수집 워크플로우
- Google Sheets 채널 목록 자동 연동
- RSS 피드 기반 새 영상 탐지 및 분석 트리거
- 분석 완료 후 Slack/Email 자동 알림 시스템
- 에러 발생 시 자동 복구 및 알림 로직
- 워크플로우 상태 모니터링 대시보드

## Definition of Done (for the Sprint)
- [ ] 매일 자동으로 새 영상이 수집되고 분석이 시작됨
- [ ] Google Sheets의 채널 목록 변경사항이 자동 반영됨
- [ ] 분석 완료 시 운영자에게 자동 알림 발송
- [ ] 시스템 에러 발생 시 자동 복구 시도 및 알림 발송
- [ ] n8n 워크플로우가 24시간 연속 정상 동작
- [ ] 수동 개입 없이 3일 연속 정상 운영 검증

## Tasks
- [ ] **T01_S02_M03** - n8n 서버 설정 및 기본 구성 (Medium)
  - Docker 배포, SSL 설정, 환경 구성 및 기본 테스트
  - File: `TX01_S02_M03_N8N_Server_Setup_Basic_Configuration.md`
- [ ] **T02_S02_M03** - 자동 영상 수집 워크플로우 구축 (Medium)
  - 매일 오전 7시 RSS 피드 기반 영상 수집 자동화
  - File: `T02_S02_M03_Automatic_Video_Collection_Workflow.md`
- [ ] **T03_S02_M03** - Google Sheets 연동 및 알림 시스템 (Medium)
  - 채널 목록 동기화 및 Slack/Email 알림 구현
  - File: `T03_S02_M03_Google_Sheets_Integration_Notification_System.md`

## Notes / Retrospective Points
- PRD Section 5.2의 n8n 워크플로우 예시를 정확히 구현
- Context7을 통해 n8n 문서를 적극 활용
- 기존 Python 시스템과의 매끄러운 연동 보장
- 월 예산 24,900원 내에서 효율적 운영