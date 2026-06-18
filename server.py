import json
import os
import sys
import time
import urllib.request
import urllib.parse
import re


PORT = int(os.environ.get("PORT", 8000))
current_media = {
    "url": "",
    "timestamp": 0.0,
    "title": "No media playing"
}


def strip_frame_restrictive_meta(html_text):
    # Strip X-Frame-Options meta tags
    html_text = re.sub(
        r'(?i)<meta\s+[^>]*http-equiv=["\']x-frame-options["\'][^>]*>', 
        '', 
        html_text
    )
    # Strip CSP meta tags that restrict framing
    html_text = re.sub(
        r'(?i)<meta\s+[^>]*http-equiv=["\']content-security-policy["\'][^>]*>', 
        '', 
        html_text
    )
    return html_text


def resolve_media_url(url):

    if not url:
        return url
    
    # If the URL is already a direct link to a media file, bypass resolution to save time
    lower_path = urllib.parse.urlparse(url).path.lower()
    if lower_path.endswith(('.mp4', '.webm', '.m3u8', '.mp3', '.ogg', '.ogv', '.mov', '.ts', '.aac', '.wav')):
        return url

    try:
        import yt_dlp
        print(f"Resolving video stream for webpage: {url} using yt-dlp...")
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'skip_download': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            
            direct_url = info.get('url')
            if direct_url:
                print(f"Successfully resolved webpage to direct video URL.")
                return direct_url
    except ImportError:
        print("Warning: yt-dlp is not installed. Using raw URL.")
    except Exception as e:
        print(f"Error resolving URL with yt-dlp: {e}")
    
    return url

# Attempt to load Flask for robust production hosting (Render, Koyeb, PythonAnywhere, etc.)
try:

    from flask import Flask, request, jsonify, send_from_path, Response
    from flask_cors import CORS
    import requests
    
    HAS_FLASK = True
    app = Flask(__name__, static_folder='public')
    CORS(app)

    @app.route('/api/state', methods=['GET'])
    def get_state():
        return jsonify(current_media)

    @app.route('/api/play', methods=['POST'])
    def play_media():
        global current_media
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        # Resolve webpage URL to direct stream URL
        resolved_url = resolve_media_url(url)
        
        current_media = {
            "url": resolved_url,
            "timestamp": time.time(),
            "title": data.get('title', 'Cast Media')
        }
        print(f"Casting URL via Flask: {resolved_url[:80]}...")
        return jsonify({"success": True, "state": current_media})

    @app.route('/api/proxy', methods=['GET'])
    def media_proxy():
        target_url = request.args.get('url')
        if not target_url:
            return "Missing url parameter", 400

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': target_url
            }
            # Forward Range header if present to support video seeking/scrubbing
            range_header = request.headers.get('Range')
            if range_header:
                headers['Range'] = range_header

            # Stream target stream using requests
            r = requests.get(target_url, headers=headers, stream=True, timeout=15)
            
            # Extract header metadata
            excluded_headers = [
                'content-encoding', 'image/x-icon', 'transfer-encoding', 
                'connection', 'x-frame-options', 'content-security-policy'
            ]
            resp_headers = [
                (name, value) for (name, value) in r.raw.headers.items()
                if name.lower() not in excluded_headers
            ]
            
            # Detect HTML pages to inject frame-busting bypass script
            content_type = r.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                html_content = r.text
                html_content = strip_frame_restrictive_meta(html_content)
                script_to_inject = """<script>
                (function() {
                    try {
                        Object.defineProperty(window, 'top', { get: function() { return window.self; } });
                        Object.defineProperty(window, 'parent', { get: function() { return window.self; } });
                    } catch(e) {}
                })();
                </script>"""
                if '<head>' in html_content:
                    html_content = html_content.replace('<head>', '<head>' + script_to_inject, 1)
                elif '<html>' in html_content:
                    html_content = html_content.replace('<html>', '<html>' + script_to_inject, 1)
                else:
                    html_content = script_to_inject + html_content

                response = Response(html_content, status=r.status_code)
                for name, value in resp_headers:
                    response.headers[name] = value
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response

            # Create a streaming response back to the client
            def generate_stream():
                for chunk in r.iter_content(chunk_size=65536):
                    yield chunk

            response = Response(generate_stream(), status=r.status_code)
            for name, value in resp_headers:
                response.headers[name] = value
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
            
        except Exception as e:
            return f"Proxy error: {str(e)}", 500

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_static(path):
        if not path or path == 'index.html':
            return send_from_path('public', 'index.html')
        return send_from_path('public', path)

