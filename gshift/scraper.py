import os
import requests
import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from urllib.parse import urlparse

class FastDLDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("scraper v0.16")
        
        # Center the window on screen
        self.center_window(550, 250)
        
        # Apply dark theme
        self.set_dark_theme()
        
        self.setup_ui()
        
    def center_window(self, width, height):
        """Center the window on the screen"""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def set_dark_theme(self):
        self.root.configure(bg='#1e1e1e')
        
        # Define dark theme colors
        self.bg_color = '#1e1e1e'
        self.fg_color = '#ffffff'
        self.entry_bg = '#252525'
        self.entry_fg = '#ffffff'
        self.button_bg = '#3c3c3c'
        self.button_fg = '#ffffff'
        self.button_active = '#4a4a4a'
        self.progress_color = '#007acc'
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles
        style.configure('.', background=self.bg_color, foreground=self.fg_color)
        style.configure('TFrame', background=self.bg_color)
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        style.configure('TEntry', fieldbackground=self.entry_bg, foreground=self.entry_fg, 
                       insertcolor=self.fg_color)
        style.configure('TButton', background=self.button_bg, foreground=self.button_fg, 
                        bordercolor=self.button_bg, lightcolor=self.button_bg, darkcolor=self.button_bg)
        style.map('TButton', 
                 background=[('active', self.button_active), ('disabled', self.button_bg)],
                 foreground=[('active', self.button_fg), ('disabled', self.fg_color)])
        style.configure('TProgressbar', background=self.progress_color, troughcolor=self.entry_bg)
        
    def setup_ui(self):
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL input section
        ttk.Label(self.main_frame, text="Enter Download URL:").pack(anchor=tk.W, pady=(0, 5))
        
        self.url_entry = ttk.Entry(self.main_frame, width=60)
        self.url_entry.pack(fill=tk.X, pady=(0, 10))
        self.url_entry.insert(0, "https://dl.game-relay.cloud/6953190d-c02b-4536-8dfd-7658840ef9eb/maps/gsh_inferno.bsp.bz2")
        
        # Download info section
        self.url_display = ttk.Label(self.main_frame, text="", wraplength=400)
        self.url_display.pack(fill=tk.X, pady=(0, 10))
        
        self.progress = ttk.Progressbar(self.main_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)
        
        self.status = ttk.Label(self.main_frame, text="Ready to download")
        self.status.pack(fill=tk.X)
        
        # Buttons
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(pady=10)
        
        self.download_btn = ttk.Button(btn_frame, text="Download", command=self.start_download)
        self.download_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.cancel_download, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        
        self.downloading = False
        self.cancel_requested = False
    
    def validate_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def start_download(self):
        url = self.url_entry.get().strip()
        
        if not self.validate_url(url):
            messagebox.showerror("Invalid URL", "Please enter a valid URL starting with http:// or https://")
            return
            
        self.fastdl_url = url
        self.url_display.config(text=f"Downloading: {url}")
        
        self.downloading = True
        self.cancel_requested = False
        self.download_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        download_thread = Thread(target=self.download_file)
        download_thread.start()
        
        self.root.after(100, self.check_progress)
    
    def cancel_download(self):
        self.cancel_requested = True
        self.status.config(text="Cancelling download...")
    
    def download_file(self):
        try:
            parsed_url = urlparse(self.fastdl_url)
            filename = os.path.basename(parsed_url.path)
            
            if not filename:
                filename = "downloaded_file"
                
            save_path = os.path.join(os.getcwd(), filename)
            
            self.update_status(f"Downloading {filename}...")
            
            with requests.get(self.fastdl_url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                
                with open(save_path, 'wb') as f:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=8192):
                        if self.cancel_requested:
                            self.update_status("Download cancelled")
                            f.close()
                            if os.path.exists(save_path):
                                os.remove(save_path)
                            return
                            
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress = int((downloaded / total_size) * 100) if total_size > 0 else 0
                            self.update_progress(progress)
                
            if not self.cancel_requested:
                self.update_status(f"Download complete! Saved to {save_path}")
                messagebox.showinfo("Success", f"File downloaded successfully to:\n{save_path}")
                
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
            messagebox.showerror("Error", f"Failed to download file:\n{str(e)}")
        finally:
            self.downloading = False
            self.root.after(100, self.reset_ui)
    
    def update_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))
    
    def update_progress(self, value):
        self.root.after(0, lambda: self.progress.config(value=value))
    
    def check_progress(self):
        if self.downloading:
            self.root.after(100, self.check_progress)
    
    def reset_ui(self):
        self.download_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        self.progress.config(value=0)

if __name__ == "__main__":
    root = tk.Tk()
    app = FastDLDownloader(root)
    root.mainloop()