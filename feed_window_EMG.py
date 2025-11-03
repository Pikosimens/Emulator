from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QLabel, QProgressBar, QWidget, QHBoxLayout, QApplication
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor, QPainter, QBrush
import time
import random
from funcpack.metrics import get_baseline_EMG, get_online_EMG

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
        
def map_value_to_color(self, val):
    """Map change value [-1, +1] → color (red–gray–green)."""
    val = max(-1, min(1, val))
    if val < 0:
        return QColor(255, int(255*(1+val)), int(255*(1+val)))  # redder for negative
    else:
        return QColor(int(255*(1-val)), 255, int(255*(1-val)))  # greener for positive
    
    
class FeedWindowEMG(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_gui = parent
        
        self.setWindowTitle("Biofeedback FEED - EMG")
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        
        self.mean_label = QLabel("Mean: -- %")
        self.std_label = QLabel("Std Dev: -- %")
        self.cumsum_label = QLabel("Cumulative Change: -- %")
        
        layout.addWidget(self.mean_label)
        layout.addWidget(self.std_label)
        layout.addWidget(self.cumsum_label)

        # --- Baseline Section ---
        self.baseline_button = QPushButton("Collect baseline")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.label = QLabel("Collecting baseline...")
        self.label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.baseline_button)
        layout.addWidget(self.progress)
        layout.addWidget(self.label)

        self.baseline_button.clicked.connect(self.collect_baseline)

        # --- Training Section ---
        self.start_button = QPushButton("Start training")
        self.start_button.setVisible(False)
        layout.addWidget(self.start_button)

        # --- Circles Section (feedback visuals) ---
        self.circles = {
            "mean_change": CircleWidget(Qt.gray),
            "std_change": CircleWidget(Qt.gray),
            "cumsum_change": CircleWidget(Qt.gray),
        }

        row = QHBoxLayout()
        for c in self.circles.values():
            row.addWidget(c)
        layout.addLayout(row)

        # --- Connections ---
        self.baseline_button.clicked.connect(self.baseline_EMG)
        self.start_button.clicked.connect(self.start_training)

        # Timer for training updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_feedback)

        self.elapsed = 0
        self.baseline_collected = False
        
    def baseline_EMG(self):
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.label.setText("Collecting baseline EMG...")
        self.baseline_button.setEnabled(False)
        QApplication.processEvents()

        # Simulate baseline collection
        for i in range(1, 101):
            time.sleep(0.05)  # Simulate time delay
            self.progress.setValue(i)
            QApplication.processEvents()

        # Here you would collect real EMG data
        sig = self.parent_gui.stream.get_data()  
        fs = self.parent_gui.stream.get_fs()
        chlist = self.parent_gui.stream.info["ch_names"]
        
        emg_names = ['LFL', 'RFL', 'LEX', 'REX']
        
        
        for e in emg_names:
            if e in chlist:
                ch_idx = self.parent_gui.stream.info["ch_names"].index(e)
                self.baseline_params[e] = get_baseline_EMG(sig, fs, duration=60)
                break
            else:
                emg_name = None

        
        if self.baseline_params is not None:
            self.baseline_collected = True
            self.label.setText("Baseline collected.")
            self.start_button.setVisible(True)
        else:
            self.label.setText("Failed to collect baseline.")
        
        self.progress.setVisible(False)
        self.baseline_button.setEnabled(True)
    # -------------------------------
    # Training Section    
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
        data = get_online_PPG(ppg, self.fs, self.baseline_params, window_size=20)
        
        data.pop("current_params", None)  # remove raw params
        
        for key, val in data.items():
            # convert val (-1…1 or percent change) → color
            color = self.map_value_to_color(val-1)
            self.circles[key].set_color(color)

        self.hr_label.setText(f"HR: {100*data["hr_change"]:.1f} %")
        self.sdnn_label.setText(f"SDNN: {100*data['sdnn_change']:.3f} %")
        self.rmssd_label.setText(f"RMSSD: {100*data['rmssd_change']:.3f} %")
        self.rmssd_corrected_label.setText(f"RMSSD Corrected: {100*data['rmssd_corrected_change']:.3f} %")  