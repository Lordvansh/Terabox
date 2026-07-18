from flask import Flask, request, jsonify
import cloudscraper
import requests
import json
import re
import time
from datetime import datetime

app = Flask(__name__)

def get_stream_data(terabox_url):
    """Get stream data using requests with proper headers"""
    base_url = "https://iteraplay.com"
    
    # Headers that mimic a real browser
    headers = {
        'authority': 'iteraplay.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
    }
    
    api_headers = {
        'authority': 'iteraplay.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
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
        # Create a session
        session = requests.Session()
        session.headers.update(headers)
        
        # Step 1: Visit the main page to get cookies
        print("Getting session from iteraplay.com...")
        response = session.get(base_url, timeout=15)
        print(f"Main page status: {response.status_code}")
        
        # Get cookies from the session
        cookies = session.cookies.get_dict()
        print(f"Cookies obtained: {list(cookies.keys())}")
        
        # Step 2: Now use cloudscraper with the cookies we got
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True,
                'desktop': False
            },
            interpreter='python'
        )
        
        # Set the cookies we got from requests session
        for name, value in cookies.items():
            scraper.cookies.set(name, value)
        
        # Also set the cookies directly in headers
        cookie_string = '; '.join([f'{k}={v}' for k, v in cookies.items()])
        api_headers['Cookie'] = cookie_string
        
        # Step 3: Make the API request
        payload = {"url": terabox_url}
        print(f"Making API request...")
        
        response = scraper.post(
            f"{base_url}/api/stream",
            headers=api_headers,
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
        'description': 'Gets fresh session for each request',
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
