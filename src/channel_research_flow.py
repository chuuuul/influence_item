#!/usr/bin/env python3
"""
채널 조사 플로우 실행기
PRD에 따른 YouTube 채널 분석 및 영상 수집 자동화
"""

import sys
import os
import json
import requests
import feedparser
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    # 수정된 채널 목록이 있으면 우선 사용
    from data.channel_list_fixed import FIXED_CHANNELS
    print("✅ 수정된 채널 목록 사용")
    channels_source = FIXED_CHANNELS
except ImportError:
    # 없으면 기본 채널 목록 사용
    from data.channel_list import get_active_channels
    print("⚠️  기본 채널 목록 사용")
    channels_source = None
from src.whisper_processor.youtube_downloader import YouTubeDownloader

def collect_rss_feeds():
    """RSS 피드에서 최신 영상 수집"""
    print("🔍 Step 3: RSS 피드에서 최신 영상 수집 시작...")
    
    # 수정된 채널 목록 또는 기본 채널 목록 사용
    if channels_source:
        channels = [ch for ch in channels_source if ch.get('active', True)]
    else:
        channels = get_active_channels()
    collected_videos = []
    
    for channel in channels:
        print(f"\n📺 채널 처리 중: {channel['name']}")
        
        try:
            # RSS 피드 파싱
            feed = feedparser.parse(channel['rss_url'])
            
            if feed.bozo:
                print(f"⚠️  RSS 피드 파싱 오류: {channel['name']}")
                continue
                
            print(f"✅ RSS 피드 파싱 성공: {len(feed.entries)}개 항목 발견")
            
            # 최근 7일 이내 영상만 수집
            cutoff_date = datetime.now() - timedelta(days=7)
            
            for entry in feed.entries[:10]:  # 최대 10개만 처리
                try:
                    # 영상 정보 추출
                    video_data = {
                        'video_id': entry.id.split(':')[-1] if ':' in entry.id else entry.id,
                        'title': entry.title,
                        'description': entry.get('summary', ''),
                        'published': entry.published,
                        'link': entry.link,
                        'channel_name': channel['name'],
                        'channel_id': channel['channel_id'],
                        'category': channel['category']
                    }
                    
                    # 미디어 채널의 경우 필터링 키워드 확인
                    if 'filter_keywords' in channel:
                        title_lower = video_data['title'].lower()
                        if not any(keyword.lower() in title_lower for keyword in channel['filter_keywords']):
                            print(f"🔍 필터링됨: {video_data['title'][:50]}...")
                            continue
                    
                    collected_videos.append(video_data)
                    print(f"📹 수집됨: {video_data['title'][:50]}...")
                    
                except Exception as e:
                    print(f"❌ 영상 처리 오류: {str(e)}")
                    
        except Exception as e:
            print(f"❌ 채널 처리 오류 ({channel['name']}): {str(e)}")
    
    print(f"\n✅ RSS 수집 완료: 총 {len(collected_videos)}개 영상 수집")
    return collected_videos

def analyze_videos(videos):
    """수집된 영상에 대한 기본 분석"""
    print(f"\n🔬 Step 4: 수집된 영상 분석 시작 ({len(videos)}개)...")
    
    analysis_results = []
    downloader = YouTubeDownloader()
    
    for i, video in enumerate(videos[:5], 1):  # 테스트를 위해 처음 5개만 분석
        print(f"\n📊 분석 중 ({i}/5): {video['title'][:50]}...")
        
        try:
            # YouTube 영상 정보 상세 조회
            video_info = downloader.get_video_info(video['link'])
            
            if video_info:
                # 분석 결과 구성
                result = {
                    'video_id': video['video_id'],
                    'title': video['title'],
                    'channel_name': video['channel_name'],
                    'duration': video_info.get('duration', 0),
                    'view_count': video_info.get('view_count', 0),
                    'like_count': video_info.get('like_count', 0),
                    'upload_date': video_info.get('upload_date', ''),
                    'analysis_status': 'pending',
                    'monetization_potential': 'unknown',
                    'analysis_timestamp': datetime.now().isoformat()
                }
                
                # 간단한 매력도 스코어링 (실제로는 AI 분석 필요)
                score = calculate_attraction_score(result)
                result['attraction_score'] = score
                
                analysis_results.append(result)
                print(f"✅ 분석 완료 - 매력도 점수: {score:.1f}")
                
            else:
                print(f"❌ 영상 정보 조회 실패")
                
        except Exception as e:
            print(f"❌ 분석 오류: {str(e)}")
    
    print(f"\n✅ 영상 분석 완료: {len(analysis_results)}개 결과")
    return analysis_results

