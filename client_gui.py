import tkinter as tk
from tkinter import messagebox
import urllib.request
import urllib.parse
import json

class TVCastClient:
    def __init__(self, root):
        self.root = root
        self.root.title("TV Cast Controller")
        self.root.geometry("600x450")
        self.root.configure(bg="#0b0c10")
        
        # Color Palette
        self.bg_color = "#0b0c10"
        self.accent_color = "#66fcf1"
        self.card_color = "#1f2833"
        self.text_color = "#c5c6c7"
        self.white = "#ffffff"
        self.black = "#111111"
        
        self.create_widgets()

    def create_widgets(self):
        # Main Layout Container (using standard tk.Frame for safety)
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(main_frame, text="TV Cast Controller", bg=self.bg_color, fg=self.accent_color, font=("Helvetica", 16, "bold"))
        title_label.pack(anchor="w", pady=(0, 20))

        # Card Panel (Server Settings)
        server_card = tk.Frame(main_frame, bg=self.card_color, padx=15, pady=15)
        server_card.pack(fill=tk.X, pady=(0, 15))
        
        server_title = tk.Label(server_card, text="Server Configuration", bg=self.card_color, fg=self.white, font=("Helvetica", 11, "bold"))
        server_title.pack(anchor="w", pady=(0, 10))
        
        server_ip_label = tk.Label(server_card, text="TV Receiver Host IP / URL:", bg=self.card_color, fg=self.text_color, font=("Helvetica", 10))
        server_ip_label.pack(anchor="w")
        
        self.server_ip_var = tk.StringVar(value="http://localhost:8000")
        self.server_entry = tk.Entry(server_card, textvariable=self.server_ip_var, bg=self.black, fg=self.white, insertbackground=self.white, bd=1, relief="solid", font=("Helvetica", 10))
        self.server_entry.pack(fill=tk.X, pady=(5, 5))

        # Card Panel (Cast Settings)
        cast_card = tk.Frame(main_frame, bg=self.card_color, padx=15, pady=15)
        cast_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        cast_title = tk.Label(cast_card, text="Media Transmission", bg=self.card_color, fg=self.white, font=("Helvetica", 11, "bold"))
        cast_title.pack(anchor="w", pady=(0, 10))
        
        url_label = tk.Label(cast_card, text="Direct Video or Stream URL:", bg=self.card_color, fg=self.text_color, font=("Helvetica", 10))
        url_label.pack(anchor="w")
        
        self.url_var = tk.StringVar(value="")
        self.url_entry = tk.Entry(cast_card, textvariable=self.url_var, bg=self.black, fg=self.white, insertbackground=self.white, bd=1, relief="solid", font=("Helvetica", 10))
        self.url_entry.pack(fill=tk.X, pady=(5, 10))

        # Media Title Option
        title_opt_label = tk.Label(cast_card, text="Media Title (Optional):", bg=self.card_color, fg=self.text_color, font=("Helvetica", 10))
        title_opt_label.pack(anchor="w")
        self.title_var = tk.StringVar(value="Stream Clip")
        self.title_entry = tk.Entry(cast_card, textvariable=self.title_var, bg=self.black, fg=self.white, insertbackground=self.white, bd=1, relief="solid", font=("Helvetica", 10))
        self.title_entry.pack(fill=tk.X, pady=(5, 15))

        # Action Buttons Frame
        btn_frame = tk.Frame(cast_card, bg=self.card_color)
        btn_frame.pack(fill=tk.X)

        self.play_btn = tk.Button(
            btn_frame, 
            text="TRANSMIT & PLAY", 
            bg=self.accent_color, 
            fg=self.bg_color, 
            activebackground="#45a29e", 
            activeforeground=self.bg_color,
            font=("Helvetica", 10, "bold"), 
            bd=0, 
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2"
        )
        self.play_btn.configure(command=self.send_play_command)
        self.play_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_btn = tk.Button(
            btn_frame, 
            text="CLEAR INPUTS", 
            bg="#3a4f50", 
            fg=self.white, 
            activebackground="#45a29e", 
            activeforeground=self.bg_color,
            font=("Helvetica", 10, "bold"), 
            bd=0, 
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2"
        )
        self.clear_btn.configure(command=self.clear_fields)
        self.clear_btn.pack(side=tk.LEFT)

        # Status Bar Frame
        self.status_frame = tk.Frame(main_frame, bg=self.card_color, padx=5, pady=5)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = tk.Label(self.status_frame, text="Status: Connected controller idle.", bg=self.card_color, fg=self.accent_color, font=("Helvetica", 9, "italic"))
        self.status_label.pack(anchor="w")

    def update_status(self, text, is_error=False):
        color = "#ff6b6b" if is_error else self.accent_color
        self.status_label.configure(text=f"Status: {text}", fg=color)

    def clear_fields(self):
        self.url_var.set("")
        self.title_var.set("Stream Clip")
        self.update_status("Fields cleared.")

    def resolve_url_locally(self, url):
        # Quick check for direct media links
        lower_path = urllib.parse.urlparse(url).path.lower()
        if lower_path.endswith(('.mp4', '.webm', '.m3u8', '.mp3', '.ogg', '.ogv', '.mov', '.ts', '.aac', '.wav')):
            return url

        self.update_status("Decoding video link locally (using yt-dlp)...")
        self.root.update_idletasks()
        
        try:
            import yt_dlp
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
                    self.update_status("Decoding successful!")
                    return direct_url
        except ImportError:
            self.update_status("yt-dlp not found on client. Sending raw URL...")
        except Exception as e:
            self.update_status(f"Decoding failed. Sending raw URL...")
            print(f"yt-dlp error: {e}")
        
        return url

    def send_play_command(self):
        server_ip = self.server_ip_var.get().strip()
        media_url = self.url_var.get().strip()
        media_title = self.title_var.get().strip()

        if not server_ip:
            messagebox.showerror("Validation Error", "Please provide a valid TV Receiver Server Address.")
            return

        if not media_url:
            messagebox.showerror("Validation Error", "Please provide a valid Video/Stream URL.")
            return

        # Resolve webpage URL to direct stream URL locally on the client's network
        resolved_url = self.resolve_url_locally(media_url)

        # Prepare payload
        payload = {
            "url": resolved_url,
            "title": media_title
        }
        
        # Always format standard base URL properly
        if not server_ip.startswith("http://") and not server_ip.startswith("https://"):
            server_ip = "http://" + server_ip

        endpoint = f"{server_ip}/api/play"

        
        self.update_status("Transmitting media packet...")
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                if res_data.get('success'):
                    self.update_status(f"Successfully casting stream to TV display!")
                else:
                    self.update_status(f"Server response error: {res_data.get('error')}", is_error=True)
                    
        except Exception as e:
            self.update_status(f"Connection failed: {str(e)}", is_error=True)
            messagebox.showerror("Connection Error", f"Unable to reach the TV Display Server at:\n{endpoint}\n\nMake sure the receiver server is running and the address is correct.")

if __name__ == "__main__":
    root = tk.Tk()
    app = TVCastClient(root)
    root.mainloop()
