"""
채널 조사 플로우 - 주요 연예인 및 뷰티 채널 목록
PRD 명세에 따른 채널 목록 관리
"""

# 주요 연예인 개인 채널
CELEBRITY_CHANNELS = [
    {
        "name": "아이유 IU",
        "channel_id": "UC3SyT4_WLHzN7JmHQwKQZww",
        "handle": "@dlwlrma",
        "category": "음악/엔터테인먼트",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC3SyT4_WLHzN7JmHQwKQZww",
        "active": True,
        "priority": "high"
    },
    {
        "name": "홍지윤 Yoon",
        "channel_id": "UCj5o8m-NsazhIOq5iQqjgew",
        "handle": "@hongYoon",
        "category": "뷰티/라이프스타일",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCj5o8m-NsazhIOq5iQqjgew",
        "active": True,
        "priority": "high"
    },
    {
        "name": "이사배 RISABAE",
        "channel_id": "UCHVlf6nBy8wuD3yj9zlUAhA",
        "handle": "@RISABAE",
        "category": "뷰티/메이크업",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCHVlf6nBy8wuD3yj9zlUAhA",
        "active": True,
        "priority": "high"
    },
    {
        "name": "박민영",
        "channel_id": "UCmNz-nvlLm74qSpG8fhgxKQ",
        "handle": "@PMY_official",
        "category": "연기/엔터테인먼트",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCmNz-nvlLm74qSpG8fhgxKQ",
        "active": True,
        "priority": "medium"
    },
    {
        "name": "송혜교",
        "channel_id": "UCKqLfF1FcEkpkBJLzK5rvRg",
        "handle": "@songhyekyo",
        "category": "연기/라이프스타일",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCKqLfF1FcEkpkBJLzK5rvRg",
        "active": True,
        "priority": "medium"
    }
]

# 주요 미디어 채널 (연예인 콘텐츠 포함)
MEDIA_CHANNELS = [
    {
        "name": "VOGUE KOREA",
        "channel_id": "UCEf_Bc-KVd7onSeifS3py9g",
        "handle": "@voguekorea",
        "category": "패션/뷰티",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCEf_Bc-KVd7onSeifS3py9g",
        "active": True,
        "priority": "high",
        "filter_keywords": ["아이유", "박민영", "송혜교", "홍지윤", "이사배"]
    },
    {
        "name": "피식대학",
        "channel_id": "UCE86oi9x6YfsYBk8WpL64NQ",
        "handle": "@physickdae",
        "category": "엔터테인먼트",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCE86oi9x6YfsYBk8WpL64NQ",
        "active": True,
        "priority": "medium",
        "filter_keywords": ["아이유", "박민영", "송혜교"]
    },
    {
        "name": "Harper's BAZAAR Korea",
        "channel_id": "UCrpB8fNHjZJWNY4kYP4NfTQ",
        "handle": "@HarpersBazaarKorea",
        "category": "패션/뷰티",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCrpB8fNHjZJWNY4kYP4NfTQ",
        "active": True,
        "priority": "high",
        "filter_keywords": ["아이유", "박민영", "송혜교", "홍지윤", "이사배"]
    },
    {
        "name": "ELLE KOREA",
        "channel_id": "UCWdhP3_7Hq0sWPW8kj0BgtQ",
        "handle": "@ellekorea",
        "category": "패션/뷰티",
        "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCWdhP3_7Hq0sWPW8kj0BgtQ",
        "active": True,
        "priority": "high",
        "filter_keywords": ["아이유", "박민영", "송혜교", "홍지윤", "이사배"]
    }
]

# 전체 채널 목록 통합
ALL_CHANNELS = CELEBRITY_CHANNELS + MEDIA_CHANNELS

def get_active_channels():
    """활성 채널 목록 반환"""
    return [channel for channel in ALL_CHANNELS if channel["active"]]

def get_channels_by_priority(priority: str):
    """우선순위별 채널 목록 반환"""
    return [channel for channel in ALL_CHANNELS if channel["priority"] == priority]

def get_channel_by_name(name: str):
    """이름으로 채널 찾기"""
    for channel in ALL_CHANNELS:
        if channel["name"] == name:
            return channel
    return None

def get_rss_urls():
    """모든 활성 채널의 RSS URL 목록 반환"""
    return [channel["rss_url"] for channel in get_active_channels()]