---
project_name: 연예인 추천 아이템 자동화 릴스 시스템
current_milestone_id: M01
highest_sprint_in_milestone: S03
current_sprint_id: S03
status: active
last_updated: 2025-06-23 04:47:00
---

# Project Manifest: 연예인 추천 아이템 자동화 릴스 시스템

이 매니페스트는 프로젝트의 중앙 참조점 역할을 하며, 현재 진행 상황과 주요 문서들을 연결합니다.

## 1. 프로젝트 비전 & 개요

연예인이 YouTube 영상에서 사용하는 제품을 AI로 자동 탐지하고, Instagram Reels용 콘텐츠를 생성하여 쿠팡 파트너스를 통한 제휴 마케팅 수익을 창출하는 완전 자동화 시스템입니다.

**핵심 가치:**
- 수동 작업 80% 감소를 통한 효율성 극대화
- AI 2-Pass 파이프라인으로 90% 이상 정확도 달성
- 월 15,000원 비용으로 월 900편 영상 분석 가능
- 24/7 무인 자동화 운영

이 프로젝트는 마일스톤 기반 개발 방식을 따릅니다.

## 2. 현재 진행 상황

- **마일스톤:** M01 - AI Pipeline Foundation
- **스프린트:** S03 - Filtering & Verification System

## 3. 현재 마일스톤의 스프린트들

### S01 Core AI Engine (✅ COMPLETED)

✅ T01_S01 - Whisper 음성 인식 모듈 구현 (완료)
✅ T02_S01 - Gemini 1차 분석 프롬프트 엔지니어링 (완료)
✅ T03_S01 - Gemini 2차 분석 종합 정보 추출 (완료)
✅ T04_S01 - 통합 파이프라인 구축 (완료)
✅ T05_S01 - 테스트 케이스 검증 (완료)

### S02 Visual Analysis Integration (✅ COMPLETED)

✅ T01_S02 - EasyOCR 텍스트 인식 구현 (완료)
✅ T02_S02 - YOLOv8 객체 인식 통합 (완료)
✅ T03_S02 - 음성+시각 데이터 융합 로직 (완료)
✅ T04_S02 - GPU 서버 최적화 (완료)
✅ T05_S02 - 타겟 시간대 시각 분석 (완료)

### S03 Filtering & Verification System (✅ COMPLETED)

✅ T01A_S03 - PPL 패턴 분석 기초 모듈 (완료)
✅ T01B_S03 - PPL 컨텍스트 분석 및 통합 (완료)
✅ T02_S03 - 쿠팡 파트너스 API 연동 (완료)
✅ T03_S03 - 매력도 스코어링 시스템 (완료)
✅ T04_S03 - 자동 필터링 워크플로우 (완료)
✅ T05_S03 - 최종 JSON 스키마 완성 (완료 - 2025-06-23 04:47)

## 4. 주요 문서

- [아키텍처 문서](./01_PROJECT_DOCS/ARCHITECTURE.md)
- [현재 마일스톤 요구사항](./02_REQUIREMENTS/M01_AI_Pipeline_Foundation/)
- [일반 태스크](./04_GENERAL_TASKS/)
- [PRD 문서](../prd.md)

## 5. 빠른 링크

- **현재 스프린트:** [S03 Filtering & Verification System](./03_SPRINTS/S03_M01_Filtering_Verification_System/)
- **활성 태스크:** 스프린트 폴더에서 T##_S03_*.md 파일 확인
- **완료된 스프린트:** [S01 Core AI Engine](./03_SPRINTS/S01_M01_Core_AI_Engine/)
- **다음 스프린트:** [S03 Filtering & Verification System](./03_SPRINTS/S03_M01_Filtering_Verification_System/)
- **프로젝트 리뷰:** [최신 리뷰](./10_STATE_OF_PROJECT/)

## 6. 핵심 성공 지표

### 기술적 목표
- AI 분석 정확도: >90%
- 영상당 처리 시간: <3분
- 시스템 가동률: >99%

### 비즈니스 목표  
- 일 평균 승인 후보: >5개
- 수익화 전환율: >30%
- 시스템 ROI: >300%

## 7. 다음 마일스톤 예정

**M02 - Management Dashboard (예정일: 2025-07-16)**
- Streamlit 기반 관리 대시보드
- 실시간 후보 검토 및 승인 시스템
- AI 생성 콘텐츠 관리 도구
