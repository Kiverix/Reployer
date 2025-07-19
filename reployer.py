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

# Constants
SERVER_ADDRESS = ('79.127.217.197', 22912)
TIMEOUT = 5  # seconds
CSV_FILENAME = "player_log.csv"
ORDINANCE_START = datetime(2025, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
MAX_DATA_POINTS = 60
UPDATE_INTERVAL = 5  # seconds

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
        self.root.title("Reployer v0.3")
        
        # Initialize data structures
        self.timestamps = deque(maxlen=MAX_DATA_POINTS)
        self.player_counts = deque(maxlen=MAX_DATA_POINTS)
        self.player_list = []
        self.server_info = None
        self.current_map = None
        
        # Setup application
        self.setup_theme()
        self.init_csv()
        self.load_existing_data()
        self.create_widgets()
        
        # Start monitoring
        self.running = True
        self.start_monitoring()
        self.test_connection()
        self.play_sound("open.wav")
    
    def setup_theme(self):
        """Configure theme colors for dark mode"""
        self.theme = {
            'bg': "#2d2d2d", 'fg': "#ffffff", 'frame': "#3d3d3d",
            'graph_bg': "#1e1e1e", 'graph_fg': "#ffffff", 'graph_grid': "#4d4d4d",
            'plot': "#4fc3f7", 'listbox_bg': "#3d3d3d", 'listbox_fg': "#ffffff",
            'select_bg': "#4fc3f7", 'select_fg': "#ffffff"
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
        
        # Apply to root window
        self.root.configure(bg=self.theme['bg'])
        
        # Apply to existing widgets
        if hasattr(self, 'fig'):
            self.update_graph_theme()
        if hasattr(self, 'player_listbox'):
            self.player_listbox.config(
                bg=self.theme['listbox_bg'], fg=self.theme['listbox_fg'],
                selectbackground=self.theme['select_bg'], selectforeground=self.theme['select_fg']
            )
    
    def create_widgets(self):
        """Create all GUI widgets"""
        # Server Information Frame
        self.create_server_info_frame()
        
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
        ttk.Label(debug_frame, text=f"Server: {SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}").pack(side=tk.RIGHT)
    
    def create_action_buttons(self):
        """Create buttons for TF2 actions"""
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Button for connecting to 2fort
        self.twofort_button = ttk.Button(
            button_frame, 
            text="Connect to 2fort", 
            command=self.connect_to_2fort,
            state=tk.DISABLED
        )
        self.twofort_button.pack(side=tk.LEFT, padx=5)
        
        # Button for connecting to the main server
        self.main_server_button = ttk.Button(
            button_frame, 
            text="Connect to Main Server", 
            command=self.connect_to_main_server,
            state=tk.DISABLED
        )
        self.main_server_button.pack(side=tk.LEFT, padx=5)
    
    def connect_to_2fort(self):
        """Launch TF2 and connect to 2fort server"""
        self.launch_tf2_with_connect("connect 79.127.217.197:22913")
    
    def connect_to_main_server(self):
        """Launch TF2 and connect to main server"""
        self.launch_tf2_with_connect("connect 79.127.217.197:22913")
    
    def launch_tf2_with_connect(self, connect_command):
        """Launch TF2 with a connect command"""
        try:
            # On Windows
            if os.name == 'nt':
                subprocess.Popen(f'start steam://rungameid/440//+{connect_command}', shell=True)
            # On Linux/Mac
            else:
                subprocess.Popen(['steam', '-applaunch', '440', f'+{connect_command}'])
        except Exception as e:
            self.status_var.set(f"Error launching TF2: {str(e)}")
    
    def create_server_info_frame(self):
        """Create server information display frame"""
        info_frame = ttk.LabelFrame(self.root, text="Server Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.server_name_label = ttk.Label(info_frame, text="Server Name: Testing connection...")
        self.server_name_label.pack(anchor=tk.W)
        
        self.server_map_label = ttk.Label(info_frame, text="Current Map: Unknown")
        self.server_map_label.pack(anchor=tk.W)
        
        self.player_count_label = ttk.Label(info_frame, text="Players: ?/?")
        self.player_count_label.pack(anchor=tk.W)
    
    def create_player_list_frame(self):
        """Create online players list frame"""
        player_frame = ttk.LabelFrame(self.root, text="Online Players", padding=10)
        player_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.player_listbox = tk.Listbox(
            player_frame, 
            bg=self.theme['listbox_bg'], fg=self.theme['listbox_fg'],
            selectbackground=self.theme['select_bg'], selectforeground=self.theme['select_fg']
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
    
    def update_graph_theme(self):
        """Update graph colors based on theme"""
        if hasattr(self, 'fig'):
            self.fig.set_facecolor(self.theme['graph_bg'])
            self.ax.set_facecolor(self.theme['graph_bg'])
            self.ax.tick_params(colors=self.theme['graph_fg'])
            self.ax.xaxis.label.set_color(self.theme['graph_fg'])
            self.ax.yaxis.label.set_color(self.theme['graph_fg'])
            self.ax.title.set_color(self.theme['graph_fg'])
            self.ax.grid(True, color=self.theme['graph_grid'])
    
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
                sock.connect(SERVER_ADDRESS)
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
            info = a2s_info(SERVER_ADDRESS, timeout=TIMEOUT)
            players = a2s_players(SERVER_ADDRESS, timeout=TIMEOUT)
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
        
        # Update server info display
        current_map = self.update_server_display(info, player_count)
        
        # Update player list
        self.update_player_list(players)
        
        # Log data and update graph
        self.log_and_update_graph(current_map, player_count, players)
        
        # Update ordinance time
        self.update_ordinance_time()
        
        # Update status with current time
        current_time = datetime.now(timezone.utc).strftime('%H:%M:%S')
        self.status_var.set(f"Last update (UTC): {current_time}")
    
    def update_server_display(self, info, player_count):
        """Update server information display"""
        current_map = "Unknown"
        
        if info:
            self.server_name_label.config(text=f"Server Name: {info.server_name}")
            self.server_map_label.config(text=f"Current Map: {info.map_name}")
            self.player_count_label.config(text=f"Players: {player_count}/{info.max_players}")
            current_map = info.map_name
            self.check_map_change(current_map)
            
            # Update button states based on current map
            self.update_button_states(current_map)
        else:
            self.server_name_label.config(text="Server Name: Unknown")
            self.server_map_label.config(text="Current Map: Unknown")
            self.player_count_label.config(text="Players: ?/?")
            # Disable both buttons if no server info
            self.twofort_button.config(state=tk.DISABLED)
            self.main_server_button.config(state=tk.DISABLED)
        
        return current_map
    
    def update_button_states(self, current_map):
        """Update the enabled/disabled state of the action buttons"""
        # Enable 2fort button only if map is "2fort"
        if current_map.lower() == "2fort":
            self.twofort_button.config(state=tk.NORMAL)
        else:
            self.twofort_button.config(state=tk.DISABLED)
        
        # Enable main server button only if map is not in the excluded list
        excluded_maps = ["mazemazemazemaze", "kurt", "ask", "askask"]
        if current_map.lower() not in [m.lower() for m in excluded_maps]:
            self.main_server_button.config(state=tk.NORMAL)
        else:
            self.main_server_button.config(state=tk.DISABLED)
    
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
        
        # Show only every nth label to prevent overcrowding
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
        
        # Set y-axis limits with some padding
        y_max = max(self.player_counts) + 1 if self.player_counts else 10
        self.ax.set_ylim(bottom=0, top=y_max)
        
        self.ax.set_title(
            f'Online Players - {SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}',
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
    
    def on_close(self):
        """Clean up resources when closing the application"""
        self.play_sound("close.wav")
        
        if PYGAME_AVAILABLE:
            time.sleep(0.5)
        
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=1)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()