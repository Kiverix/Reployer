import tkinter as tk
from tkinter import ttk
import threading
import time
import a2s
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class ServerTab:
    def __init__(self, notebook, ip, port):
        self.ip = ip
        self.port = port
        self.source_tv_port = 27013  # Standard SourceTV port
        self.running = True
        self.data = []
        self.times = []
        self.start_time = time.time()
        self.lock = threading.Lock()
        self.current_map = "Unknown"
        self.players = []
        self.main_server_online = False
        self.source_tv_online = False

        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text=f"{ip}:{port}")

        # Create main container with 2 columns
        self.main_container = ttk.Frame(self.frame)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left column for the graph
        self.graph_frame = ttk.Frame(self.main_container)
        self.graph_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Right column for player info
        self.info_frame = ttk.Frame(self.main_container)
        self.info_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Configure grid weights
        self.main_container.columnconfigure(0, weight=3)
        self.main_container.columnconfigure(1, weight=1)
        self.main_container.rowconfigure(0, weight=1)

        # Graph setup
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(6, 4), dpi=100, facecolor='#2e2e2e')
        self.ax.set_title("Players on CGE7-193", color='white')
        self.ax.set_xlabel("Time (s)", color='white')
        self.ax.set_ylabel("Players", color='white')
        self.ax.grid(True, color='#4a4a4a')
        self.ax.set_facecolor('#2e2e2e')
        self.ax.tick_params(colors='white')

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Info panel setup
        self.status_frame = ttk.Frame(self.info_frame)
        self.status_frame.pack(fill=tk.X, pady=(0, 10))

        # Main server status indicator
        self.main_server_status = ttk.Label(
            self.status_frame, 
            text="Main: Offline", 
            foreground="red",
            font=('Helvetica', 9, 'bold')
        )
        self.main_server_status.pack(side=tk.LEFT, padx=5)

        # SourceTV status indicator
        self.source_tv_status = ttk.Label(
            self.status_frame, 
            text="SourceTV: Offline", 
            foreground="red",
            font=('Helvetica', 9, 'bold')
        )
        self.source_tv_status.pack(side=tk.LEFT, padx=5)

        self.map_label = ttk.Label(self.info_frame, text="Map: Unknown", font=('Helvetica', 10, 'bold'))
        self.map_label.pack(pady=(0, 10))

        self.player_count_label = ttk.Label(self.info_frame, text="Players: 0/0", font=('Helvetica', 10))
        self.player_count_label.pack(pady=(0, 10))

        self.player_list_label = ttk.Label(self.info_frame, text="Online Players:", font=('Helvetica', 10, 'bold'))
        self.player_list_label.pack(anchor='w')

        self.player_listbox = tk.Listbox(
            self.info_frame,
            bg='#3e3e3e',
            fg='white',
            selectbackground='#4e79a7',
            selectforeground='white',
            relief=tk.FLAT,
            font=('Helvetica', 9)
        )
        self.player_listbox.pack(fill=tk.BOTH, expand=True)

        self.thread = threading.Thread(target=self.update_loop, daemon=True)
        self.thread.start()

    def check_server_status(self, ip, port):
        try:
            a2s.info((ip, port), timeout=2)
            return True
        except:
            return False

    def query_server(self):
        # Check server statuses
        self.main_server_online = self.check_server_status(self.ip, self.port)
        self.source_tv_online = self.check_server_status(self.ip, self.source_tv_port)
        
        # Update status indicators
        self.frame.after(0, self.update_status_indicators)

        # Try to get data from online servers
        if self.main_server_online:
            try:
                info = a2s.info((self.ip, self.port), timeout=2)
                players = a2s.players((self.ip, self.port), timeout=2)
                return info.player_count, info.map_name, players
            except Exception as e:
                print(f"[{self.ip}:{self.port}] Main server query failed: {e}")
        
        if self.source_tv_online:
            try:
                stv_info = a2s.info((self.ip, self.source_tv_port), timeout=2)
                stv_players = a2s.players((self.ip, self.source_tv_port), timeout=2)
                return stv_info.player_count, stv_info.map_name, stv_players
            except Exception as stv_e:
                print(f"[{self.ip}:{self.source_tv_port}] SourceTV query failed: {stv_e}")
        
        return None, None, None

    def update_status_indicators(self):
        # Update main server status
        if self.main_server_online:
            self.main_server_status.config(text="Main: Online", foreground="green")
        else:
            self.main_server_status.config(text="Main: Offline", foreground="red")

        # Update SourceTV status
        if self.source_tv_online:
            self.source_tv_status.config(text="SourceTV: Online", foreground="green")
        else:
            self.source_tv_status.config(text="SourceTV: Offline", foreground="red")

    def update_loop(self):
        while self.running:
            count, map_name, players = self.query_server()
            current_time = time.time() - self.start_time
            
            if count is not None and map_name is not None:
                with self.lock:
                    self.times.append(current_time)
                    self.data.append(count)
                    self.current_map = map_name
                    self.players = players if players else []
                
                self.frame.after(0, self.update_display)
            
            time.sleep(5)

    def update_display(self):
        with self.lock:
            times = self.times.copy()
            data = self.data.copy()
            map_name = self.current_map
            players = self.players.copy()
        
        # Update the graph
        self.ax.clear()
        if times and data:
            self.ax.plot(times, data, marker='o', color='#4e79a7')
            self.ax.set_title("Players on CGE7-193", color='white')
            self.ax.set_xlabel("Time (s)", color='white')
            self.ax.set_ylabel("Players", color='white')
            self.ax.grid(True, color='#4a4a4a')
            self.ax.set_facecolor('#2e2e2e')
            self.ax.tick_params(colors='white')
            self.canvas.draw()

        # Update the info panel
        self.map_label.config(text=f"Map: {map_name}")
        
        player_count = len(players)
        max_players = 24  # Default TF2 max players, adjust if needed
        self.player_count_label.config(text=f"Players: {player_count}/{max_players}")
        
        self.player_listbox.delete(0, tk.END)
        for player in players:
            name = player.name if player.name else "Unknown"
            self.player_listbox.insert(tk.END, name)

    def close(self):
        """Clean up resources when tab is closed"""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1)
        plt.close(self.fig)


