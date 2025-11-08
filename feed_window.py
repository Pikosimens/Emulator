from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QLabel, QProgressBar, QWidget, QHBoxLayout
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor, QPainter, QBrush
import time
import random
from funcpack.metrics import get_baseline_PPG, get_online_PPG

class CircleWidget(QWidget):
    """Simple widget to draw a colored circle."""
    def __init__(self, color=Qt.gray, diameter=60, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._diameter = diameter
        self.setFixedSize(diameter + 10, diameter + 10)

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        brush = QBrush(self._color)
        painter.setBrush(brush)
        painter.drawEllipse(5, 5, self._diameter, self._diameter)


class FeedWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_gui = parent
        
        self.setWindowTitle("Biofeedback FEED")
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        
        self.hr_label = QLabel("HR: -- %")
        self.sdnn_label = QLabel("SDNN: -- %")
        self.rmssd_label = QLabel("RMSSD: -- %")
        self.rmssd_corrected_label = QLabel("RMSSD Corrected: -- %")
        
        
        layout.addWidget(self.hr_label)
        layout.addWidget(self.sdnn_label)
        layout.addWidget(self.rmssd_label)
        layout.addWidget(self.rmssd_corrected_label)

        # --- Baseline Section ---
        self.baseline_button = QPushButton("Collect baseline")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.baseline_button)
        layout.addWidget(self.progress)
        layout.addWidget(self.label)

        # --- Training Section ---
        self.start_button = QPushButton("Start training")
        self.start_button.setVisible(False)
        layout.addWidget(self.start_button)

        # --- Circles Section (feedback visuals) ---
        self.circles = {
            "hr_change": CircleWidget(Qt.gray),
            "sdnn_change": CircleWidget(Qt.gray),
            "rmssd_change": CircleWidget(Qt.gray),
            "rmssd_corrected_change": CircleWidget(Qt.gray),
        }

        row = QHBoxLayout()
        for c in self.circles.values():
            row.addWidget(c)
        layout.addLayout(row)

        # --- Connections ---
        self.baseline_button.clicked.connect(self.baseline_PPG)
        self.start_button.clicked.connect(self.start_training)

        # Timer for training updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_feedback)

        self.elapsed = 0
        self.baseline_collected = False

    # -------------------------------
    # Baseline collection
    # -------------------------------
    def baseline_PPG(self):
        """Collect baseline for 60 seconds."""
        self.baseline_button.setEnabled(False)
        self.progress.setVisible(True)
        self.label.setText("SIT STILL!")
        self.progress.setValue(0)
        self.elapsed = 0

        self.baseline_timer = QTimer(self)
        self.baseline_timer.timeout.connect(self._update_baseline_progress)
        self.baseline_timer.start(1000)  # 1s steps

    def _update_baseline_progress(self):
        
        self.elapsed += 1
        self.progress.setValue(int(100 * self.elapsed / 60))
        
        if self.elapsed >= 60:
            
            self.baseline_timer.stop()
            
            ch_list = self.parent_gui.stream.info["ch_names"]   
            ppg_names = ['EEG PPG', 'PPG']
                        
            for p in ppg_names:
                
                if p in ch_list:
                    ppg_name = p
                    break
                else:
                    ppg_name = None
                
            if not ppg_name:
                raise ValueError("No PPG channel found in stream!")
            
            
                
            self.ppg_idx = self.parent_gui.stream.info["ch_names"].index(ppg_name)                
            print("PPG channel index:", self.ppg_idx)
            
            signal, ts = self.parent_gui.stream.get_data(60)
            ppg = signal[self.ppg_idx, :] 
            self.fs = int(self.parent_gui.stream.info["sfreq"])
            self.baseline_params = get_baseline_PPG(ppg, self.fs, duration=60)
            

            self.baseline_collected = True
            self.start_button.setVisible(True)
            self.progress.setVisible(False)
                
            


    # -------------------------------
    # Training session
    # -------------------------------
    def start_training(self):
        """Start biofeedback updates every 300 ms."""
        if not self.baseline_collected:
            self.label.setText("Please collect baseline first.")
            return
        self.label.setText("Training in progress...")
        self.timer.start(100)

    def update_feedback(self):
        """Update the biofeedback visualization."""
        
        signal, ts = self.parent_gui.stream.get_data(20) # SET WINDOW SIZE
        ppg = signal[self.ppg_idx, :]  
        data = get_online_PPG(ppg, self.fs, self.baseline_params, window_size=8)
        
        data.pop("current_params", None)  # remove raw params
        
        for key, val in data.items():
            # convert val (-1…1 or percent change) → color
            color = self.map_value_to_color(val-1)
            self.circles[key].set_color(color)

        self.hr_label.setText(f"HR: {100*data["hr_change"]:.1f} %")
        self.sdnn_label.setText(f"SDNN: {100*data['sdnn_change']:.1f} %")
        self.rmssd_label.setText(f"RMSSD: {100*data['rmssd_change']:.1f} %")
        self.rmssd_corrected_label.setText(f"RMSSD Corrected: {100*data['rmssd_corrected_change']:.1f} %")        
        
    # def get_online_PPG(self):
    #     """Mock function: simulate changing physiological data."""
    #     # In reality, you'd query your real-time stream here.
    #     return {
    #         "hr_change": random.uniform(-1, 1),
    #         "sdnn_change": random.uniform(-1, 1),
    #         "rmssd_change": random.uniform(-1, 1),
    #         "rmssd_corrected_change": random.uniform(-1, 1),
    #     }

    def map_value_to_color(self, val):
        """Map change value [-1, +1] → color (red–gray–green)."""
        val = max(-1, min(1, val))
        if val < 0:
            return QColor(255, int(255*(1+val)), int(255*(1+val)))  # redder for negative
        else:
            return QColor(int(255*(1-val)), 255, int(255*(1-val)))  # greener for positive
