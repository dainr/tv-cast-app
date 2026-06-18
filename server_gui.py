import tkinter as tk
import threading
import socket
import os
import sys

# Import the server code handler
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from server import TVCastHandler, PORT
import socketserver

class TVCastServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TV Cast Server Manager")
        self.root.geometry("500x350")
        self.root.configure(bg="#0b0c10")
        self.root.resizable(False, False)

        # Theme Colors
        self.bg_color = "#0b0c10"
        self.accent_color = "#66fcf1"
        self.card_color = "#1f2833"
        self.text_color = "#c5c6c7"
        self.white = "#ffffff"

        self.httpd = None
        self.server_thread = None
        
        self.create_widgets()
        self.start_server()

        # Handle window close event to shutdown server
        self.root.protocol("WM_DELETE_WINDOW", self.stop_server_and_exit)

    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(main_frame, text="TV Cast Server Control Panel", bg=self.bg_color, fg=self.accent_color, font=("Helvetica", 16, "bold"))
        title_label.pack(anchor="w", pady=(0, 20))

        # Status Panel
        status_card = tk.Frame(main_frame, bg=self.card_color, padx=20, pady=20)
        status_card.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.status_label = tk.Label(status_card, text="Status: Starting Server...", bg=self.card_color, fg=self.accent_color, font=("Helvetica", 11, "bold"))
        self.status_label.pack(anchor="w", pady=(0, 10))

        # Show local IPs
        self.ip_info_label = tk.Label(status_card, text="Retrieving local network addresses...", bg=self.card_color, fg=self.text_color, justify=tk.LEFT, font=("Helvetica", 10))
        self.ip_info_label.pack(anchor="w", pady=(5, 15))

        # Instruction
        inst_label = tk.Label(status_card, text="Enter one of the addresses above into your controller client.", bg=self.card_color, fg=self.text_color, font=("Helvetica", 9, "italic"))
        inst_label.pack(anchor="w")

        # Action Buttons
        btn_frame = tk.Frame(main_frame, bg=self.bg_color)
        btn_frame.pack(fill=tk.X)

        self.stop_btn = tk.Button(
            btn_frame, 
            text="STOP SERVER & EXIT", 
            bg="#ff6b6b", 
            fg=self.bg_color, 
            activebackground="#ff5252", 
            activeforeground=self.bg_color,
            font=("Helvetica", 10, "bold"), 
            bd=0, 
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2"
        )
        self.stop_btn.configure(command=self.stop_server_and_exit)
        self.stop_btn.pack(side=tk.RIGHT)

    def get_local_ips(self):
        ips = ["http://localhost:" + str(PORT)]
        try:
            # Get IP addresses from network interfaces
            hostname = socket.gethostname()
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Doesn't need to connect to anything, just resolves interface
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            ips.append(f"http://{local_ip}:{PORT}")
        except Exception:
            pass
        return ips

    def start_server(self):
        socketserver.TCPServer.allow_reuse_address = True
        try:
            self.httpd = socketserver.TCPServer(("", PORT), TVCastHandler)
            
            # Start in a daemon thread
            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()

            ips = self.get_local_ips()
            ip_text = "\n".join([f"• {ip}" for ip in ips])
            self.status_label.configure(text="Status: LIVE & STREAMING", fg=self.accent_color)
            self.ip_info_label.configure(text=f"Receiver URL(s):\n{ip_text}")
        except Exception as e:
            self.status_label.configure(text="Status: FAILED TO START", fg="#ff6b6b")
            self.ip_info_label.configure(text=f"Error bind/start: {str(e)}")

    def stop_server_and_exit(self):
        if self.httpd:
            print("Shutting down TV Cast HTTP server...")
            self.httpd.shutdown()
            self.httpd.server_close()
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = TVCastServerGUI(root)
    root.mainloop()