def calculate_attraction_score(video_info):
    """간단한 매력도 점수 계산 (실제로는 AI 모델 사용)"""
    score = 50.0  # 기본 점수
    
    # 조회수 기반 점수
    view_count = video_info.get('view_count', 0)
    if view_count > 100000:
        score += 20
    elif view_count > 50000:
        score += 15
    elif view_count > 10000:
        score += 10
    
    # 좋아요 수 기반 점수
    like_count = video_info.get('like_count', 0)
    if like_count > 1000:
        score += 15
    elif like_count > 500:
        score += 10
    elif like_count > 100:
        score += 5
    
    # 영상 길이 기반 점수 (적절한 길이 선호)
    duration = video_info.get('duration', 0)
    if 300 <= duration <= 1800:  # 5분~30분
        score += 10
    elif duration < 60:  # 1분 미만은 감점
        score -= 10
    
    return min(100.0, max(0.0, score))

def save_results(videos, analysis_results):
    """결과를 파일에 저장"""
    print(f"\n💾 Step 5: 결과 저장 중...")
    
    results_dir = project_root / "data" / "channel_research_results"
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 수집된 영상 목록 저장
    videos_file = results_dir / f"collected_videos_{timestamp}.json"
    with open(videos_file, 'w', encoding='utf-8') as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    
    # 분석 결과 저장
    analysis_file = results_dir / f"analysis_results_{timestamp}.json"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 결과 저장 완료:")
    print(f"   📁 영상 목록: {videos_file}")
    print(f"   📁 분석 결과: {analysis_file}")
    
    return videos_file, analysis_file

def generate_summary_report(videos, analysis_results):
    """요약 보고서 생성"""
    print(f"\n📊 Step 6: 요약 보고서 생성...")
    
    # 채널별 통계
    channel_stats = {}
    for video in videos:
        channel = video['channel_name']
        if channel not in channel_stats:
            channel_stats[channel] = 0
        channel_stats[channel] += 1
    
    # 매력도 점수별 분포
    score_distribution = {'high': 0, 'medium': 0, 'low': 0}
    for result in analysis_results:
        score = result.get('attraction_score', 0)
        if score >= 80:
            score_distribution['high'] += 1
        elif score >= 60:
            score_distribution['medium'] += 1
        else:
            score_distribution['low'] += 1
    
    report = {
        'summary': {
            'total_videos_collected': len(videos),
            'total_videos_analyzed': len(analysis_results),
            'timestamp': datetime.now().isoformat()
        },
        'channel_statistics': channel_stats,
        'score_distribution': score_distribution,
        'top_candidates': sorted(
            analysis_results, 
            key=lambda x: x.get('attraction_score', 0), 
            reverse=True
        )[:3]
    }
    
    print(f"📈 요약 보고서:")
    print(f"   총 수집 영상: {report['summary']['total_videos_collected']}개")
    print(f"   분석 완료: {report['summary']['total_videos_analyzed']}개")
    print(f"   채널별 분포: {dict(list(channel_stats.items())[:3])}...")
    print(f"   고득점(80+): {score_distribution['high']}개")
    print(f"   중간점수(60-79): {score_distribution['medium']}개")
    print(f"   저득점(<60): {score_distribution['low']}개")
    
    return report

def main():
    """메인 실행 함수"""
    print("🚀 채널 조사 플로우 시작")
    print("=" * 50)
    
    try:
        # Step 1: 채널 목록 확인
        print("📋 Step 1: 활성 채널 목록 확인...")
        if channels_source:
            channels = [ch for ch in channels_source if ch.get('active', True)]
        else:
            channels = get_active_channels()
        print(f"✅ {len(channels)}개 활성 채널 발견")
        for channel in channels:
            print(f"   - {channel['name']} ({channel['category']}) - 우선순위: {channel['priority']}")
        
        # Step 2: RSS 피드 수집
        videos = collect_rss_feeds()
        if not videos:
            print("❌ 수집된 영상이 없습니다.")
            return
        
        # Step 3: 영상 분석
        analysis_results = analyze_videos(videos)
        
        # Step 4: 결과 저장
        videos_file, analysis_file = save_results(videos, analysis_results)
        
        # Step 5: 요약 보고서
        report = generate_summary_report(videos, analysis_results)
        
        print("\n" + "=" * 50)
        print("✅ 채널 조사 플로우 완료!")
        print(f"📊 대시보드에서 결과를 확인하세요: http://localhost:8501")
        
    except Exception as e:
        print(f"❌ 플로우 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()