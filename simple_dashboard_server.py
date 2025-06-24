#!/usr/bin/env python3
"""
간단한 대시보드 서버 (Flask 기반)
Streamlit 대신 간단한 웹 인터페이스로 테스트
"""

from flask import Flask, render_template_string, request, jsonify
import sys
from pathlib import Path
from datetime import date, timedelta
import json

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 채널 탐색 모듈 import
from src.channel_discovery import (
    ChannelDiscoveryEngine, DiscoveryConfig, ChannelCandidate,
    ChannelType, ChannelStatus, DEFAULT_CELEBRITY_KEYWORDS
)

app = Flask(__name__)

# 간단한 HTML 템플릿
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>채널 탐색 시스템</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; text-align: center; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, textarea, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        button { background-color: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #2980b9; }
        .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
        .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .warning { background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
        .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .results { margin-top: 20px; }
        .candidate { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; background-color: white; }
        .candidate h3 { margin-top: 0; color: #2c3e50; }
        .score { font-weight: bold; color: #e74c3c; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 신규 채널 탐색 시스템</h1>
        <p style="text-align: center; color: #7f8c8d;">PRD 2.1 요구사항에 따른 채널 자동 탐색 및 평가</p>
        
        <div class="section">
            <h2>📊 시스템 상태</h2>
            <div class="status success">
                ✅ 채널 탐색 엔진: 정상 동작<br>
                ✅ 매칭 알고리즘: 정상 동작<br>
                ✅ 점수화 시스템: 정상 동작<br>
                ⚠️ Google Sheets 연동: 비활성화 (gspread 라이브러리 필요)<br>
                ⚠️ YouTube API: API 키 필요
            </div>
        </div>
        
        <div class="section">
            <h2>🚀 새로운 채널 탐색</h2>
            <form id="discoveryForm">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div>
                        <div class="form-group">
                            <label>탐색 키워드 (쉼표로 구분)</label>
                            <textarea id="keywords" rows="3" placeholder="뷰티, 패션, 메이크업, 스킨케어">{{ default_keywords }}</textarea>
                        </div>
                        
                        <div class="form-group">
                            <label>최소 구독자 수</label>
                            <input type="number" id="minSubscribers" value="1000" min="0">
                        </div>
                        
                        <div class="form-group">
                            <label>최대 후보 수</label>
                            <input type="number" id="maxCandidates" value="10" min="1" max="50">
                        </div>
                    </div>
                    
                    <div>
                        <div class="form-group">
                            <label>채널 타입</label>
                            <select id="channelType">
                                <option value="CELEBRITY_PERSONAL">연예인 개인</option>
                                <option value="BEAUTY_INFLUENCER">뷰티 인플루언서</option>
                                <option value="FASHION_INFLUENCER">패션 인플루언서</option>
                                <option value="LIFESTYLE_INFLUENCER">라이프스타일 인플루언서</option>
                                <option value="OTHER">기타</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label>최소 점수</label>
                            <input type="range" id="minScore" min="0" max="100" value="30" oninput="document.getElementById('scoreValue').textContent = this.value">
                            <span id="scoreValue">30</span>점
                        </div>
                        
                        <div class="form-group">
                            <label>대상 국가</label>
                            <select id="targetCountry">
                                <option value="KR">한국</option>
                                <option value="US">미국</option>
                                <option value="">전체</option>
                            </select>
                        </div>
                    </div>
                </div>
                
                <button type="submit">🔍 탐색 시작</button>
            </form>
        </div>
        
        <div id="results" class="section" style="display: none;">
            <h2>📋 탐색 결과</h2>
            <div id="resultsContent"></div>
        </div>
        
        <div class="section">
            <h2>📊 샘플 데이터</h2>
            <p>실제 API 연동 없이 시스템 동작을 확인할 수 있는 샘플 데이터입니다.</p>
            <button onclick="showSampleData()">샘플 데이터 보기</button>
            <div id="sampleData" style="display: none; margin-top: 15px;"></div>
        </div>
    </div>
    
    <script>
        document.getElementById('discoveryForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = {
                keywords: document.getElementById('keywords').value,
                minSubscribers: document.getElementById('minSubscribers').value,
                maxCandidates: document.getElementById('maxCandidates').value,
                channelType: document.getElementById('channelType').value,
                minScore: document.getElementById('minScore').value,
                targetCountry: document.getElementById('targetCountry').value
            };
            
            fetch('/discover', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('results').style.display = 'block';
                document.getElementById('resultsContent').innerHTML = data.html;
            })
            .catch(error => {
                console.error('Error:', error);
                alert('탐색 중 오류가 발생했습니다.');
            });
        });
        
        function showSampleData() {
            const sampleHtml = `
                <table>
                    <tr><th>채널명</th><th>구독자수</th><th>총점수</th><th>등급</th><th>상태</th></tr>
                    <tr><td>뷰티 채널 A</td><td>125,000</td><td>87.5</td><td>A</td><td>검토대기</td></tr>
                    <tr><td>패션 채널 B</td><td>89,000</td><td>76.2</td><td>B</td><td>검토대기</td></tr>
                    <tr><td>라이프스타일 채널 C</td><td>156,000</td><td>92.1</td><td>S</td><td>검토대기</td></tr>
                    <tr><td>메이크업 채널 D</td><td>67,000</td><td>68.9</td><td>C</td><td>검토대기</td></tr>
                    <tr><td>스킨케어 채널 E</td><td>203,000</td><td>84.3</td><td>A</td><td>검토대기</td></tr>
                </table>
            `;
            document.getElementById('sampleData').style.display = 'block';
            document.getElementById('sampleData').innerHTML = sampleHtml;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """메인 대시보드 페이지"""
    default_keywords = ", ".join(DEFAULT_CELEBRITY_KEYWORDS[:10])
    return render_template_string(DASHBOARD_TEMPLATE, default_keywords=default_keywords)

@app.route('/discover', methods=['POST'])
def discover_channels():
    """채널 탐색 실행"""
    
    try:
        data = request.json
        
        # 입력 데이터 검증
        keywords_text = data.get('keywords', '')
        if not keywords_text.strip():
            return jsonify({
                'success': False,
                'error': '키워드를 입력해주세요.',
                'html': '<div class="error">키워드를 입력해주세요.</div>'
            })
        
        # 설정 생성
        keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
        
        config = DiscoveryConfig(
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            target_keywords=keywords,
            target_channel_types=[ChannelType(data.get('channelType', 'OTHER'))],
            min_subscriber_count=int(data.get('minSubscribers', 1000)),
            max_total_candidates=int(data.get('maxCandidates', 10)),
            min_matching_score=float(data.get('minScore', 30)) / 100,
            target_country=data.get('targetCountry') if data.get('targetCountry') else None
        )
        
        # 모의 탐색 결과 생성 (실제 API 없이)
        mock_candidates = create_mock_candidates(config)
        
        # HTML 결과 생성
        results_html = generate_results_html(mock_candidates, config)
        
        return jsonify({
            'success': True,
            'candidates_count': len(mock_candidates),
            'html': results_html
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'html': f'<div class="error">오류 발생: {str(e)}</div>'
        })

def create_mock_candidates(config: DiscoveryConfig):
    """모의 채널 후보 생성"""
    
    candidates = []
    
    for i, keyword in enumerate(config.target_keywords[:config.max_total_candidates]):
        candidate = ChannelCandidate(
            channel_id=f"mock_channel_{i+1}",
            channel_name=f"{keyword} 전문 채널 {i+1}",
            channel_url=f"https://youtube.com/channel/mock_channel_{i+1}",
            subscriber_count=config.min_subscriber_count + (i * 10000),
            video_count=50 + (i * 20),
            view_count=(config.min_subscriber_count + (i * 10000)) * 100,
            description=f"{keyword} 관련 콘텐츠를 제작하는 전문 채널입니다. 다양한 {keyword} 정보와 팁을 제공합니다.",
            channel_type=config.target_channel_types[0] if config.target_channel_types else ChannelType.OTHER,
            status=ChannelStatus.DISCOVERED,
            total_score=60 + (i * 5) + (i % 3) * 10,  # 60-90점 범위의 점수
            keywords=[keyword, f"{keyword}_팁", f"{keyword}_추천"],
            verified=(i % 3 == 0),  # 일부만 인증됨
            matching_scores={
                'matching': 0.7 + (i * 0.05),
                'quality': 0.6 + (i * 0.08),
                'potential': 0.5 + (i * 0.07),
                'monetization': 0.4 + (i * 0.06)
            },
            metadata={
                'grade': ['C', 'B', 'A', 'S'][min(i, 3)],
                'strengths': [f"{keyword} 전문성", "꾸준한 업로드", "높은 참여도"],
                'weaknesses': ["제한적 주제", "해외 진출 필요"] if i % 2 == 0 else ["콘텐츠 다양성 부족"]
            }
        )
        candidates.append(candidate)
    
    # 점수순으로 정렬
    candidates.sort(key=lambda x: x.total_score, reverse=True)
    
    return candidates

def generate_results_html(candidates, config):
    """결과 HTML 생성"""
    
    if not candidates:
        return '<div class="warning">조건에 맞는 채널을 찾을 수 없습니다.</div>'
    
    # 통계 정보
    avg_score = sum(c.total_score for c in candidates) / len(candidates)
    high_score_count = len([c for c in candidates if c.total_score >= 80])
    verified_count = len([c for c in candidates if c.verified])
    
    html = f"""
    <div class="status success">
        ✅ 탐색 완료! {len(candidates)}개의 채널 후보를 발견했습니다.
    </div>
    
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0;">
        <div style="text-align: center; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
            <h3 style="margin: 0; color: #495057;">총 후보 수</h3>
            <p style="font-size: 24px; font-weight: bold; color: #007bff; margin: 5px 0;">{len(candidates)}</p>
        </div>
        <div style="text-align: center; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
            <h3 style="margin: 0; color: #495057;">평균 점수</h3>
            <p style="font-size: 24px; font-weight: bold; color: #28a745; margin: 5px 0;">{avg_score:.1f}</p>
        </div>
        <div style="text-align: center; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
            <h3 style="margin: 0; color: #495057;">고점수 후보</h3>
            <p style="font-size: 24px; font-weight: bold; color: #ffc107; margin: 5px 0;">{high_score_count}</p>
        </div>
        <div style="text-align: center; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
            <h3 style="margin: 0; color: #495057;">인증 채널</h3>
            <p style="font-size: 24px; font-weight: bold; color: #17a2b8; margin: 5px 0;">{verified_count}</p>
        </div>
    </div>
    
    <h3>🏆 상위 채널 후보</h3>
    """
    
    # 상위 후보 테이블
    html += '<table><tr><th>순위</th><th>채널명</th><th>구독자수</th><th>총점수</th><th>등급</th><th>인증</th><th>상태</th></tr>'
    
    for i, candidate in enumerate(candidates):
        verified_mark = "✅" if candidate.verified else ""
        score_color = "#28a745" if candidate.total_score >= 80 else "#ffc107" if candidate.total_score >= 60 else "#dc3545"
        
        html += f"""
        <tr>
            <td>{i+1}</td>
            <td><strong>{candidate.channel_name}</strong></td>
            <td>{candidate.subscriber_count:,}</td>
            <td style="color: {score_color}; font-weight: bold;">{candidate.total_score:.1f}</td>
            <td>{candidate.metadata.get('grade', '-') if candidate.metadata else '-'}</td>
            <td>{verified_mark}</td>
            <td>검토대기</td>
        </tr>
        """
    
    html += '</table>'
    
    # 상세 정보
    html += '<h3>📊 상세 분석</h3>'
    
    for candidate in candidates[:5]:  # 상위 5개만 상세 표시
        strengths = candidate.metadata.get('strengths', []) if candidate.metadata else []
        weaknesses = candidate.metadata.get('weaknesses', []) if candidate.metadata else []
        
        html += f"""
        <div class="candidate">
            <h3>{candidate.channel_name} (점수: {candidate.total_score:.1f})</h3>
            <p><strong>구독자:</strong> {candidate.subscriber_count:,} | <strong>영상수:</strong> {candidate.video_count:,} | <strong>조회수:</strong> {candidate.view_count:,}</p>
            <p><strong>설명:</strong> {candidate.description}</p>
            <p><strong>키워드:</strong> {', '.join(candidate.keywords) if candidate.keywords else '-'}</p>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <div>
                    <strong>💪 강점:</strong>
                    <ul>{''.join(f'<li>{s}</li>' for s in strengths)}</ul>
                </div>
                <div>
                    <strong>⚠️ 약점:</strong>
                    <ul>{''.join(f'<li>{w}</li>' for w in weaknesses)}</ul>
                </div>
            </div>
        </div>
        """
    
    return html

if __name__ == '__main__':
    print("🚀 채널 탐색 시스템 대시보드 서버 시작")
    print("📍 접속 주소: http://localhost:8080")
    print("⚠️  이 서버는 테스트용이며, 모의 데이터를 사용합니다.")
    
    app.run(host='0.0.0.0', port=8080, debug=True)