import sys
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QPushButton,
    QHBoxLayout, QLabel, QMessageBox, QWidget, QApplication, QFileDialog
)
#from mne_lsl import StreamLSL, list_lsl_streams
import logging
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mne_lsl.player import PlayerLSL as Player
from mne_lsl.stream import StreamLSL as Stream
from mne_lsl.lsl import resolve_streams
from feed_window import FeedWindow
from funcpack.metrics import compute_heart_params

import time
import uuid

def bandpass_filter(sig, fs, low=0.5, high=8.0, order=3):
    nyq = 0.5 * fs
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    return filtfilt(b, a, sig)


class HeartApp(QWidget):
    def __init__(self):
        
        super().__init__()
        self.setWindowTitle("PPG Streaming GUI")
        
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Buttons
        self.start_btn = QPushButton("Emulate Stream")
        self.stop_btn = QPushButton("Stop Stream")
        self.connect_button = QPushButton("Connect to Stream")
        self.feed_button = QPushButton("Open FEED")
        
        self.layout.addWidget(self.start_btn)
        self.layout.addWidget(self.stop_btn)
        self.layout.addWidget(self.connect_button)
        self.layout.addWidget(self.feed_button)
        
        # Labels for metrics
        self.hr_label = QLabel("HR: -- bpm")
        self.sdnn_label = QLabel("SDNN: -- s")
        self.rmssd_label = QLabel("RMSSD: -- s")
        self.rmssd_corrected_label = QLabel("RMSSD Corrected: -- s")
        
        
        self.layout.addWidget(self.hr_label)
        self.layout.addWidget(self.sdnn_label)
        self.layout.addWidget(self.rmssd_label)
        self.layout.addWidget(self.rmssd_corrected_label)
        # self.layout.addWidget(self.rmssd_corrected_label) 
        # Matplotlib figure
        self.fig = Figure(figsize=(6, 3))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.layout.addWidget(self.canvas)


        # Signals
        self.start_btn.clicked.connect(self.start_stream)
        self.stop_btn.clicked.connect(self.stop_stream)
        self.connect_button.clicked.connect(self.connect_stream)
        self.feed_button.clicked.connect(self.open_feed_window)
        
        # State
        self.player = None
        self.stream = None
        self.timer = None
    
    def open_feed_window(self):
        self.feed_window = FeedWindow(self)
        self.feed_window.exec_()

    def connect_stream(self):
        """Let the user pick an LSL stream and connect to it (PyQt5 + mne-lsl)."""

        # Step 1. Discover available LSL streams
        streams = resolve_streams(timeout=5)
        if not streams:
            QMessageBox.warning(self, "No streams", "No LSL streams found.")
            return

        # Step 2. Create a popup selection dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Select LSL Stream")
        layout = QVBoxLayout(dlg)

        label = QLabel("Available LSL streams:")
        layout.addWidget(label)

        list_widget = QListWidget()
        for s in streams:
            
            display_text = (
                f"{s.name}  "
            )
            
            list_widget.addItem(display_text)
            
        layout.addWidget(list_widget)

        # Buttons
        buttons = QHBoxLayout()
        btn_ok = QPushButton("Connect")
        btn_cancel = QPushButton("Cancel")
        buttons.addWidget(btn_ok)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        selected_index = {"idx": None}

        def on_ok():
            selected_index["idx"] = list_widget.currentRow()
            dlg.accept()

        def on_cancel():
            dlg.reject()

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(on_cancel)

        # Step 3. Run the dialog modally
        if dlg.exec_() == QDialog.Accepted and selected_index["idx"] is not None:
            s = streams[selected_index["idx"]]
            try:
                # Step 4. Connect to the chosen stream
                self.stream = Stream(bufsize=60, name=s.name).connect()
                QMessageBox.information(
                    self,
                    "Connected",
                    f"Connected to stream:\n{s.name} ")
                print(self.stream.info)
                
                logging.info(f"Connected to {s.name} ")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")
        else:
            logging.info("User cancelled connection.")
            
        from PyQt5.QtCore import QTimer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(1000)  # update every 500ms
        
        
    def start_stream(self):
        # choose file
        fname, _ = QFileDialog.getOpenFileName(self, "Select EDF file", "", "FIF Files (*.edf)")
        if not fname:
            return

        # start player
        #self.player = Player(fname, chunk_size=200).start()
        ppg_stream = uuid.uuid4().hex

        self.player = Player(fname, chunk_size=200, source_id=ppg_stream, name='PPG_Stream').start()

        # connect to stream
        self.stream = Stream(bufsize=60, source_id=ppg_stream, name="PPG_Stream").connect()
        print(self.stream.info)
        
        

        # update periodically
        from PyQt5.QtCore import QTimer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(400)  # update every 500ms

    def stop_stream(self):
        if self.timer:
            self.timer.stop()
        if self.player:
            self.player.stop()
        self.player = None
        self.stream = None
        self.ax.clear()
        self.canvas.draw()

    def update_plot(self):
        # get recent 5s of data
        data, ts = self.stream.get_data(20)  # 20 seconds
        if data.shape[1] == 0:
            return
        
        ch_list = self.stream.info["ch_names"]        
        ppg_names = ['EEG PPG', 'PPG']
        
        for p in ppg_names:
            if p in ch_list:
                ppg_name = p
                break
            else:
                ppg_name = None
                
        if not ppg_name:
            raise ValueError("No PPG channel found in stream!")
        
        
        ppg_idx = self.stream.info["ch_names"].index(ppg_name)
        
        
        ppg = data[ppg_idx, :]  # first channel
        fs = int(self.stream.info["sfreq"])

        # filter
        signal = -bandpass_filter(ppg, fs)
        #prominence = 0.5 * np.std(signal)
        #peaks, _ = find_peaks(signal, distance=int(0.4 * fs), prominence=prominence)

        # compute metrics
        #if len(peaks) > 2 and max(ts) > 20:
            
        params = compute_heart_params(ppg, fs)
        
        if params:
            
            self.hr_label.setText(f"HR: {params['hr']:.1f} bpm")
            self.sdnn_label.setText(f"SDNN: {params['sdnn']:.3f} s")
            self.rmssd_label.setText(f"RMSSD: {params['rmssd']:.3f} s")
            self.rmssd_corrected_label.setText(f"RMSSD Corrected: {params['rmssd_corrected']:.3f} s")
            peaks = params["peaks"]
            # plot
            self.ax.clear()
            self.ax.plot(ts, signal, label="PPG")
            self.ax.plot(ts[peaks], signal[peaks], "ro", label="Peaks")
            self.ax.set_title("PPG Signal")
            self.ax.legend()
            self.canvas.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = HeartApp()
    win.show()
    sys.exit(app.exec_())
