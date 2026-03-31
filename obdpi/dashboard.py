import tkinter as tk                # lets you create a window + UI
from obd_manager import ObdManager  # class that talks to the car

class ObdDashboard:
    def __init__(self, root):
        self.root = root  #stores the window inside the object. root is the window that popped up
        self.root.title("OBD Dashboard")
        self.root.geometry("1000x600")
        self.root.configure(bg="black")

        # comment this for nonfullscreen on Pi
        self.root.attributes("-fullscreen", True)

        self.manager = ObdManager()
        self.port = "/dev/rfcomm0"   # change if needed
        self.try_connect()


        # Colors
        self.bg = "#0f1115"
        self.card = "#1a1f29"
        self.text = "#f5f7fa"
        self.muted = "#9aa4b2"
        self.accent = "#39c0ff"
        self.good = "#47d16c"
        self.warn = "#ffb020"
        self.bad = "#ff5f5f"

        # runs the function that creates all the visual pieces
        # the “draw the screen” step
        self.build_ui() 

        # what starts the repeating update loop
        self.update_dashboard()

    def try_connect(self):
        
        # Try to run the following code, but if something goes wrong, do not crash immediately
        try: 
            self.manager.init_obd_connection(self.port)
            # .init_obd_connection(...) = the function inside that helper that tries to connect
        except:
            pass # Do nothing. Prevents the GUI from instantly dying


    # Creates the visible layout.
    def build_ui(self):

        title = tk.Label(
            self.root, # window it lives inside
            text="OBD LIVE DASHBOARD", # text shown on the label
            bg=self.bg, # Background color of the label
            fg=self.text, #fg means foreground color, which is basically text color. So the title text is bright
            
            #This places the label in the window.
            font=("Helvetica", 28, "bold")
        )
        title.pack(pady=(20, 10))

        self.status_label = tk.Label(
            self.root,
            text="CONNECTING...",
            bg=self.bg,
            fg=self.muted,
            font=("Helvetica", 14, "bold")
        )
        self.status_label.pack()


        # Place the box on screen,
        # give it space around it,
        # and stretch it across the width
        speed_frame = tk.Frame(self.root, bg=self.card, padx=30, pady=20)
        speed_frame.pack(pady=20, padx=30, fill="x")

        tk.Label(
            speed_frame,
            text="SPEED",
            bg=self.card,
            fg=self.muted,
            font=("Helvetica", 18, "bold")
        ).pack()

        self.speed_value = tk.Label(
            speed_frame,
            text="--",
            bg=self.card,
            fg=self.accent,
            font=("Helvetica", 90, "bold")
        )
        self.speed_value.pack()

        tk.Label(
            speed_frame,
            text="KPH",
            bg=self.card,
            fg=self.text,
            font=("Helvetica", 20, "bold")
        ).pack()

        grid_frame = tk.Frame(self.root, bg=self.bg)
        grid_frame.pack(padx=30, pady=10, fill="both", expand=True)

        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)
        grid_frame.columnconfigure(2, weight=1)

        self.rpm_card = self.make_card(grid_frame, "RPM", 0, 0)
        self.boost_card = self.make_card(grid_frame, "BOOST (PSI)", 0, 1)
        self.temp_card = self.make_card(grid_frame, "COOLANT TEMP (C)", 0, 2)
        self.voltage_card = self.make_card(grid_frame, "VOLTAGE (V)", 1, 0)
        self.dtc_card = self.make_card(grid_frame, "DTC CODES", 1, 1)
        self.connection_card = self.make_card(grid_frame, "STATUS", 1, 2)

    def make_card(self, parent, title, row, col):
        frame = tk.Frame(parent, bg=self.card, padx=20, pady=20)
        frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        label = tk.Label(
            frame,
            text=title,
            bg=self.card,
            fg=self.muted,
            font=("Helvetica", 14, "bold")
        )
        label.pack(anchor="w")

        value = tk.Label(
            frame,
            text="--",
            bg=self.card,
            fg=self.text,
            font=("Helvetica", 28, "bold")
        )
        value.pack(anchor="w", pady=(15, 0))

        return value

    def parse_numeric(self, response):
        try:
            return float(str(response).split()[0])
        except:
            return None

    def get_response(self, command):
        try:
            return self.manager.generate_obd_response(command)
        except:
            return "No OBD response"

    def update_dashboard(self):
        connected = False
        try:
            connected = self.manager.has_obd_connection()
        except:
            connected = False

        if not connected:
            self.try_connect()
            try:
                connected = self.manager.has_obd_connection()
            except:
                connected = False

        if connected:
            self.status_label.config(text="CONNECTED", fg=self.good)
            self.connection_card.config(text="CONNECTED", fg=self.good)

            speed = self.get_response("SPEED")
            rpm = self.get_response("RPM")
            boost = self.get_response("BOOST")
            temp = self.get_response("COOLANT_TEMP")
            voltage = self.get_response("VOLTAGE")
            dtc = self.get_response("DTC")

            speed_num = self.parse_numeric(speed)
            rpm_num = self.parse_numeric(rpm)
            boost_num = self.parse_numeric(boost)
            temp_num = self.parse_numeric(temp)
            voltage_num = self.parse_numeric(voltage)

            self.speed_value.config(text=str(int(speed_num)) if speed_num is not None else "--")
            self.rpm_card.config(text=str(int(rpm_num)) if rpm_num is not None else "--")
            self.boost_card.config(text=f"{boost_num:.1f}" if boost_num is not None else "--")

            if temp_num is not None:
                if temp_num < 95:
                    self.temp_card.config(text=f"{temp_num:.0f}", fg=self.good)
                elif temp_num < 110:
                    self.temp_card.config(text=f"{temp_num:.0f}", fg=self.warn)
                else:
                    self.temp_card.config(text=f"{temp_num:.0f}", fg=self.bad)
            else:
                self.temp_card.config(text="--", fg=self.text)

            if voltage_num is not None:
                if voltage_num >= 12.4:
                    self.voltage_card.config(text=f"{voltage_num:.1f}", fg=self.good)
                elif voltage_num >= 12.0:
                    self.voltage_card.config(text=f"{voltage_num:.1f}", fg=self.warn)
                else:
                    self.voltage_card.config(text=f"{voltage_num:.1f}", fg=self.bad)
            else:
                self.voltage_card.config(text="--", fg=self.text)

            if str(dtc).strip() == "[]":
                self.dtc_card.config(text="NONE", fg=self.good)
            else:
                self.dtc_card.config(text=str(dtc), fg=self.warn)

        else:
            self.status_label.config(text="NO CONNECTION", fg=self.bad)
            self.connection_card.config(text="NO CONNECTION", fg=self.bad)
            self.speed_value.config(text="--")
            self.rpm_card.config(text="--", fg=self.text)
            self.boost_card.config(text="--", fg=self.text)
            self.temp_card.config(text="--", fg=self.text)
            self.voltage_card.config(text="--", fg=self.text)
            self.dtc_card.config(text="--", fg=self.text)

        self.root.after(1000, self.update_dashboard)

root = tk.Tk()
app = ObdDashboard(root)
root.mainloop()