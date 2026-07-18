from flask import Flask, request, jsonify
import cloudscraper
import requests
import json
import re
import time
from datetime import datetime

app = Flask(__name__)

# Your saved cookies as a HARDCODED dictionary (no parsing needed)
COOKIES = {
    "remember_me": "yes",
    "_ga_NFYSD8YZN4": "GS2.1.s1784384135$o1$g1$t1784384242$j27$l0$h0",
    "__secure_token": "eyJ1aWQiOm51bGwsInNpZCI6ImU5ZmEwNjlhNmI1MTczZWM4MDdlMDE3OWFhZDU3OWI2IiwidCI6MTc4NDM4NDI0MjgwNSwibiI6IjEwODAwZmM3YzAyYzgyY2MifTo6MzI2ZWYwMDQzZTZhYTBjNmNlODhiNmFkYmUxNWYyZTFmYjkwZTlmMzQ5MjBhZTdhM2EzNWM3ZGRiNzQ1OTQ2NQ%3D%3D",
    "_ga": "GA1.1.558453591.1784384135",
    "FCCDCF": "%5Bnull%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2C%5B%5B32%2C%22%5B%5C%2289fec263-4582-4899-93f3-f98160446051%5C%22%2C%5B1784384136%5D%5D%22%5D%5D%5D",
    "FCNEC": "%5B%5B%22AKsRol9TLkQ2UJYcRn72sbYVFRmdKbj829okOONU4bmrqE7zgWJ2NTFKjqoruvwlXaLVyxHLmc24a6XID7ZXSq0aYe2L80agFHmQnep_15x9iuo9X8OGAv5DI3VYIbqeAU6EGyGY7oUBnBMu2rDFNu3KwGY8QYGdwA%3D%3D%22%5D%2Cnull%2C%5B%5B21%2C%22%5B%5B%5B%5B5%2C1%2C%5B0%5D%5D%2C%5B1784384138%2C145374000%5D%2C%5B1209600%5D%5D%5D%5D%22%5D%5D%5D",
    "login_token": "f0f7cf11ab5adeb1d35cce1df4d0692e383c87d89bc1798edc92b73dd266499181b73aaa48a406d2350abbcd204b2ebc5e24d34613b1e991fe57863667fa25cb",
    "session_id": "e9fa069a6b5173ec807e0179aad579b6"
}

def get_stream_data(terabox_url):
    """Get stream data using hardcoded cookies"""
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
    
    try:
        # Create scraper
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True,
                'desktop': False
            },
            interpreter='python'
        )
        
        # Set cookies directly
        for name, value in COOKIES.items():
            scraper.cookies.set(name, value)
        
        # First, visit the page to get verification token
        print("Visiting iteraplay.com...")
        response = scraper.get(base_url, timeout=15)
        print(f"Status: {response.status_code}")
        
        # Get CSRF token from cookies after page load
        csrf_token = None
        for cookie in scraper.cookies:
            if 'xsrf' in cookie.name.lower() or 'csrf' in cookie.name.lower() or 'token' in cookie.name.lower():
                csrf_token = cookie.value
                break
        
        # If no token in cookies, try to extract from HTML
        if not csrf_token:
            token_patterns = [
                r'name="csrf-token" content="([^"]+)"',
                r'name="csrf_token" value="([^"]+)"',
                r'"csrfToken":"([^"]+)"',
                r'"token":"([^"]+)"',
                r'data-csrf="([^"]+)"'
            ]
            for pattern in token_patterns:
                match = re.search(pattern, response.text)
                if match:
                    csrf_token = match.group(1)
                    break
        
        # Add token to headers if found
        if csrf_token:
            headers['x-csrf-token'] = csrf_token
            headers['csrf-token'] = csrf_token
            headers['X-XSRF-TOKEN'] = csrf_token
            scraper.cookies.set('XSRF-TOKEN', csrf_token)
        
        # Make API request
        payload = {"url": terabox_url}
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
            return None, "Rate limited! Try again later"
        elif response.status_code == 403:
            return None, "403 Forbidden - Session may have expired"
        else:
            return None, f"Failed: {response.status_code} - {response.text[:100]}"
            
    except Exception as e:
        return None, f"Error: {str(e)}"

@app.route('/api/terabox', methods=['GET', 'POST'])
def terabox_api():
    """Main API endpoint"""
    if request.method == 'GET':
        url = request.args.get('url')
    else:
        data = request.get_json() or {}
        url = data.get('url')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'Missing url parameter',
            'message': 'Please provide a terabox URL'
        }), 400
    
    if not url.startswith('http'):
        url = 'https://' + url
    
    data, error = get_stream_data(url)
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Failed to get tokens',
            'message': error
        }), 500
    
    file_info = data['list'][0] if data.get('list') else {}
    
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
            }
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
        'service': 'Terabox API',
        'version': '1.0.0',
        'developer': '@KindCoders',
        'description': 'Uses saved session cookies to bypass rate limiting',
        'endpoints': {
            '/api/terabox': {
                'method': 'POST or GET',
                'params': {
                    'url': 'Terabox share URL (required)'
                },
                'example': '/api/terabox?url=https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug'
            },
            '/api/health': {
                'method': 'GET',
                'description': 'Health check'
            }
        }
    }), 200

app = app

if __name__ == '__main__':
    print("=" * 50)
    print("  🎬 TERABOX API")
    print("  👨‍💻 Developer: @KindCoders")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
