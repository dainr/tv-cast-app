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
media_queue = []


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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__, static_folder=os.path.join(base_dir, 'public'))
    CORS(app)

    @app.route('/api/state', methods=['GET'])
    def get_state():
        state = current_media.copy()
        state["queue"] = media_queue
        return jsonify(state)

    @app.route('/api/play', methods=['POST'])
    def play_media():
        global current_media, media_queue
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        # Resolve webpage URL to direct stream URL
        resolved_url = resolve_media_url(url)
        
        item = {
            "id": int(time.time() * 1000),
            "url": resolved_url,
            "title": data.get('title', 'Cast Media'),
            "timestamp": time.time()
        }
        
        force_play = data.get('force', False)
        
        if not current_media.get("url") or force_play:
            current_media = item
            print(f"Casting URL immediately via Flask: {resolved_url[:80]}...")
        else:
            if len(media_queue) >= 15:
                return jsonify({"error": "Queue is full (max 15 items)"}), 400
            media_queue.append(item)
            print(f"Added URL to queue via Flask: {resolved_url[:80]}...")
            
        state = current_media.copy()
        state["queue"] = media_queue
        return jsonify({"success": True, "state": state})

    @app.route('/api/next', methods=['POST'])
    def play_next():
        global current_media, media_queue
        if media_queue:
            current_media = media_queue.pop(0)
            current_media["timestamp"] = time.time()
            print(f"Playing next video from queue: {current_media['title']}")
        else:
            current_media = {
                "url": "",
                "timestamp": time.time(),
                "title": "No media playing"
            }
            print("Queue is empty, stopping playback.")
            
        state = current_media.copy()
        state["queue"] = media_queue
        return jsonify({"success": True, "state": state})

    @app.route('/api/queue/delete', methods=['POST'])
    def queue_delete():
        global media_queue
        data = request.get_json() or {}
        item_id = data.get('id')
        if item_id is None:
            return jsonify({"error": "Item ID is required"}), 400
            
        media_queue = [item for item in media_queue if item["id"] != int(item_id)]
        print(f"Deleted item {item_id} from queue.")
        
        state = current_media.copy()
        state["queue"] = media_queue
        return jsonify({"success": True, "state": state})

    @app.route('/api/queue/reorder', methods=['POST'])
    def queue_reorder():
        global media_queue
        data = request.get_json() or {}
        item_ids = data.get('ids')
        if not isinstance(item_ids, list):
            return jsonify({"error": "List of IDs is required"}), 400
            
        id_to_item = {item["id"]: item for item in media_queue}
        new_queue = []
        for iid in item_ids:
            try:
                iid_int = int(iid)
                if iid_int in id_to_item:
                    new_queue.append(id_to_item[iid_int])
            except ValueError:
                continue
                
        for item in media_queue:
            if item["id"] not in [x["id"] for x in new_queue]:
                new_queue.append(item)
                
        media_queue = new_queue[:15]
        print("Reordered queue.")
        
        state = current_media.copy()
        state["queue"] = media_queue
        return jsonify({"success": True, "state": state})

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
                
                # Base tag injection to resolve relative references correctly
                parsed_target = urllib.parse.urlparse(target_url)
                base_url = f"{parsed_target.scheme}://{parsed_target.netloc}{parsed_target.path}"
                base_tag = f'<base href="{base_url}">'
                
                script_to_inject = """<script>
                (function() {
                    try {
                        Object.defineProperty(window, 'top', { get: function() { return window.self; } });
                        Object.defineProperty(window, 'parent', { get: function() { return window.self; } });
                    } catch(e) {}
                })();
                </script>"""
                if '<head>' in html_content:
                    html_content = html_content.replace('<head>', '<head>' + base_tag + script_to_inject, 1)
                elif '<html>' in html_content:
                    html_content = html_content.replace('<html>', '<html>' + base_tag + script_to_inject, 1)
                else:
                    html_content = base_tag + script_to_inject + html_content

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
        base_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(base_dir, 'public')
        
        # Normalize path and handle aliases/redirects
        clean_path = path.lower().strip('/')
        if not clean_path or clean_path in ['display', 'receiver', 'index.html']:
            return send_from_path(static_dir, 'index.html')
        elif clean_path in ['controller', 'controller.html']:
            return send_from_path(static_dir, 'controller.html')
            
        return send_from_path(static_dir, path)

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
                            
                            # Base tag injection to resolve relative references correctly
                            parsed_target = urllib.parse.urlparse(target_url)
                            base_url = f"{parsed_target.scheme}://{parsed_target.netloc}{parsed_target.path}"
                            base_tag = f'<base href="{base_url}">'
                            
                            script_to_inject = """<script>
                            (function() {
                                try {
                                    Object.defineProperty(window, 'top', { get: function() { return window.self; } });
                                    Object.defineProperty(window, 'parent', { get: function() { return window.self; } });
                                } catch(e) {}
                            })();
                            </script>"""
                            if '<head>' in html_content:
                                html_content = html_content.replace('<head>', '<head>' + base_tag + script_to_inject, 1)
                            elif '<html>' in html_content:
                                html_content = html_content.replace('<html>', '<html>' + base_tag + script_to_inject, 1)
                            else:
                                html_content = base_tag + script_to_inject + html_content
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

            # Serve static files from public relative to script path
            base_dir = os.path.dirname(os.path.abspath(__file__))
            root = os.path.join(base_dir, 'public')
            
            clean_path = parsed_url.path.lower().strip('/')
            if not clean_path or clean_path in ['display', 'receiver', 'index.html']:
                filepath = os.path.join(root, 'index.html')
            elif clean_path in ['controller', 'controller.html']:
                filepath = os.path.join(root, 'controller.html')
            else:
                filepath = os.path.join(root, parsed_url.path.lstrip('/'))

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
            global current_media, media_queue
            parsed_url = urllib.parse.urlparse(self.path)
            
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b""
            
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
            except Exception:
                data = {}

            if parsed_url.path == '/api/play':
                url = data.get('url')
                if not url:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "URL is required"}).encode('utf-8'))
                    return
                
                resolved_url = resolve_media_url(url)
                item = {
                    "id": int(time.time() * 1000),
                    "url": resolved_url,
                    "title": data.get('title', 'Cast Media'),
                    "timestamp": time.time()
                }
                
                force_play = data.get('force', False)
                if not current_media.get("url") or force_play:
                    current_media = item
                else:
                    if len(media_queue) >= 15:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "Queue is full"}).encode('utf-8'))
                        return
                    media_queue.append(item)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                state = current_media.copy()
                state["queue"] = media_queue
                self.wfile.write(json.dumps({"success": True, "state": state}).encode('utf-8'))
                print(f"Casting URL via Built-in Server: {resolved_url[:80]}...")
                return
                
            elif parsed_url.path == '/api/next':
                if media_queue:
                    current_media = media_queue.pop(0)
                    current_media["timestamp"] = time.time()
                else:
                    current_media = {
                        "url": "",
                        "timestamp": time.time(),
                        "title": "No media playing"
                    }
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                state = current_media.copy()
                state["queue"] = media_queue
                self.wfile.write(json.dumps({"success": True, "state": state}).encode('utf-8'))
                return

            elif parsed_url.path == '/api/queue/delete':
                item_id = data.get('id')
                if item_id is not None:
                    media_queue = [item for item in media_queue if item["id"] != int(item_id)]
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                state = current_media.copy()
                state["queue"] = media_queue
                self.wfile.write(json.dumps({"success": True, "state": state}).encode('utf-8'))
                return

            elif parsed_url.path == '/api/queue/reorder':
                item_ids = data.get('ids', [])
                id_to_item = {item["id"]: item for item in media_queue}
                new_queue = []
                for iid in item_ids:
                    try:
                        iid_int = int(iid)
                        if iid_int in id_to_item:
                            new_queue.append(id_to_item[iid_int])
                    except ValueError:
                        continue
                for item in media_queue:
                    if item["id"] not in [x["id"] for x in new_queue]:
                        new_queue.append(item)
                media_queue = new_queue[:15]
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                state = current_media.copy()
                state["queue"] = media_queue
                self.wfile.write(json.dumps({"success": True, "state": state}).encode('utf-8'))
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
