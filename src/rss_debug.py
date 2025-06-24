#!/usr/bin/env python3
"""
RSS 피드 실패 원인 디버깅 도구
각 채널의 RSS URL을 개별적으로 테스트하고 오류 원인 파악
"""

import sys
import requests
import feedparser
from pathlib import Path
import urllib.parse

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.channel_list import ALL_CHANNELS

def test_single_rss(channel):
    """단일 RSS 피드 테스트"""
    print(f"\n{'='*60}")
    print(f"📺 채널: {channel['name']}")
    print(f"🔗 RSS URL: {channel['rss_url']}")
    print(f"📂 카테고리: {channel['category']}")
    
    try:
        # 1. 직접 HTTP 요청으로 상태 확인
        print(f"\n🌐 Step 1: HTTP 요청 테스트...")
        response = requests.get(channel['rss_url'], timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        print(f"   ✅ HTTP 상태 코드: {response.status_code}")
        print(f"   📏 응답 크기: {len(response.content)} bytes")
        print(f"   📋 Content-Type: {response.headers.get('content-type', 'Unknown')}")
        
        # 2. RSS 내용 일부 확인
        content_preview = response.text[:500]
        print(f"   📄 내용 미리보기: {content_preview[:100]}...")
        
        # 3. feedparser로 파싱 시도
        print(f"\n🔍 Step 2: feedparser 파싱 테스트...")
        feed = feedparser.parse(response.content)
        
        print(f"   📊 파싱 결과:")
        print(f"      - bozo: {feed.bozo}")
        if feed.bozo:
            print(f"      - bozo_exception: {feed.bozo_exception}")
        print(f"      - 피드 제목: {feed.feed.get('title', 'N/A')}")
        print(f"      - 항목 수: {len(feed.entries)}")
        
        # 4. 첫 번째 항목 분석
        if feed.entries:
            first_entry = feed.entries[0]
            print(f"   📹 첫 번째 항목:")
            print(f"      - 제목: {first_entry.get('title', 'N/A')[:50]}...")
            print(f"      - 링크: {first_entry.get('link', 'N/A')}")
            print(f"      - 발행일: {first_entry.get('published', 'N/A')}")
            print(f"      - ID: {first_entry.get('id', 'N/A')}")
        
        # 5. 성공 여부 판단
        if not feed.bozo and len(feed.entries) > 0:
            print(f"   ✅ RSS 피드 정상 작동")
            return True
        else:
            print(f"   ❌ RSS 피드 문제 발견")
            return False
            
    except requests.exceptions.Timeout:
        print(f"   ❌ 타임아웃 오류 (10초 초과)")
        return False
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 연결 오류 (네트워크 문제)")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"   ❌ HTTP 오류: {e}")
        return False
    except Exception as e:
        print(f"   ❌ 예상치 못한 오류: {type(e).__name__}: {e}")
        return False

def suggest_alternative_rss_url(channel):
    """대안 RSS URL 제안"""
    print(f"\n💡 대안 RSS URL 제안:")
    
    # YouTube 채널 ID에서 다양한 RSS URL 형식 시도
    channel_id = channel.get('channel_id')
    handle = channel.get('handle', '').replace('@', '')
    
    alternatives = []
    
    if channel_id:
        # 표준 채널 ID 형식
        alternatives.append(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
        
        # UC로 시작하지 않는 경우 UC 추가
        if not channel_id.startswith('UC'):
            alternatives.append(f"https://www.youtube.com/feeds/videos.xml?channel_id=UC{channel_id}")
    
    if handle:
        # 핸들명 기반
        alternatives.append(f"https://www.youtube.com/feeds/videos.xml?user={handle}")
        alternatives.append(f"https://www.youtube.com/@{handle}")
    
    for i, alt_url in enumerate(alternatives, 1):
        print(f"   {i}. {alt_url}")
    
    return alternatives

def test_alternative_urls(channel, alternatives):
    """대안 URL들 테스트"""
    print(f"\n🧪 대안 URL 테스트:")
    
    for i, alt_url in enumerate(alternatives, 1):
        print(f"\n   테스트 {i}: {alt_url}")
        try:
            response = requests.get(alt_url, timeout=5, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                if not feed.bozo and len(feed.entries) > 0:
                    print(f"      ✅ 성공! {len(feed.entries)}개 항목 발견")
                    print(f"      📺 피드 제목: {feed.feed.get('title', 'N/A')}")
                    return alt_url
                else:
                    print(f"      ⚠️  파싱 가능하지만 문제 있음 (bozo: {feed.bozo})")
            else:
                print(f"      ❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"      ❌ 오류: {str(e)[:50]}...")
    
    return None

def validate_youtube_channel(channel):
    """YouTube 채널 존재 여부 확인"""
    print(f"\n🔍 YouTube 채널 존재 여부 확인:")
    
    channel_id = channel.get('channel_id')
    handle = channel.get('handle', '').replace('@', '')
    
    # 1. 채널 ID로 확인
    if channel_id:
        channel_url = f"https://www.youtube.com/channel/{channel_id}"
        try:
            response = requests.get(channel_url, timeout=5)
            if response.status_code == 200:
                print(f"   ✅ 채널 ID 유효: {channel_url}")
            else:
                print(f"   ❌ 채널 ID 무효 (HTTP {response.status_code}): {channel_url}")
        except:
            print(f"   ❌ 채널 ID 확인 실패: {channel_url}")
    
    # 2. 핸들로 확인
    if handle:
        handle_url = f"https://www.youtube.com/@{handle}"
        try:
            response = requests.get(handle_url, timeout=5)
            if response.status_code == 200:
                print(f"   ✅ 핸들 유효: {handle_url}")
            else:
                print(f"   ❌ 핸들 무효 (HTTP {response.status_code}): {handle_url}")
        except:
            print(f"   ❌ 핸들 확인 실패: {handle_url}")

def main():
    """메인 디버깅 함수"""
    print("🔍 RSS 피드 실패 원인 분석 시작")
    print("="*80)
    
    failed_channels = []
    success_channels = []
    
    for channel in ALL_CHANNELS:
        if not channel.get('active', True):
            continue
            
        is_working = test_single_rss(channel)
        
        if not is_working:
            failed_channels.append(channel)
            validate_youtube_channel(channel)
            alternatives = suggest_alternative_rss_url(channel)
            working_url = test_alternative_urls(channel, alternatives)
            
            if working_url:
                print(f"   ✅ 대안 URL 발견: {working_url}")
                channel['suggested_rss_url'] = working_url
        else:
            success_channels.append(channel)
    
    # 최종 요약
    print(f"\n{'='*80}")
    print(f"📊 최종 분석 결과:")
    print(f"   ✅ 정상 작동: {len(success_channels)}개")
    print(f"   ❌ 실패: {len(failed_channels)}개")
    
    if success_channels:
        print(f"\n✅ 정상 작동 채널:")
        for ch in success_channels:
            print(f"   - {ch['name']}")
    
    if failed_channels:
        print(f"\n❌ 실패 채널:")
        for ch in failed_channels:
            print(f"   - {ch['name']}")
            if 'suggested_rss_url' in ch:
                print(f"     💡 제안 URL: {ch['suggested_rss_url']}")
    
    # 수정된 채널 목록 저장
    if failed_channels:
        print(f"\n💾 수정된 채널 목록 생성 중...")
        generate_fixed_channel_list(ALL_CHANNELS)

def generate_fixed_channel_list(channels):
    """수정된 채널 목록 파일 생성"""
    fixed_file = project_root / "data" / "channel_list_fixed.py"
    
    with open(fixed_file, 'w', encoding='utf-8') as f:
        f.write('"""\n수정된 채널 목록 - RSS 디버깅 결과 반영\n"""\n\n')
        f.write('# 디버깅을 통해 수정된 채널 목록\n')
        f.write('FIXED_CHANNELS = [\n')
        
        for channel in channels:
            if 'suggested_rss_url' in channel:
                channel['rss_url'] = channel['suggested_rss_url']
                del channel['suggested_rss_url']
            
            f.write(f'    {channel},\n')
        
        f.write(']\n')
    
    print(f"✅ 수정된 채널 목록 저장: {fixed_file}")

if __name__ == "__main__":
    main()