class TF2MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reployer")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Apply dark theme to the main window
        self.root.configure(bg='#2e2e2e')
        
        # Create style for dark theme
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure colors
        self.style.configure('.', background='#2e2e2e', foreground='white')
        self.style.configure('TNotebook', background='#2e2e2e', borderwidth=0)
        self.style.configure('TNotebook.Tab', background='#3e3e3e', foreground='white', 
                           padding=[10, 5], borderwidth=0)
        self.style.map('TNotebook.Tab', background=[('selected', '#4e4e4e')])
        self.style.configure('TFrame', background='#2e2e2e')
        self.style.configure('TLabel', background='#2e2e2e', foreground='white')
        
        self.server_tabs = []

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Add controls frame
        self.controls_frame = ttk.Frame(root)
        self.controls_frame.pack(fill=tk.X, padx=10, pady=5)

        # Add server input fields
        self.ip_label = ttk.Label(self.controls_frame, text="Server IP:")
        self.ip_label.pack(side=tk.LEFT, padx=5)
        
        self.ip_entry = ttk.Entry(self.controls_frame, width=15)
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        self.ip_entry.insert(0, "79.127.217.197")
        
        self.port_label = ttk.Label(self.controls_frame, text="Port:")
        self.port_label.pack(side=tk.LEFT, padx=5)
        
        self.port_entry = ttk.Entry(self.controls_frame, width=6)
        self.port_entry.pack(side=tk.LEFT, padx=5)
        self.port_entry.insert(0, "22912")
        
        self.add_button = ttk.Button(self.controls_frame, text="Add Server", command=self.add_server_from_input)
        self.add_button.pack(side=tk.LEFT, padx=5)

        # Add the predefined server tab
        self.add_server_tab("79.127.217.197", 22912)

    def add_server_from_input(self):
        ip = self.ip_entry.get()
        port = self.port_entry.get()
        try:
            port = int(port)
            self.add_server_tab(ip, port)
        except ValueError:
            tk.messagebox.showerror("Error", "Port must be a number")

    def add_server_tab(self, ip, port):
        try:
            tab = ServerTab(self.notebook, ip, port)
            self.server_tabs.append(tab)
            self.notebook.select(tab.frame)  # Focus on the new tab
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to monitor server: {e}")

    def on_close(self):
        """Clean up all server tabs before closing"""
        for tab in self.server_tabs:
            tab.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        app = TF2MonitorApp(root)
        root.mainloop()
    except Exception as e:
        tk.messagebox.showerror("Fatal Error", f"Application crashed: {e}")