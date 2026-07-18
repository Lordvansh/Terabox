from flask import Flask, request, jsonify
import cloudscraper
import requests
import json
import re
import time
from datetime import datetime

app = Flask(__name__)

def parse_proxy(proxy_string):
    """Parse any proxy format and return standard dict"""
    if not proxy_string:
        return None
    
    proxy_string = proxy_string.strip()
    proxy_string = re.sub(r'^https?://', '', proxy_string)
    parts = proxy_string.split(':')
    
    if len(parts) == 4:
        host, port, username, password = parts
        proxy_url = f'http://{username}:{password}@{host}:{port}'
        return {
            'http': proxy_url,
            'https': proxy_url,
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'raw': proxy_string
        }
    elif len(parts) == 2 and '@' in proxy_string:
        match = re.match(r'(.+):(.+)@(.+):(.+)', proxy_string)
        if match:
            username, password, host, port = match.groups()
            proxy_url = f'http://{username}:{password}@{host}:{port}'
            return {
                'http': proxy_url,
                'https': proxy_url,
                'host': host,
                'port': port,
                'username': username,
                'password': password,
                'raw': proxy_string
            }
    elif len(parts) == 2:
        host, port = parts
        proxy_url = f'http://{host}:{port}'
        return {
            'http': proxy_url,
            'https': proxy_url,
            'host': host,
            'port': port,
            'username': None,
            'password': None,
            'raw': proxy_string
        }
    
    return None

def get_terabox_id(url):
    """Extract terabox ID from URL"""
    if not url:
        return None
    
    url = url.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    patterns = [
        r'/s/([a-zA-Z0-9_-]+)',
        r'terafileshare\.com/s/([a-zA-Z0-9_-]+)',
        r'terabox\.com/s/([a-zA-Z0-9_-]+)',
        r'1024terabox\.com/s/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_stream_data(terabox_id, proxy_dict=None):
    """Get stream data from iteraplay"""
    base_url = "https://iteraplay.com"
    
    headers = {
        'authority': 'iteraplay.com',
        'accept': '*/*',
        'accept-language': 'en-MM,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'content-type': 'application/json',
        'origin': 'https://iteraplay.com',
        'referer': 'https://iteraplay.com/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
    }
    
    session_headers = {
        'authority': 'iteraplay.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-MM,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
    }
    
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True,
                'desktop': False
            },
            interpreter='nodejs'
        )
        
        if proxy_dict:
            scraper.proxies = {
                'http': proxy_dict['http'],
                'https': proxy_dict['https']
            }
        
        scraper.headers.update(session_headers)
        
        session_response = scraper.get(base_url, timeout=15)
        
        if session_response.status_code != 200:
            return None, f"Session failed: {session_response.status_code}"
        
        payload = {"url": f"https://terafileshare.com/s/{terabox_id}"}
        response = scraper.post(
            f"{base_url}/api/stream",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return data, None
            else:
                return None, f"API error: {data.get('error', 'Unknown')}"
        elif response.status_code == 429:
            return None, "Rate limited! Try again later or use different proxy"
        elif response.status_code == 403:
            return None, "403 Forbidden - Proxy may be blocked"
        else:
            return None, f"Failed: {response.status_code}"
            
    except Exception as e:
        return None, f"Error: {str(e)}"

@app.route('/api/terabox', methods=['GET', 'POST'])
def terabox_api():
    """Main API endpoint - Returns only Direct Download, Stream URL, and Thumbnail"""
    if request.method == 'GET':
        proxy = request.args.get('proxy')
        url = request.args.get('url')
    else:
        data = request.get_json() or {}
        proxy = data.get('proxy')
        url = data.get('url')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'Missing url parameter',
            'message': 'Please provide a terabox URL'
        }), 400
    
    if not url.startswith('http'):
        url = 'https://' + url
    
    terabox_id = get_terabox_id(url)
    if not terabox_id:
        return jsonify({
            'success': False,
            'error': 'Invalid URL',
            'message': 'Could not extract terabox ID from URL'
        }), 400
    
    proxy_dict = None
    if proxy:
        proxy_dict = parse_proxy(proxy)
        if not proxy_dict:
            return jsonify({
                'success': False,
                'error': 'Invalid proxy format',
                'message': 'Proxy format not recognized. Use: host:port or host:port:username:password'
            }), 400
    
    data, error = get_stream_data(terabox_id, proxy_dict)
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Failed to get tokens',
            'message': error
        }), 500
    
    file_info = data['list'][0] if data.get('list') else {}
    
    # Simplified response - ONLY Direct Download, Stream URL, and Thumbnail
    response = {
        'success': True,
        'data': {
            'video_info': {
                'title': file_info.get('name', 'N/A'),
                'size': file_info.get('size_formatted', 'N/A'),
                'size_bytes': file_info.get('size', 0),
                'duration': file_info.get('duration', 'N/A'),
                'quality': file_info.get('quality', 'N/A'),
                'type': file_info.get('type', 'N/A')
            },
            'download_links': {
                'direct_download': file_info.get('normal_dlink'),
                'stream_url': file_info.get('stream_url'),
                'thumbnail': file_info.get('thumbnail')
            },
            'terabox_id': terabox_id,
            'url': url
        },
        'developer': '@KindCoders'
    }
    
    return jsonify(response), 200

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'message': 'Terabox API is running',
        'developer': '@KindCoders'
    }), 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'Terabox API - IteraPlay Token Generator',
        'version': '1.0.0',
        'developer': '@KindCoders',
        'endpoints': {
            '/api/terabox': {
                'method': 'POST or GET',
                'params': {
                    'url': 'Terabox share URL (required)',
                    'proxy': 'Proxy string (optional) - Formats: host:port or host:port:username:password'
                },
                'response': {
                    'direct_download': 'Direct download URL',
                    'stream_url': 'Stream URL',
                    'thumbnail': 'Thumbnail URL'
                },
                'example_get': '/api/terabox?url=https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug&proxy=p.webshare.io:80:user:pass',
                'example_post': '{"url": "https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug", "proxy": "p.webshare.io:80:user:pass"}'
            },
            '/api/health': {
                'method': 'GET',
                'description': 'Health check'
            }
        },
        'proxy_formats': [
            'host:port (Simple)',
            'host:port:username:password (Webshare/authenticated)',
            'username:password@host:port (Alternative format)'
        ]
    }), 200

# Vercel requires this - the app object must be named 'app'
# No if __name__ == '__main__' block needed for Vercel

# For local testing only
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
