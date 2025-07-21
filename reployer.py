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
import requests
from bs4 import BeautifulSoup
import hashlib
import websockets
import asyncio
import json

# Constants
CGE7_193 = ('79.127.217.197', 22912)
TIMEOUT = 5  # seconds
CSV_FILENAME = "player_log.csv"
ORDINANCE_START = datetime(2025, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
MAX_DATA_POINTS = 60
UPDATE_INTERVAL = 5  # seconds
VIEWS_WEBSOCKET_URL = "wss://view.gaq9.com"
# VIEWS_WEBSOCKET_URL = "wss://test.interloper.party" # Webhook testing URL, thanks lunascapegaq9 <3
VIEWS_HISTORY_FILE = "views_history.txt"

# Module Imports and Initialization
try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not available, sound effects disabled")

try:
    from a2s.info import info as a2s_info
    from a2s.players import players as a2s_players
    A2S_AVAILABLE = True
except ImportError:
    A2S_AVAILABLE = False
    print("Warning: python-a2s not installed properly")

class ServerMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reployer v1.0")
        
        # Initialize data structures
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
        
        # Setup application
        self.setup_theme()
        self.init_csv()
        self.load_existing_data()
        self.create_widgets()
        
        # Start monitoring
        self.running = True
        self.start_monitoring()
        self.start_websocket_monitor()
        self.test_connection()
        self.play_sound("open.wav")
        
        # Start map cycle updates
        self.update_map_display()

    def setup_theme(self):
        """Configure theme colors for dark mode"""
        self.theme = {
            'bg': "#2d2d2d", 
            'fg': "#ffffff", 
            'frame': "#3d3d3d",
            'graph_bg': "#1e1e1e", 
            'graph_fg': "#ffffff", 
            'graph_grid': "#4d4d4d",
            'plot': "#4fc3f7", 
            'listbox_bg': "#3d3d3d", 
            'listbox_fg': "#ffffff",
            'select_bg': "#4fc3f7", 
            'select_fg': "#ffffff",
            'status_online': "green",
            'status_restart1': "blue",
            'status_restart2': "gold",
            'button_bg': "#3d3d3d",
            'button_fg': "#ffffff",
            'views_bg': "#3d3d3d",
            'views_fg': "#4fc3f7"
        }
        self.apply_theme()

    def apply_theme(self):
        """Apply theme to all widgets"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles
        style.configure('.', background=self.theme['bg'], foreground=self.theme['fg'])
        style.configure('TFrame', background=self.theme['bg'])
        style.configure('TLabel', background=self.theme['bg'], foreground=self.theme['fg'])
        style.configure('TLabelframe', background=self.theme['bg'], foreground=self.theme['fg'])
        style.configure('TLabelframe.Label', background=self.theme['bg'], foreground=self.theme['fg'])
        style.configure('TButton', 
                       background=self.theme['button_bg'],
                       foreground=self.theme['button_fg'],
                       bordercolor=self.theme['button_bg'])
        
        # Apply to root window
        self.root.configure(bg=self.theme['bg'])
        
        # Apply to existing widgets
        if hasattr(self, 'fig'):
            self.update_graph_theme()
        if hasattr(self, 'player_listbox'):
            self.player_listbox.config(
                bg=self.theme['listbox_bg'], 
                fg=self.theme['listbox_fg'],
                selectbackground=self.theme['select_bg'], 
                selectforeground=self.theme['select_fg']
            )
        if hasattr(self, 'views_label'):
            self.views_label.config(
                bg=self.theme['views_bg'],
                fg=self.theme['views_fg']
            )

    def create_widgets(self):
        """Create all GUI widgets"""
        # Server Information Frame (now includes map cycle info)
        self.create_server_info_frame()
        
        # Views Counter Frame
        self.create_views_frame()
        
        # Player List Frame
        self.create_player_list_frame()
        
        # Graph Frame
        self.create_graph_frame()
        
        # Action Buttons Frame
        self.create_action_buttons()
        
        # Status Bars
        self.create_status_bars()
        
        # Debug Info
        debug_frame = ttk.Frame(self.root)
        debug_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(debug_frame, text=f"Server: {CGE7_193[0]}:{CGE7_193[1]}").pack(side=tk.RIGHT)

    def create_views_frame(self):
        """Create views counter display frame"""
        views_frame = ttk.LabelFrame(self.root, text="Website Views Monitor", padding=10)
        views_frame.pack(fill=tk.X, padx=10, pady=5)
        
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

    def create_server_info_frame(self):
        """Create server information display frame with integrated map cycle info"""
        info_frame = ttk.LabelFrame(self.root, text="Server Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Server info section
        self.server_name_label = ttk.Label(info_frame, text="Server Name: Testing connection...")
        self.server_name_label.pack(anchor=tk.W)
        
        self.server_map_label = ttk.Label(info_frame, text="Current Map: Unknown")
        self.server_map_label.pack(anchor=tk.W)
        
        self.player_count_label = ttk.Label(info_frame, text="Players: ?/?")
        self.player_count_label.pack(anchor=tk.W)
        
        self.query_status_label = ttk.Label(info_frame, text="Query Status: Initializing...")
        self.query_status_label.pack(anchor=tk.W)
        
        # Separator
        ttk.Separator(info_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # Map cycle section
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
        """Get the correct map based on the hardcoded UTC schedule"""
        if hour is None:
            hour = datetime.utcnow().hour

        # The exact map rotation (00:00-23:59 UTC)
        map_schedule = {
            0: "askask",   1: "ask",     2: "ask",     3: "askask",
            4: "ask",      5: "dustbowl", 6: "askask",  7: "ask",
            8: "ask",      9: "askask",  10: "ask",    11: "dustbowl",
            12: "askask", 13: "ask",    14: "ask",    15: "askask",
            16: "ask",    17: "dustbowl",18: "askask", 19: "ask",
            20: "dustbowl",21: "askask", 22: "ask",    23: "dustbowl"
        }
        return map_schedule.get(hour, "unknown")
    
    def get_adjacent_maps(self):
        """Get previous and next map in cycle with time remaining"""
        current_hour = datetime.utcnow().hour
        current_minute = datetime.utcnow().minute
        current_second = datetime.utcnow().second
        
        prev_hour = current_hour - 1
        if prev_hour < 0:
            prev_hour = 23
        prev_map = self.get_map_based_on_utc_hour(prev_hour)
        
        next_hour = current_hour + 1
        if next_hour > 23:
            next_hour = 0
        next_map = self.get_map_based_on_utc_hour(next_hour)
        
        seconds_remaining = (59 - current_second) % 60
        minutes_remaining = (59 - current_minute) % 60
        
        return prev_map, next_map, minutes_remaining, seconds_remaining

    def update_map_display(self):
        """Update the map and time display"""
        utc_now = datetime.utcnow()
        local_now = datetime.now()
        
        utc_time = utc_now.strftime("%H:%M:%S")
        local_time = local_now.strftime("%H:%M:%S")
        
        current_map = self.get_map_based_on_utc_hour()
        prev_map, next_map, mins_left, secs_left = self.get_adjacent_maps()
        
        # Determine restart status
        current_minute = utc_now.minute
        current_second = utc_now.second
        
        if current_minute == 59 and current_second >= 10:
            restart_status = "FIRST RESTART"
            status_color = self.theme['status_restart1']
        elif current_minute == 1 and current_second <= 30:
            restart_status = "SECOND RESTART"
            status_color = self.theme['status_restart2']
        else:
            restart_status = "ONLINE"
            status_color = self.theme['status_online']
        
        # Update labels with theme colors
        self.time_label.config(text=f"UTC: {utc_time} | Local: {local_time}")
        self.current_map_cycle_label.config(text=f"Current Map Cycle: {current_map}")
        self.adjacent_maps_label.config(text=f"Previous: {prev_map} | Next: {next_map}")
        self.countdown_label.config(text=f"Next cycle in: {mins_left:02d}m {secs_left:02d}s")
        self.restart_status_label.config(text=f"Server Status: {restart_status}", foreground=status_color)

        # Play time warning sounds
        self.handle_time_warning_sounds(utc_now)

        # Play new cycle sound at hour change
        if utc_now.minute == 59 and utc_now.second == 0:
            if self.sound_played_minute != utc_now.hour:
                self.play_sound('new_cycle.wav')
                self.sound_played_minute = utc_now.hour
        elif utc_now.minute != 59:
            self.sound_played_minute = None
        
        self.root.after(50, self.update_map_display)

    def handle_time_warning_sounds(self, utc_now):
        """Handle playing time warning sounds"""
        current_minute = utc_now.minute
        current_second = utc_now.second
        
        if current_second == 0:
            minute_sounds = {
                30: 'thirty.wav',
                45: 'fifteen.wav',
                55: 'five.wav'
            }
            
            sound_key = minute_sounds.get(current_minute)
            if sound_key and self.last_time_sound_minute != current_minute:
                self.play_sound(sound_key)
                self.last_time_sound_minute = current_minute
            elif current_minute not in minute_sounds:
                self.last_time_sound_minute = None

    def create_player_list_frame(self):
        """Create online players list frame"""
        player_frame = ttk.LabelFrame(self.root, text="Online Players", padding=10)
        player_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.player_listbox = tk.Listbox(
            player_frame, 
            bg=self.theme['listbox_bg'], 
            fg=self.theme['listbox_fg'],
            selectbackground=self.theme['select_bg'], 
            selectforeground=self.theme['select_fg']
        )
        self.player_listbox.pack(fill=tk.BOTH, expand=True)

    def create_graph_frame(self):
        """Create player count history graph frame"""
        graph_frame = ttk.LabelFrame(self.root, text="Player Count History", padding=10)
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.fig = Figure(figsize=(8, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.update_graph_theme()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_graph_theme(self):
        """Update graph colors based on theme"""
        self.fig.set_facecolor(self.theme['graph_bg'])
        self.ax.set_facecolor(self.theme['graph_bg'])
        self.ax.tick_params(colors=self.theme['graph_fg'])
        self.ax.xaxis.label.set_color(self.theme['graph_fg'])
        self.ax.yaxis.label.set_color(self.theme['graph_fg'])
        self.ax.title.set_color(self.theme['graph_fg'])
        self.ax.grid(True, color=self.theme['graph_grid'])

    def create_action_buttons(self):
        """Create buttons for TF2 actions"""
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        # CGE7-193 Button
        self.cge_button = ttk.Button(
            button_frame,
            text="Connect to CGE7-193",
            command=self.connect_to_cge,
            state=tk.DISABLED
        )
        self.cge_button.pack(side=tk.LEFT, padx=5)

        # SourceTV Button
        self.sourceTV_button = ttk.Button(
            button_frame, 
            text="Connect to SourceTV", 
            command=self.connect_to_sourceTV,
            state=tk.DISABLED
        )
        self.sourceTV_button.pack(side=tk.LEFT, padx=5)

    def connect_to_cge(self):
        """Launch TF2 and connect to CGE7-193 server"""
        self.launch_tf2_with_connect("connect 79.127.217.197:22912")

    def connect_to_sourceTV(self):
        """Launch TF2 and connect to SourceTV server"""
        self.launch_tf2_with_connect("connect 79.127.217.197:22913")

    def launch_tf2_with_connect(self, connect_command):
        """Launch TF2 with a connect command"""
        try:
            if os.name == 'nt':
                subprocess.Popen(f'start steam://rungameid/440//+{connect_command}', shell=True)
            else:
                subprocess.Popen(['steam', '-applaunch', '440', f'+{connect_command}'])
        except Exception as e:
            self.status_var.set(f"Error launching TF2: {str(e)}")

    def create_status_bars(self):
        """Create status and ordinance time bars"""
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
        """Initialize CSV file with headers if it doesn't exist"""
        if not os.path.exists(CSV_FILENAME):
            with open(CSV_FILENAME, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['UTC Timestamp', 'Player Count', 'Map', 'Players Online'])

    def log_to_csv(self, timestamp, player_count, map_name, players):
        """Log data to CSV file"""
        try:
            with open(CSV_FILENAME, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                player_names = ", ".join([player.name for player in players]) if players else "None"
                writer.writerow([timestamp, player_count, map_name, player_names])
        except IOError as e:
            print(f"Error writing to CSV: {e}")

    def load_existing_data(self):
        """Load existing data from CSV file to populate the graph"""
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
        except Exception as e:
            print(f"Error loading existing data: {e}")

    def test_connection(self):
        """Test if we can reach the server"""
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

    def get_server_info(self):
        """Try to get server info with multiple fallback methods"""
        if not A2S_AVAILABLE:
            return None, 0, []
        
        try:
            info = a2s_info(CGE7_193, timeout=TIMEOUT)
            players = a2s_players(CGE7_193, timeout=TIMEOUT)
            return info, len(players), players
        except Exception as e:
            self.status_var.set(f"A2S Error: {str(e)}")
            return None, 0, []

    def start_monitoring(self):
        """Start the update thread"""
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def update_loop(self):
        """Main update loop running in a separate thread"""
        while self.running:
            try:
                self.update_server_info()
            except Exception as e:
                print(f"Error in update loop: {e}")
            time.sleep(UPDATE_INTERVAL)

    def update_server_info(self):
        """Update all server information displays"""
        info, player_count, players = self.get_server_info()
        self.player_list = players
        
        if info is not None:
            query_status = "✓ Query successful"
        else:
            query_status = "✗ Query failed"
        
        current_map = self.update_server_display(info, player_count, query_status)
        self.update_player_list(players)
        self.log_and_update_graph(current_map, player_count, players)
        self.update_ordinance_time()
        
        current_time = datetime.now(timezone.utc).strftime('%H:%M:%S')
        self.status_var.set(f"Last update (UTC): {current_time} | {query_status}")

    def update_server_display(self, info, player_count, query_status):
        """Update server information display"""
        current_map = "Unknown"
        self.query_status_label.config(text=f"Query Status: {query_status}")
        
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
        """Update the enabled/disabled state of the action buttons"""
        # Enable CGE7-193 button only when map is 2fort
        if current_map.lower() == "2fort":
            self.cge_button.config(state=tk.NORMAL)
        else:
            self.cge_button.config(state=tk.DISABLED)
        
        # Enable SourceTV button for all maps except excluded ones
        excluded_maps = ["mazemazemazemaze", "kurt", "ask", "askask"]
        if current_map.lower() not in [m.lower() for m in excluded_maps]:
            self.sourceTV_button.config(state=tk.NORMAL)
        else:
            self.sourceTV_button.config(state=tk.DISABLED)

    def update_player_list(self, players):
        """Update the player listbox with current players"""
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
            
            self.player_listbox.insert(tk.END, f"{player.name}{playtime}")

    def log_and_update_graph(self, current_map, player_count, players):
        """Log data and update the graph"""
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
        """Update the player count graph"""
        if not self.timestamps:
            return
            
        self.ax.clear()
        
        n = max(1, len(self.timestamps) // 10)
        visible_ticks = [tick if i % n == 0 else "" for i, tick in enumerate(self.timestamps)]
        
        self.ax.plot(
            self.timestamps, 
            self.player_counts, 
            color=self.theme['plot'], 
            marker='o'
        )
        self.ax.set_xticks(self.timestamps)
        self.ax.set_xticklabels(visible_ticks, rotation=45)
        
        y_max = max(self.player_counts) + 1 if self.player_counts else 10
        self.ax.set_ylim(bottom=0, top=y_max)
        
        self.ax.set_title(
            f'Online Players - {CGE7_193[0]}:{CGE7_193[1]}',
            color=self.theme['graph_fg']
        )
        
        self.update_graph_theme()
        self.canvas.draw()

    def update_ordinance_time(self):
        """Calculate and display time since ordinance start"""
        current_utc = datetime.now(timezone.utc)
        time_diff = current_utc - ORDINANCE_START
        
        days = time_diff.days
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        self.ordinance_var.set(
            f"Time since start of ordinance: {days} days, {hours:02d}:{minutes:02d}:{seconds:02d}"
        )

    def play_sound(self, sound_file):
        """Play a sound file from the resources folder"""
        if not PYGAME_AVAILABLE:
            return
        
        try:
            sound_path = os.path.join("resources", sound_file)
            if os.path.exists(sound_path):
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
            else:
                print(f"Sound file not found: {sound_path}")
        except Exception as e:
            print(f"Error playing sound {sound_file}: {e}")

    def check_map_change(self, new_map):
        """Check if map has changed and play appropriate sound"""
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
        """Start the WebSocket monitoring thread"""
        self.websocket_thread = threading.Thread(target=self.run_websocket, daemon=True)
        self.websocket_thread.start()

    def run_websocket(self):
        """Run the WebSocket connection in a separate thread"""
        asyncio.run(self.websocket_handler())

    async def websocket_handler(self):
        """Handle WebSocket connection and messages"""
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
                            # Send ping to keep connection alive
                            await websocket.ping()
                            continue
                            
            except Exception as e:
                error_msg = f"WebSocket Error: {str(e)}"
                self.root.after(0, self.update_views_status, error_msg)
                await asyncio.sleep(5)  # Wait before reconnecting

    def process_websocket_message(self, message):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            if data.get('type') == 'NEW_VIEW':
                view_data = data['data']
                view_id = view_data['id']
                timestamp = view_data['timestamp']
                
                # Convert timestamp to CST datetime
                cst_time = datetime.fromtimestamp(timestamp)
                time_str = cst_time.strftime('%Y-%m-%d %I:%M:%S %p CST')
                
                # Update UI
                self.root.after(0, self.update_views_display, view_id, time_str)
                
                # Show notification if this is a new view
                if self.last_view_id is None or int(view_id) > int(self.last_view_id):
                    self.root.after(0, self.show_new_view_notification, view_id, time_str)
                    self.last_view_id = view_id
                    
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self.root.after(0, self.update_views_status, error_msg)

    def update_views_display(self, view_id, timestamp):
        """Update the views display with new information"""
        self.views_label.config(text=f"Current View ID: {view_id}")
        self.last_view_time_label.config(text=f"Last View Time: {timestamp}")
        self.update_views_status("New view received")

    def update_views_status(self, message):
        """Update the views status label"""
        self.views_status.config(text=f"Status: {message}")

    def show_new_view_notification(self, view_id, timestamp):
        """Show notification for new view"""
        self.play_sound("new_view.wav")
        messagebox.showinfo(
            "New View on GAQ9.com",
            f"New View Detected!\n\nView ID: {view_id}\nTimestamp: {timestamp}"
        )

    def on_close(self):
        """Clean up resources when closing the application"""
        self.play_sound("close.wav")
        
        if PYGAME_AVAILABLE:
            time.sleep(0.5)
        
        self.running = False
        self.websocket_running = False
        
        if hasattr(self, 'update_thread') and self.update_thread.is_alive():
            self.update_thread.join(timeout=1)
        if hasattr(self, 'websocket_thread') and self.websocket_thread.is_alive():
            self.websocket_thread.join(timeout=1)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()