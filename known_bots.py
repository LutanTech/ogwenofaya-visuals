import ipaddress
import re

import dns.resolver
import dns.reversename

BOT_PATTERNS = [
    (r'googlebot', 'Googlebot'),
    (r'adsbot-google', 'Google AdsBot'),
    (r'bingbot', 'Bingbot'),
    (r'yandexrenderresourcesbot', 'Yandex Render Resources Bot'),
    (r'yandexaccessibilitybot', 'Yandex Accessibility Bot'),
    (r'yandexuserproxy', 'Yandex User Proxy'),
    (r'yandex', 'YandexBot'),
    (r'baidu', 'Baiduspider'),
    (r'duckduckbot', 'DuckDuckBot'),
    (r'slurp', 'Yahoo! Slurp'),
    (r'applebot', 'Applebot'),
    (r'facebookexternalhit', 'Facebook Bot'),
    (r'twitterbot', 'Twitterbot'),
    (r'tweetmemebot', 'TweetmemeBot'),
    (r'semrushbot', 'SEMrushBot'),
    (r'ahrefsbot', 'AhrefsBot'),
    (r'mj12bot', 'MJ12bot'),
    (r'dotbot', 'DotBot'),
    (r'petalbot', 'PetalBot'),
    (r'bytespider', 'ByteSpider'),
    (r'gptbot', 'GPTBot'),
    (r'chatgpt-user', 'ChatGPT-User'),
    (r'ccbot', 'CCBot'),
    (r'ia_archiver', 'Wayback Machine'),
    (r'seznambot', 'SeznamBot'),
    (r'exabot', 'Exabot'),
    (r'qwantify', 'Qwantify'),
    (r'coccocbot', 'CocCocBot'),
    (r'amazonadbot', 'AmazonAdBot'),
    (r'mail\.ru_bot', 'Mail.RU Bot'),
    (r'quillbot', 'QuillBot'),
    (r'bitsightbot', 'BitSightBot'),
    (r'hanaleibot', 'HanaleiBot'),
    (r'backlinkspider', 'BacklinkSpider'),
    (r'statusnestbacklinkspider', 'StatusNest BacklinkSpider'),
    (r'abevalbot', 'ABEvalBot'),
    (r'contxbot', 'ContxBot'),
    (r'startmebot', 'Start.me Bot'),
    (r'centurybot', 'CenturyBot'),
    (r'go-http-client', 'Go HTTP Client'),
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



DNS_TIMEOUT = 2

VERIFIED_DOMAINS = {
    "Googlebot": ["googlebot.com"],
    "Google AdsBot": ["google.com"],
    "Bingbot": ["search.msn.com"]
}


def verify_bot_ip(ip, user_agent):
    is_bot, bot_name = detect_bot(user_agent)

    if not is_bot:
        return False, None, None

    domains = VERIFIED_DOMAINS.get(bot_name)

    if not domains:
        return False, None, None

    try:
        ip_obj = ipaddress.ip_address(ip)

        resolver = dns.resolver.Resolver()
        resolver.timeout = DNS_TIMEOUT
        resolver.lifetime = DNS_TIMEOUT

        reverse_name = dns.reversename.from_address(str(ip_obj))
        answers = resolver.resolve(reverse_name, "PTR")

        for answer in answers:
            hostname = str(answer.target).rstrip(".").lower()

            if not any(
                hostname == domain or hostname.endswith("." + domain)
                for domain in domains
            ):
                continue

            resolved_ips = set()

            for record_type in ("A", "AAAA"):
                try:
                    records = resolver.resolve(hostname, record_type)
                    resolved_ips.update(
                        ipaddress.ip_address(record.address)
                        for record in records
                    )
                except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                    continue

            if ip_obj in resolved_ips:
                return True, bot_name, hostname

        return False, bot_name, None

    except (ValueError, dns.exception.DNSException, OSError):
        return False, bot_name, None