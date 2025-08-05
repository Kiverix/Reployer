import socket
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from collections import deque
import time
import threading
import csv
from datetime import datetime, timezone
import os
import subprocess
import websockets
import asyncio
import json
import webbrowser

# Constants
CGE7_193 = ('79.127.217.197', 22912)
TIMEOUT = 5
CSV_FILENAME = "player_log.csv"
ORDINANCE_START = datetime(2025, 4, 25, 0, 0, 0, tzinfo=timezone.utc)
MAX_DATA_POINTS = 60
UPDATE_INTERVAL = 5
VIEWS_WEBSOCKET_URL = "wss://view.gaq9.com"

# Sound and server query modules
try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

try:
    from a2s.info import info as a2s_info
    from a2s.players import players as a2s_players
    A2S_AVAILABLE = True
except ImportError:
    A2S_AVAILABLE = False

# Main application class
class ServerMonitorApp:
    def play_hover_sound(self, event=None):
        if not PYGAME_AVAILABLE:
            return
        try:
            sound_path = os.path.join("resources", "hover.wav")
            if os.path.exists(sound_path):
                sound = pygame.mixer.Sound(sound_path)
                sound.set_volume(0.25)
                sound.play()
        except Exception:
            pass
    def get_server_info(self):
        # Query server info
        if not A2S_AVAILABLE:
            return None, 0, []
        try:
            info = a2s_info(CGE7_193, timeout=TIMEOUT)
            players = a2s_players(CGE7_193, timeout=TIMEOUT)
            return info, len(players), players
        except Exception:
            return None, 0, []

    def start_monitoring(self):
        # Start server monitoring thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def __init__(self, root):
        self.root = root
        self.root.title("Reployer v2.5 - Made by Kiverix 'the clown'")
        self.root.geometry("1500x1000")

        self.create_custom_title_bar()  # Custom title bar

        # Data structures
        self.timestamps = deque(maxlen=MAX_DATA_POINTS)
        self.player_counts = deque(maxlen=MAX_DATA_POINTS)
        self.player_list = []
        self.server_info = None
        self.current_map = None

        # Map cycle variables
        self.last_map_name = None
        self.map_sound_played = {}
        self.sound_played_minute = None
        self.last_time_sound_minute = None

        # Views monitoring
        self.current_views = 0
        self.last_view_id = None
        self.websocket_running = True

        self.setup_theme()  # Theme
        self.init_csv()     # CSV file
        self.load_existing_data()  # Load data
        self.create_widgets()      # GUI widgets

        # Start background tasks
        self.running = True
        self.start_monitoring()
        self.start_websocket_monitor()
        self.test_connection()
        self.play_sound("open.wav")
        self.update_map_display()

    def create_custom_title_bar(self):
        # Custom title bar with close and minimize buttons
        self.title_bar = tk.Frame(self.root, bg="#232323", relief=tk.RAISED, bd=0, height=32)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.bind('<Button-1>', self.start_move)
        self.title_bar.bind('<B1-Motion>', self.on_move)

        # App title
        title_label = tk.Label(self.title_bar, text="Reployer v2.5 - With Love, by Kiverix", bg="#232323", fg="#4fc3f7", font=("Arial", 12, "bold"))
        title_label.pack(side=tk.LEFT, padx=10)

        # Close button (rightmost)
        close_btn = tk.Button(
            self.title_bar, text="✕", bg="#232323", fg="#ff5555", font=("Arial", 12, "bold"), bd=0,
            relief=tk.FLAT, activebackground="#3d3d3d", activeforeground="#ff5555", command=self.on_close, cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT, padx=(0, 10))
        close_btn.bind('<Enter>', self.play_hover_sound)

        # Minimize button (to the left of close)
        minimize_btn = tk.Button(
            self.title_bar, text="━", bg="#232323", fg="#4fc3f7", font=("Arial", 12, "bold"), bd=0,
            relief=tk.FLAT, activebackground="#3d3d3d", activeforeground="#4fc3f7", command=self.minimize_window, cursor="hand2"
        )
        minimize_btn.pack(side=tk.RIGHT, padx=(0, 0))
        minimize_btn.bind('<Enter>', self.play_hover_sound)

    def minimize_window(self):
        # Minimize main window
        self.root.update_idletasks()
        self.root.iconify()

    def start_move(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def on_move(self, event):
        x = self.root.winfo_x() + event.x - self._drag_start_x
        y = self.root.winfo_y() + event.y - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def setup_theme(self):
        # Configure dark theme
        self.theme = {
            'bg': "#2d2d2d", 'fg': "#ffffff", 'frame': "#3d3d3d",
            'graph_bg': "#1e1e1e", 'graph_fg': "#ffffff", 'graph_grid': "#4d4d4d",
            'plot': "#4fc3f7", 'listbox_bg': "#3d3d3d", 'listbox_fg': "#ffffff",
            'select_bg': "#4fc3f7", 'select_fg': "#ffffff",
            'status_online': "green", 'status_restart1': "blue", 'status_restart2': "gold",
            'button_bg': "#3d3d3d", 'button_fg': "#ffffff",
            'views_bg': "#3d3d3d", 'views_fg': "#4fc3f7"
        }
        self.apply_theme()

    def apply_theme(self):
        # Apply theme to widgets
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background=self.theme['bg'], foreground=self.theme['fg'])
        style.configure('TFrame', background=self.theme['bg'])
        style.configure('TLabel', background=self.theme['bg'], foreground=self.theme['fg'])
        style.configure('TLabelframe', background=self.theme['bg'], foreground=self.theme['fg'])
        style.configure('TLabelframe.Label', background=self.theme['bg'], foreground=self.theme['fg'])
        style.configure('TButton', background=self.theme['button_bg'], foreground=self.theme['button_fg'])
        
        self.root.configure(bg=self.theme['bg'])
        
        if hasattr(self, 'fig'):
            self.update_graph_theme()
        if hasattr(self, 'player_listbox'):
            self.player_listbox.config(
                bg=self.theme['listbox_bg'], fg=self.theme['listbox_fg'],
                selectbackground=self.theme['select_bg'], selectforeground=self.theme['select_fg']
            )
        if hasattr(self, 'views_label'):
            self.views_label.config(bg=self.theme['views_bg'], fg=self.theme['views_fg'])

    def create_widgets(self):
        # Create all GUI widgets
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_server_info_frame(left_frame)
        self.create_views_frame(left_frame)
        self.create_player_list_frame(left_frame)
        self.create_graph_frame(right_frame)
        self.create_action_buttons()
        self.create_status_bars()
        
        debug_frame = ttk.Frame(self.root)
        debug_frame.pack(fill=tk.X, padx=10, pady=5)
        ip_text = f"Server: {CGE7_193[0]}:{CGE7_193[1]}"
        self.ip_label = tk.Label(debug_frame, text=ip_text, fg="#4fc3f7", cursor="hand2", bg=self.theme['bg'])
        self.ip_label.pack(side=tk.RIGHT)
        def copy_ip_to_clipboard(event=None):
            self.root.clipboard_clear()
            self.root.clipboard_append(f"{CGE7_193[0]}:{CGE7_193[1]}")
            self.status_var.set("Server IP copied to clipboard!")
            self.play_sound("information.wav")
        self.ip_label.bind("<Button-1>", copy_ip_to_clipboard)

        self.gaq9_label = tk.Label(debug_frame, text="Go to gaq9.com", fg="purple", bg=self.theme['bg'], font=("Arial", 9), cursor="hand2")
        self.gaq9_label.pack(side=tk.LEFT, padx=(0, 10))
        def open_gaq9(event=None):
            webbrowser.open("https://gaq9.com")
            self.play_sound("information.wav")
        self.gaq9_label.bind("<Button-1>", open_gaq9)

        self.am_label = tk.Label(debug_frame, text="Join Anomalous Materials on Discord", fg="beige", bg=self.theme['bg'], font=("Arial", 9), cursor="hand2")
        self.am_label.pack(side=tk.LEFT)
        def open_am_discord(event=None):
            webbrowser.open("https://discord.gg/anomidae")
            self.play_sound("information.wav")
        self.am_label.bind("<Button-1>", open_am_discord)

        self.youtube_label = tk.Label(debug_frame, text="Subscribe to my Youtube", fg="red", bg=self.theme['bg'], font=("Arial", 9), cursor="hand2")
        self.youtube_label.pack(side=tk.LEFT, padx=(10, 0))
        def open_youtube(event=None):
            webbrowser.open("https://www.youtube.com/@kiverix")
            self.play_sound("information.wav")
        self.youtube_label.bind("<Button-1>", open_youtube)

    def create_views_frame(self, parent):
        # Views counter frame
        views_frame = ttk.LabelFrame(parent, text="CGE7-193 Diet View Monitor (no new views since July 24th sadly, it's joever)", padding=10)
        views_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.views_label = tk.Label(
            views_frame,
            text="Current View ID: Waiting for new view...",
            font=("Arial", 10, "bold"),
            bg=self.theme['views_bg'],
            fg=self.theme['views_fg']
        )
        self.views_label.pack(anchor=tk.W)
        
        self.last_view_time_label = tk.Label(
            views_frame,
            text="Last View Time: --",
            font=("Arial", 9)
        )
        self.last_view_time_label.pack(anchor=tk.W)
        
        self.views_status = ttk.Label(views_frame, text="Status: Connecting to WebSocket...")
        self.views_status.pack(anchor=tk.W)

    def create_server_info_frame(self, parent):
        # Server info frame
        info_frame = ttk.LabelFrame(parent, text="CGE7-193 Information", padding=10)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.server_name_label = ttk.Label(info_frame, text="Server Name: Testing connection...")
        self.server_name_label.pack(anchor=tk.W)
        
        self.server_map_label = ttk.Label(info_frame, text="Current Map: Unknown")
        self.server_map_label.pack(anchor=tk.W)
        
        self.player_count_label = ttk.Label(info_frame, text="Players: ?/?")
        self.player_count_label.pack(anchor=tk.W)
        
        ttk.Separator(info_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        self.current_map_cycle_label = ttk.Label(
            info_frame, 
            text="Current Map Cycle: Loading...",
            font=("Arial", 10, "bold")
        )
        self.current_map_cycle_label.pack(anchor=tk.W)
        
        self.adjacent_maps_label = ttk.Label(
            info_frame,
            text="Previous: Loading... | Next: Loading...",
            font=("Arial", 9)
        )
        self.adjacent_maps_label.pack(anchor=tk.W)
        
        self.countdown_label = ttk.Label(
            info_frame,
            text="Next cycle in: --:--",
            font=("Arial", 9, "bold")
        )
        self.countdown_label.pack(anchor=tk.W)
        
        self.time_label = ttk.Label(
            info_frame,
            text="UTC: --:--:-- | Local: --:--:--",
            font=("Arial", 9)
        )
        self.time_label.pack(anchor=tk.W)
        
        self.restart_status_label = ttk.Label(
            info_frame,
            text="Server Status: ONLINE",
            font=("Arial", 10, "bold"),
            foreground=self.theme['status_online']
        )
        self.restart_status_label.pack(anchor=tk.W)

    def get_map_based_on_utc_hour(self, hour=None):
        # Map schedule by UTC hour
        if hour is None:
            hour = datetime.utcnow().hour

        map_schedule = {
            0: "askask", 1: "ask", 2: "ask", 3: "askask",
            4: "ask", 5: "dustbowl", 6: "askask", 7: "ask",
            8: "ask", 9: "askask", 10: "ask", 11: "dustbowl",
            12: "askask", 13: "ask", 14: "ask", 15: "askask",
            16: "ask", 17: "dustbowl", 18: "askask", 19: "ask",
            20: "dustbowl", 21: "askask", 22: "ask", 23: "dustbowl"
        }
        return map_schedule.get(hour, "unknown")
    
    def get_adjacent_maps(self):
        # Previous and next map
        current_hour = datetime.utcnow().hour
        current_minute = datetime.utcnow().minute
        current_second = datetime.utcnow().second
        
        prev_hour = current_hour - 1 if current_hour > 0 else 23
        prev_map = self.get_map_based_on_utc_hour(prev_hour)
        
        next_hour = current_hour + 1 if current_hour < 23 else 0
        next_map = self.get_map_based_on_utc_hour(next_hour)
        
        seconds_remaining = (59 - current_second) % 60
        minutes_remaining = (59 - current_minute) % 60
        
        return prev_map, next_map, minutes_remaining, seconds_remaining


    def update_map_display(self):
        # Update map and time display
        utc_now = datetime.utcnow()
        local_now = datetime.now()

        utc_time = utc_now.strftime("%H:%M:%S")
        local_time = local_now.strftime("%H:%M:%S")

        current_map = self.get_map_based_on_utc_hour()
        prev_map, next_map, mins_left, secs_left = self.get_adjacent_maps()

        # Determine restart status
        current_minute = utc_now.minute
        current_second = utc_now.second

        restart_type = None
        if current_minute == 59 and current_second >= 10:
            restart_status = "FIRST RESTART"
            status_color = self.theme['status_restart1']
            restart_type = "FIRST"
        elif current_minute == 1 and current_second <= 30:
            restart_status = "SECOND RESTART"
            status_color = self.theme['status_restart2']
            restart_type = "SECOND"
        else:
            restart_status = "ONLINE"
            status_color = self.theme['status_online']
            restart_type = None

        # Play information.wav only once per restart type
        if not hasattr(self, '_last_restart_type'):
            self._last_restart_type = None
        if restart_type and self._last_restart_type != restart_type:
            self.play_sound("information.wav")
            self._last_restart_type = restart_type
        elif restart_type is None:
            self._last_restart_type = None

        # Update labels
        self.time_label.config(text=f"UTC: {utc_time} | Local: {local_time}")
        self.current_map_cycle_label.config(text=f"Current Map Cycle: {current_map}")
        self.adjacent_maps_label.config(text=f"Previous: {prev_map} | Next: {next_map}")
        self.countdown_label.config(text=f"Next cycle in: {mins_left:02d}m {secs_left:02d}s")
        self.restart_status_label.config(text=f"Server Status: {restart_status}", foreground=status_color)

        # Play sounds
        self.handle_time_warning_sounds(utc_now)

        if utc_now.minute == 59 and utc_now.second == 0:
            if self.sound_played_minute != utc_now.hour:
                self.play_sound('new_cycle.wav')
                self.sound_played_minute = utc_now.hour
        elif utc_now.minute != 59:
            self.sound_played_minute = None

        self.root.after(50, self.update_map_display)

    def handle_time_warning_sounds(self, utc_now):
        # Play warning sounds at specific times
        current_minute = utc_now.minute
        current_second = utc_now.second
        
        if current_second == 0:
            minute_sounds = {30: 'thirty.wav', 45: 'fifteen.wav', 55: 'five.wav'}
            sound_key = minute_sounds.get(current_minute)
            if sound_key and self.last_time_sound_minute != current_minute:
                self.play_sound(sound_key)
                self.last_time_sound_minute = current_minute
            elif current_minute not in minute_sounds:
                self.last_time_sound_minute = None

    def create_player_list_frame(self, parent):
        # Player list frame
        player_frame = ttk.LabelFrame(parent, text="Online Players", padding=10)
        player_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.player_listbox = tk.Listbox(
            player_frame, 
            bg=self.theme['listbox_bg'], 
            fg=self.theme['listbox_fg'],
            selectbackground=self.theme['select_bg'], 
            selectforeground=self.theme['select_fg']
        )
        self.player_listbox.pack(fill=tk.BOTH, expand=True)

    def create_graph_frame(self, parent):
        # Player count graph
        graph_frame = ttk.LabelFrame(parent, text="Player Count History", padding=10)
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.fig = Figure(figsize=(8, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.update_graph_theme()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_graph_theme(self):
        # Update graph colors
        self.fig.set_facecolor(self.theme['graph_bg'])
        self.ax.set_facecolor(self.theme['graph_bg'])
        self.ax.tick_params(colors=self.theme['graph_fg'])
        self.ax.xaxis.label.set_color(self.theme['graph_fg'])
        self.ax.yaxis.label.set_color(self.theme['graph_fg'])
        self.ax.title.set_color(self.theme['graph_fg'])
        self.ax.grid(True, color=self.theme['graph_grid'])

    def create_action_buttons(self):
        # Action buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cge_button = ttk.Button(
            button_frame,
            text="Connect to CGE7-193",
            command=self.connect_to_cge,
            state=tk.DISABLED
        )
        self.cge_button.pack(side=tk.LEFT, padx=5)
        self.cge_button.bind('<Enter>', self.play_hover_sound)

        self.sourceTV_button = ttk.Button(
            button_frame, 
            text="Connect to SourceTV", 
            command=self.connect_to_sourceTV,
            state=tk.DISABLED
        )
        self.sourceTV_button.pack(side=tk.LEFT, padx=5)
        self.sourceTV_button.bind('<Enter>', self.play_hover_sound)

    def connect_to_cge(self):
        # Connect to CGE7-193 server
        self.play_sound("join.wav")
        self.launch_tf2_with_connect("connect 79.127.217.197:22912")

    def connect_to_sourceTV(self):
        # Connect to SourceTV server
        self.play_sound("join.wav")
        self.launch_tf2_with_connect("connect 79.127.217.197:22913")

    def show_tf2_not_installed(self):
        # Show splash window if TF2 is not installed
        win = tk.Toplevel(self.root)
        win.title("TF2 is NOT installed")
        win.configure(bg="#2d2d2d")
        win.overrideredirect(True)
        center_window(win, 400, 200)
        # Message
        label = tk.Label(win, text="TF2 is NOT installed", font=("Arial", 18, "bold"), bg="#2d2d2d", fg="#ff5555")
        label.pack(pady=(40, 10))
        # Close button
        close_btn = tk.Button(win, text="Close", font=("Arial", 12), bg="#232323", fg="#ffffff", bd=0, relief=tk.FLAT, activebackground="#3d3d3d", activeforeground="#ff5555", command=win.destroy, cursor="hand2")
        close_btn.pack(pady=(10, 20))
        win.lift()
        win.attributes('-topmost', True)
        win.after(3000, win.destroy)

    def launch_tf2_with_connect(self, connect_command):
        # Launch TF2 with connect command
        try:
            server = connect_command.split(' ')[1]
            if os.name == 'nt':
                # Windows: Use Steam.exe directly to launch TF2 and connect
                steam_path = self.find_steam_executable()
                if steam_path:
                    subprocess.Popen([steam_path, '-applaunch', '440', f'+connect {server}'])
                else:
                    self.status_var.set("Steam executable not found. Please ensure Steam is installed.")
                    self.show_tf2_not_installed()
            else:
                # Linux/Mac: Use steam -applaunch 440 +connect ip:port
                subprocess.Popen(['steam', '-applaunch', '440', f'+connect {server}'])
        except Exception as e:
            self.status_var.set(f"Error launching TF2: {str(e)}")

    def find_steam_executable(self):
        # Find Steam.exe path on Windows
        possible_paths = [
            os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Steam', 'Steam.exe'),
            os.path.join(os.environ.get('ProgramFiles', ''), 'Steam', 'Steam.exe'),
            os.path.join(os.environ.get('ProgramW6432', ''), 'Steam', 'Steam.exe'),
            os.path.expandvars(r'%LOCALAPPDATA%\Steam\Steam.exe'),
            os.path.expandvars(r'%USERPROFILE%\Steam\Steam.exe'),
        ]
        for path in possible_paths:
            if path and os.path.exists(path):
                return path
        return None

    def create_status_bars(self):
        # Status bars
        self.status_var = tk.StringVar(value="Initializing...")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, 
            relief=tk.SUNKEN, anchor=tk.CENTER
        )
        status_bar.pack(fill=tk.X, padx=10, pady=5)
        
        self.ordinance_var = tk.StringVar(value="Calculating time since ordinance start...")
        ordinance_bar = ttk.Label(
            self.root, textvariable=self.ordinance_var,
            relief=tk.SUNKEN, anchor=tk.CENTER
        )
        ordinance_bar.pack(fill=tk.X, padx=10, pady=(0, 5))

    def init_csv(self):
        # Initialize CSV file
        if not os.path.exists(CSV_FILENAME):
            with open(CSV_FILENAME, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['UTC Timestamp', 'Player Count', 'Map', 'Players Online'])

    def log_to_csv(self, timestamp, player_count, map_name, players):
        # Log data to CSV
        try:
            with open(CSV_FILENAME, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                player_names = ", ".join([player.name for player in players]) if players else "None"
                writer.writerow([timestamp, player_count, map_name, player_names])
        except IOError:
            pass

    def load_existing_data(self):
        # Load existing data from CSV
        if not os.path.exists(CSV_FILENAME):
            return
        
        try:
            with open(CSV_FILENAME, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                
                for row in rows[-MAX_DATA_POINTS:]:
                    try:
                        dt = datetime.fromisoformat(row['UTC Timestamp'].replace('Z', '+00:00'))
                        time_str = dt.strftime('%H:%M:%S')
                        player_count = int(row['Player Count'])
                        
                        self.timestamps.append(time_str)
                        self.player_counts.append(player_count)
                    except (KeyError, ValueError):
                        continue
        except Exception:
            pass

    def test_connection(self):
        # Test server connection
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(TIMEOUT)
                sock.connect(CGE7_193)
                sock.send(b'\xFF\xFF\xFF\xFFTSource Engine Query\x00')
                sock.recv(1400)
            self.status_var.set("Connection test successful")
            return True
        except Exception as e:
            self.status_var.set(f"Connection failed: {str(e)}")
            return False

    def update_server_info(self):
        # Update server info
        info, player_count, players = self.get_server_info()
        
        if info is None:
            query_status = "\u2717 Query failed"
            if self.server_info is not None:
                info = self.server_info
            if self.player_counts:
                player_count = self.player_counts[-1]
            if self.player_list:
                players = self.player_list
        else:
            query_status = "\u2713 Query successful"
            self.server_info = info
            self.player_list = players

        current_map = self.update_server_display(info, player_count, query_status)
        self.update_player_list(players)
        self.log_and_update_graph(current_map, player_count, players)
        # Only call update_ordinance_time once at startup, it will reschedule itself
        if not hasattr(self, '_ordinance_timer_started'):
            self._ordinance_timer_started = True
            self.update_ordinance_time()
        current_time = datetime.now(timezone.utc).strftime('%H:%M:%S')
        self.status_var.set(f"Last update (UTC): {current_time} | {query_status}")

    def update_loop(self):
        # Main update loop
        while self.running:
            try:
                self.update_server_info()
            except Exception:
                pass
            time.sleep(UPDATE_INTERVAL)

    def update_server_display(self, info, player_count, query_status):
        # Update server display
        current_map = "Unknown"
        
        if info:
            self.server_name_label.config(text=f"Server Name: {info.server_name}")
            self.server_map_label.config(text=f"Current Map: {info.map_name}")
            self.player_count_label.config(text=f"Players: {player_count}/{info.max_players}")
            current_map = info.map_name
            self.check_map_change(current_map)
            self.update_button_states(current_map)
        else:
            self.server_name_label.config(text="Server Name: Unknown")
            self.server_map_label.config(text="Current Map: Unknown")
            self.player_count_label.config(text="Players: ?/?")
            self.cge_button.config(state=tk.DISABLED)
            self.sourceTV_button.config(state=tk.DISABLED)
        
        return current_map

    def update_button_states(self, current_map):
        # Update button states
        if current_map.lower() == "2fort":
            self.cge_button.config(state=tk.NORMAL)
        else:
            self.cge_button.config(state=tk.DISABLED)
        
        excluded_maps = ["mazemazemazemaze", "kurt", "ask", "askask"]
        if current_map.lower() not in [m.lower() for m in excluded_maps]:
            self.sourceTV_button.config(state=tk.NORMAL)
        else:
            self.sourceTV_button.config(state=tk.DISABLED)

    def update_player_list(self, players):
        # Update player list
        self.player_listbox.delete(0, tk.END)
        
        if not players:
            self.player_listbox.insert(tk.END, "No players online")
            return
        
        for player in players:
            playtime = ""
            if player.duration > 0:
                hours = int(player.duration // 3600)
                minutes = int((player.duration % 3600) // 60)
                playtime = f" ({hours}h {minutes}m)"
            # If player name is empty or unreadable, show 'connecting...'
            name = player.name if player.name and player.name.strip() else "connecting..."
            self.player_listbox.insert(tk.END, f"{name}{playtime}")

    def log_and_update_graph(self, current_map, player_count, players):
        # Log data and update graph
        current_time = datetime.now(timezone.utc).strftime('%H:%M:%S')
        self.timestamps.append(current_time)
        self.player_counts.append(player_count)
        
        self.log_to_csv(
            datetime.now(timezone.utc).isoformat(),
            player_count,
            current_map,
            players
        )
        
        self.update_graph()

    def update_graph(self):
        # Update graph
        if not self.timestamps:
            return
            
        self.ax.clear()
        
        n = max(1, len(self.timestamps)) // 10
        visible_ticks = [tick if i % n == 0 else "" for i, tick in enumerate(self.timestamps)]
        
        self.ax.plot(self.timestamps, self.player_counts, color=self.theme['plot'], marker='o')
        self.ax.set_xticks(self.timestamps)
        self.ax.set_xticklabels(visible_ticks, rotation=45)
        
        # Always show y-axis from 0 to 16 with 17 integer ticks
        self.ax.set_ylim(0, 16)
        self.ax.set_yticks(list(range(17)))
        self.ax.yaxis.set_major_formatter(lambda x, pos: f"{int(x)}")
        self.ax.set_title(f'Online Players - {CGE7_193[0]}:{CGE7_193[1]}', color=self.theme['graph_fg'])
        self.update_graph_theme()
        self.canvas.draw()

    def update_ordinance_time(self):
        # Update ordinance time every second
        current_utc = datetime.now(timezone.utc)
        time_diff = current_utc - ORDINANCE_START

        days = time_diff.days
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        self.ordinance_var.set(
            f"Time since start of cge7-193: {days} days, {hours:02d}:{minutes:02d}:{seconds:02d}"
        )
        # Schedule next update in 1 second
        if hasattr(self, 'root') and self.running:
            self.root.after(1000, self.update_ordinance_time)

    def play_sound(self, sound_file):
        # Play sound file
        if not PYGAME_AVAILABLE:
            return
        try:
            sound_path = os.path.join("resources", sound_file)
            if os.path.exists(sound_path):
                sound = pygame.mixer.Sound(sound_path)
                # Set volume to 50% for join.wav and information.wav
                if sound_file in ("join.wav", "information.wav"):
                    sound.set_volume(0.25)
                sound.play()
        except Exception:
            pass

    def check_map_change(self, new_map):
        # Check for map change
        if self.current_map is not None and self.current_map != new_map:
            if new_map == "ordinance":
                self.play_sound("ordinance.wav")
            elif new_map.startswith("ord_"):
                if new_map == "ord_cry":
                    self.play_sound("ord_cry.wav")
                elif new_map == "ord_err":
                    self.play_sound("ord_err.wav")
                elif new_map == "ord_ren":
                    self.play_sound("ord_ren.wav")
                else:
                    self.play_sound("ord_mapchange.wav")
        
        self.current_map = new_map

    def start_websocket_monitor(self):
        # Start WebSocket monitor
        self.websocket_thread = threading.Thread(target=self.run_websocket, daemon=True)
        self.websocket_thread.start()

    def run_websocket(self):
        # Run WebSocket connection
        asyncio.run(self.websocket_handler())

    async def websocket_handler(self):
        # Handle WebSocket connection
        uri = VIEWS_WEBSOCKET_URL
        
        while self.websocket_running:
            try:
                async with websockets.connect(uri) as websocket:
                    self.root.after(0, self.update_views_status, "Connected to WebSocket")
                    
                    while self.websocket_running:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=30)
                            self.process_websocket_message(message)
                        except asyncio.TimeoutError:
                            await websocket.ping()
                            continue
                            
            except Exception as e:
                self.root.after(0, self.update_views_status, f"WebSocket Error: {str(e)}")
                await asyncio.sleep(5)

    def process_websocket_message(self, message):
        # Process WebSocket message
        try:
            data = json.loads(message)
            if data.get('type') == 'NEW_VIEW':
                view_data = data['data']
                view_id = view_data['id']
                timestamp = view_data['timestamp']
                
                cst_time = datetime.fromtimestamp(timestamp)
                time_str = cst_time.strftime('%Y-%m-%d %I:%M:%S %p CST')
                
                self.root.after(0, self.update_views_display, view_id, time_str)
                
                if self.last_view_id is None or int(view_id) > int(self.last_view_id):
                    self.root.after(0, self.show_new_view_notification, view_id, time_str)
                    self.last_view_id = view_id
                    
        except Exception as e:
            self.root.after(0, self.update_views_status, f"Error processing message: {str(e)}")

    def update_views_display(self, view_id, timestamp):
        # Update views display
        self.views_label.config(text=f"Current View ID: {view_id}")
        self.last_view_time_label.config(text=f"Last View Time: {timestamp}")
        self.update_views_status("New view received")

    def update_views_status(self, message):
        # Update views status
        self.views_status.config(text=f"Status: {message}")

    def on_close(self):
        # Clean up on close
        self.play_sound("close.wav")
        # wait for close.wav to finish playing before closing
        if PYGAME_AVAILABLE:
            import pygame
            start = time.time()
            # wait up to 1 seconds for sound to finish
            while pygame.mixer.get_busy() and time.time() - start < 1:
                self.root.update()
                time.sleep(0.05)
        self.running = False
        self.websocket_running = False
        self.root.destroy()

def center_window(window, width, height):
    # Center window on screen
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def show_thank_you():
    # Show splash screen
    splash = tk.Tk()
    splash.title("Welcome to Reployer")
    splash.configure(bg="#2d2d2d")
    splash.overrideredirect(True)  # Remove window top bar
    # Set splash icon to sourceclown.ico
    try:
        icon_path = os.path.join("resources", "sourceclown.ico")
        if os.path.exists(icon_path):
            splash.iconbitmap(icon_path)
    except Exception:
        pass
    # Make splash screen always on top
    try:
        splash.attributes('-topmost', True)
    except Exception:
        pass

    # Play a random preopenX.mp3 sound at 50% volume
    try:
        import random
        preopen_files = ["preopen1.mp3", "preopen2.mp3", "preopen3.mp3"]
        chosen = random.choice(preopen_files)
        sound_path = os.path.join("resources", chosen)
        if os.path.exists(sound_path):
            try:
                import pygame
                pygame.mixer.init()
                sound = pygame.mixer.Sound(sound_path)
                sound.set_volume(0.5)
                sound.play()
            except Exception:
                pass
    except Exception:
        pass

    # Display gaq9.png and sourceclown.png side by side at the top, with sourceclown.png resized to match gaq9.png
    try:
        from tkinter import PhotoImage
        img_frame = tk.Frame(splash, bg="#2d2d2d")
        img_frame.pack(side=tk.TOP, pady=(10, 0))
        gaq9_path = os.path.join("resources", "gaq9.png")
        sourceclown_path = os.path.join("resources", "sourceclown.png")
        gaq9_img = None
        sourceclown_img = None
        if os.path.exists(gaq9_path):
            splash.gaq9_img = PhotoImage(file=gaq9_path)
            gaq9_img = splash.gaq9_img
            gaq9_label = tk.Label(img_frame, image=gaq9_img, bg="#2d2d2d")
            gaq9_label.pack(side=tk.LEFT, padx=(0, 10))
        if os.path.exists(sourceclown_path) and gaq9_img is not None:
            try:
                from PIL import Image, ImageTk
                gaq9_pil = Image.open(gaq9_path)
                sourceclown_pil = Image.open(sourceclown_path)
                # Resize sourceclown.png to match gaq9.png size
                sourceclown_pil = sourceclown_pil.resize(gaq9_pil.size, Image.LANCZOS)
                splash.sourceclown_img = ImageTk.PhotoImage(sourceclown_pil)
                sourceclown_img = splash.sourceclown_img
            except Exception:
                # Fallback: show original size if PIL not available
                splash.sourceclown_img = PhotoImage(file=sourceclown_path)
                sourceclown_img = splash.sourceclown_img
            sourceclown_label = tk.Label(img_frame, image=sourceclown_img, bg="#2d2d2d")
            sourceclown_label.pack(side=tk.LEFT)
    except Exception:
        pass

    label = tk.Label(splash, text="Thank you for downloading Reployer!", font=("Arial", 16, "bold"), bg="#2d2d2d", fg="#4fc3f7")
    label.pack(pady=(5, 0))

    author_label = tk.Label(splash, text="Made by Kiverix (the clown)", font=("Arial", 12), bg="#2d2d2d", fg="#ffffff")
    author_label.pack(pady=(5, 0))

    loading_var = tk.StringVar(value="Loading")
    loading_label = tk.Label(splash, textvariable=loading_var, font=("Arial", 14), bg="#2d2d2d", fg="#ffffff")
    loading_label.pack(pady=10)

    # Center window after all widgets are packed
    center_window(splash, 500, 375)

    def animate_loading(count=0):
        dots = '.' * ((count % 4) + 1)
        loading_var.set(f"Loading{dots}")
        if splash.winfo_exists():
            splash.after(200, animate_loading, count + 1)

    animate_loading()
    splash.after(5000, splash.destroy)
    splash.mainloop()

if __name__ == "__main__":
    show_thank_you()
    root = tk.Tk()
    # Set main app icon to sourceclown.ico
    try:
        icon_path = os.path.join("resources", "sourceclown.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass
    center_window(root, 1500, 1000)
    app = ServerMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()