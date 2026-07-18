from flask import Flask, request, jsonify
import cloudscraper
import requests
import json
import re
import time
from datetime import datetime

app = Flask(__name__)

def get_stream_data(terabox_url):
    """Get stream data by first getting fresh session"""
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
        # Create scraper with browser emulation
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True,
                'desktop': False
            },
            interpreter='python'
        )
        
        # Step 1: Visit the main page to get fresh session
        print("Getting fresh session from iteraplay.com...")
        response = scraper.get(base_url, timeout=15)
        print(f"Main page status: {response.status_code}")
        
        # Step 2: Get CSRF token from cookies
        csrf_token = None
        for cookie in scraper.cookies:
            if 'xsrf' in cookie.name.lower() or 'csrf' in cookie.name.lower():
                csrf_token = cookie.value
                print(f"Found CSRF token: {csrf_token[:20]}...")
                break
        
        # Step 3: If no token in cookies, extract from HTML
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
                    print(f"Found CSRF token in HTML: {csrf_token[:20]}...")
                    break
        
        # Step 4: Add token to headers if found
        if csrf_token:
            headers['x-csrf-token'] = csrf_token
            headers['csrf-token'] = csrf_token
            headers['X-XSRF-TOKEN'] = csrf_token
            scraper.cookies.set('XSRF-TOKEN', csrf_token)
        
        # Step 5: Also try to get __secure_token from cookies
        secure_token = None
        for cookie in scraper.cookies:
            if '__secure_token' in cookie.name:
                secure_token = cookie.value
                print(f"Found secure token")
                break
        
        # Step 6: Make the API request with fresh cookies
        payload = {"url": terabox_url}
        print(f"Making API request for: {terabox_url}")
        
        response = scraper.post(
            f"{base_url}/api/stream",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"API Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("Stream data received successfully!")
                return data, None
            else:
                return None, f"API error: {data.get('error', 'Unknown')}"
        elif response.status_code == 429:
            return None, "Rate limited! Try again later"
        elif response.status_code == 403:
            return None, "403 Forbidden - Try again in a few minutes"
        else:
            return None, f"Failed: {response.status_code} - {response.text[:100]}"
            
    except Exception as e:
        return None, f"Error: {str(e)}"

@app.route('/api/terabox', methods=['GET', 'POST'])
def terabox_api():
    """Main API endpoint - Gets fresh session each time"""
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
    
    # Get fresh session and data
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
        'message': 'Terabox API is running - Gets fresh session each request',
        'developer': '@KindCoders'
    }), 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'Terabox API - Fresh Session',
        'version': '1.0.0',
        'developer': '@KindCoders',
        'description': 'Gets fresh session from iteraplay.com for each request',
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
        },
        'note': 'No cookies needed - gets fresh session automatically'
    }), 200

app = app

if __name__ == '__main__':
    print("=" * 50)
    print("  🎬 TERABOX API - Fresh Session")
    print("  👨‍💻 Developer: @KindCoders")
    print("=" * 50)
    print("\n📍 Endpoints:")
    print("   GET/POST /api/terabox?url=TERABOX_URL")
    print("   GET /api/health")
    print("   GET / - Documentation")
    print("\n💡 Gets fresh session automatically - no cookies needed")
    print("🔧 Starting server...")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