except ImportError as e:
    # Fallback to standard HTTP library if Flask is not installed (no dependencies required for local run)
    print(f"Warning: Flask imports failed, falling back to built-in HTTP server. Error: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    HAS_FLASK = False
    import http.server
    import socketserver

    class TVCastHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(200)
            self.end_headers()

        def do_GET(self):
            global current_media
            parsed_url = urllib.parse.urlparse(self.path)
            
            if parsed_url.path == '/api/state':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(current_media).encode('utf-8'))
                return
                
            elif parsed_url.path == '/api/proxy':
                query_params = urllib.parse.parse_qs(parsed_url.query)
                target_url = query_params.get('url', [None])[0]
                if not target_url:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Missing url parameter")
                    return

                try:
                    req = urllib.request.Request(target_url)
                    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                    req.add_header('Referer', target_url)
                    
                    range_header = self.headers.get('Range')
                    if range_header:
                        req.add_header('Range', range_header)

                    with urllib.request.urlopen(req, timeout=10) as response:
                        content_type = response.headers.get('Content-Type', '')
                        is_html = 'text/html' in content_type

                        self.send_response(200)
                        for header in ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges']:
                            val = response.headers.get(header)
                            if val:
                                if is_html and header == 'Content-Length':
                                    continue
                                self.send_header(header, val)
                        self.end_headers()
                        
                        if is_html:
                            html_content = response.read().decode('utf-8', errors='ignore')
                            html_content = strip_frame_restrictive_meta(html_content)
                            script_to_inject = """<script>
                            (function() {
                                try {
                                    Object.defineProperty(window, 'top', { get: function() { return window.self; } });
                                    Object.defineProperty(window, 'parent', { get: function() { return window.self; } });
                                } catch(e) {}
                            })();
                            </script>"""
                            if '<head>' in html_content:
                                html_content = html_content.replace('<head>', '<head>' + script_to_inject, 1)
                            elif '<html>' in html_content:
                                html_content = html_content.replace('<html>', '<html>' + script_to_inject, 1)
                            else:
                                html_content = script_to_inject + html_content
                            self.wfile.write(html_content.encode('utf-8'))
                        else:
                            while True:
                                chunk = response.read(65536)
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Proxy error: {str(e)}".encode('utf-8'))
                return

            # Serve static files from public
            if parsed_url.path == '/' or parsed_url.path == '/index.html':
                self.path = '/public/index.html'
            else:
                self.path = '/public' + parsed_url.path

            root = os.path.join(os.getcwd(), 'public')
            rel_path = parsed_url.path.lstrip('/')
            if rel_path == '' or rel_path == 'index.html':
                filepath = os.path.join(root, 'index.html')
            else:
                filepath = os.path.join(root, rel_path)

            if os.path.exists(filepath) and os.path.isfile(filepath):
                self.send_response(200)
                if filepath.endswith('.html'):
                    self.send_header('Content-Type', 'text/html')
                elif filepath.endswith('.css'):
                    self.send_header('Content-Type', 'text/css')
                elif filepath.endswith('.js'):
                    self.send_header('Content-Type', 'application/javascript')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found")

        def do_POST(self):
            global current_media
            parsed_url = urllib.parse.urlparse(self.path)
            
            if parsed_url.path == '/api/play':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                try:
                    data = json.loads(post_data.decode('utf-8'))
                    url = data.get('url')
                    if not url:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "URL is required"}).encode('utf-8'))
                        return
                    
                    # Resolve webpage URL to direct stream URL
                    resolved_url = resolve_media_url(url)
                    
                    current_media = {
                        "url": resolved_url,
                        "timestamp": time.time(),
                        "title": data.get('title', 'Cast Media')
                    }
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "state": current_media}).encode('utf-8'))
                    print(f"Casting URL via Built-in Server: {resolved_url[:80]}...")
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                return
            
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    if HAS_FLASK:
        print(f"Starting Flask TV Cast backend on port {PORT}...")
        app.run(host='0.0.0.0', port=PORT)
    else:
        print(f"Flask not found. Starting fallback built-in TV Cast server on port {PORT}...")
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", PORT), TVCastHandler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nStopping server...")
