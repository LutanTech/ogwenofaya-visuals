# known_bots.py
import re

BOT_PATTERNS = [
    (r'googlebot', 'Googlebot'),
    (r'bingbot', 'Bingbot'),
    (r'yandex', 'YandexBot'),
    (r'baidu', 'Baiduspider'),
    (r'duckduckbot', 'DuckDuckBot'),
    (r'slurp', 'Yahoo! Slurp'),
    (r'facebookexternalhit', 'Facebook Bot'),
    (r'twitterbot', 'Twitterbot'),
    (r'applebot', 'Applebot'),
    (r'semrushbot', 'SEMrushBot'),
    (r'ahrefsbot', 'AhrefsBot'),
    (r'petalbot', 'PetalBot'),
    (r'bytespider', 'ByteSpider'),
    (r'gptbot', 'GPTBot'),
    (r'chatgpt-user', 'ChatGPT-User'),
    (r'ccbot', 'CCBot'),
    (r'ia_archiver', 'Wayback Machine'),
    (r'bot|crawler|spider|scraper|archiver', 'Generic Bot')
]

def detect_bot(user_agent):
    if not user_agent:
        return False, None
    ua_lower = user_agent.lower()
    for pattern, name in BOT_PATTERNS:
        if re.search(pattern, ua_lower):
            return True, name
    return False, None