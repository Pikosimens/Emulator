from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QLabel, QProgressBar, QWidget, QHBoxLayout, QApplication
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor, QPainter, QBrush
import time
import random
from funcpack.metrics import get_baseline_EMG, get_online_EMG

# class CircleWidget(QWidget):
#     """Simple widget to draw a colored circle."""
#     def __init__(self, color=Qt.gray, diameter=60, parent=None):
#         super().__init__(parent)
#         self._color = QColor(color)
#         self._diameter = diameter
#         self.setFixedSize(diameter + 10, diameter + 10)

#     def set_color(self, color):
#         self._color = QColor(color)
#         self.update()

#     def paintEvent(self, event):
#         painter = QPainter(self)
#         painter.setRenderHint(QPainter.Antialiasing)
#         brush = QBrush(self._color)
#         painter.setBrush(brush)
#         painter.drawEllipse(5, 5, self._diameter, self._diameter)
        
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
        
        # self.mean_label = QLabel("Mean: -- %")
        # self.std_label = QLabel("Std Dev: -- %")
        self.cumsum_label = QLabel("Cumulative Change: -- %")
        
        # layout.addWidget(self.mean_label)
        # layout.addWidget(self.std_label)
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

        # --- Training Section ---
        self.start_button = QPushButton("Start training")
        self.start_button.setVisible(False)
        layout.addWidget(self.start_button)
        self.game_button = QPushButton("Start Game")
        self.game_button.setVisible(False)
        layout.addWidget(self.game_button)
        self.game_button.clicked.connect(self.open_game)

        # # --- Circles Section (feedback visuals) ---
        # self.circles = {
        #     "mean_change": CircleWidget(Qt.gray),
        #     "std_change": CircleWidget(Qt.gray),
        #     "cumsum_change": CircleWidget(Qt.gray),
        # }

        # row = QHBoxLayout()
        # for c in self.circles.values():
        #     row.addWidget(c)
        # layout.addLayout(row)

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
            time.sleep(0.2)  # Simulate time delay
            self.progress.setValue(i)
            QApplication.processEvents()

        # Here you would collect real EMG data
        sig, ts = self.parent_gui.stream.get_data()  
        self.fs = self.parent_gui.stream.info["sfreq"]
        chlist = self.parent_gui.stream.info["ch_names"]
        
        self.baseline_params = {}
        
        emg_names = ['LFL', 'RFL', 'LEX', 'REX']
        self.emg_ids = {}
        
        for e in emg_names:
            if e in chlist:
                ch_idx = self.parent_gui.stream.info["ch_names"].index(e)
                self.emg_ids[e] = ch_idx

        self.active_chnames = list(self.emg_ids.keys())
        print(self.emg_ids)
        for e in self.emg_ids.keys():
            print(f"Collecting baseline for EMG channel: {self.emg_ids[e]}")      
            self.baseline_params[e] = get_baseline_EMG(sig[self.emg_ids[e], :], self.fs, duration=20)

        
        if self.baseline_params is not None:
            self.baseline_collected = True
            self.label.setText("Baseline collected.")
            self.start_button.setVisible(True)
            self.game_button.setVisible(True)

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
        result = {}
        signal, ts = self.parent_gui.stream.get_data(2) # SET WINDOW SIZE
        
        for channel in self.active_chnames:
            
            idx = self.emg_ids[channel]
            bsl_channel = self.baseline_params[channel]
            result[channel] = 100 * get_online_EMG(signal[idx, :], self.fs, bsl_channel)
            
        feed_string = ""
            
        for channel in self.active_chnames:
            
            feed_string += f"{channel}: {result[channel]:.2f} %   "
            
        self.cumsum_label.setText(f"Cumulative Change: {feed_string}")
        
    def open_game(self):
        self.game = GameWindow(self.parent_gui)
        self.game.exec_()
    
        
        # for key, val in data.items():
        #     # convert val (-1…1 or percent change) → color
        #     color = self.map_value_to_color(val-1)
        #     self.circles[key].set_color(color)

from PyQt5.QtWidgets import QProgressBar, QPushButton, QVBoxLayout, QHBoxLayout, QLabel

class GameWindow(QDialog):
    """Простая мини-игра типа Pong с управлением от LEX и LFL и визуальными индикаторами."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_gui = parent
        self.setWindowTitle("EMG Pong Game")
        self.setFixedSize(500, 450)

        # Игровые переменные
        self.ball_pos = [240, 200]
        self.ball_vel = [4, 3]
        self.paddle_x = 210
        self.paddle_width = 80
        self.paddle_height = 10
        self.score = 0

        # Таймер
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_game)
        self.timer.start(33)  # ~30 fps

        # --- Верхняя панель с индикаторами ---
        top_layout = QHBoxLayout()

        self.lex_bar = QProgressBar()
        self.lex_bar.setOrientation(Qt.Vertical)
        self.lex_bar.setRange(0, 100)
        self.lex_bar.setValue(0)
        self.lex_label = QLabel("LEX")
        self.lex_label.setAlignment(Qt.AlignCenter)

        self.lfl_bar = QProgressBar()
        self.lfl_bar.setOrientation(Qt.Vertical)
        self.lfl_bar.setRange(0, 100)
        self.lfl_bar.setValue(0)
        self.lfl_label = QLabel("LFL")
        self.lfl_label.setAlignment(Qt.AlignCenter)

        left_box = QVBoxLayout()
        left_box.addWidget(self.lex_bar)
        left_box.addWidget(self.lex_label)

        right_box = QVBoxLayout()
        right_box.addWidget(self.lfl_bar)
        right_box.addWidget(self.lfl_label)

        top_layout.addLayout(left_box)
        top_layout.addStretch()
        top_layout.addLayout(right_box)

        # --- Кнопка завершения игры ---
        self.end_button = QPushButton("End Game")
        self.end_button.clicked.connect(self.close_game)

        # --- Общий Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.end_button)

    # ----------------------- Игровая логика -----------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Мяч
        p.setBrush(QBrush(Qt.blue))
        p.drawEllipse(self.ball_pos[0], self.ball_pos[1], 15, 15)
        # Ракетка
        p.setBrush(QBrush(Qt.darkGray))
        p.drawRect(int(self.paddle_x), 410, int(self.paddle_width), int(self.paddle_height))
        # Счёт
        p.setPen(Qt.black)
        p.drawText(10, 20, f"Score: {self.score}")

    def update_game(self):
        """Обновление положения мяча и управление ракеткой по ЭМГ."""
        # Движение мяча
        self.ball_pos[0] += self.ball_vel[0]
        self.ball_pos[1] += self.ball_vel[1]

        # Столкновения со стенами
        if self.ball_pos[0] <= 0 or self.ball_pos[0] >= self.width() - 15:
            self.ball_vel[0] *= -1
        if self.ball_pos[1] <= 0:
            self.ball_vel[1] *= -1

        # Проверка на касание ракетки
        if self.ball_pos[1] >= 410:
            if self.paddle_x <= self.ball_pos[0] <= self.paddle_x + self.paddle_width:
                self.ball_vel[1] *= -1
                self.score += 1
            else:
                # Промах — рестарт
                self.ball_pos = [self.width()//2, self.height()//2]
                self.ball_vel = [4, 3]
                self.score = 0

        # Чтение потоков ЭМГ
        #try:
        signal, _ = self.parent_gui.stream.get_data(2)
        fs = self.parent_gui.stream.info["sfreq"]
        chlist = self.parent_gui.stream.info["ch_names"]
        
        result = {}
        
        for channel in self.parent_gui.emg_feed_window.active_chnames:
        
            idx = self.parent_gui.emg_feed_window.emg_ids[channel]
            bsl_channel = self.parent_gui.emg_feed_window.baseline_params[channel]
            result[channel] = get_online_EMG(signal[idx, :], fs, bsl_channel)
        
        # Берём среднее за короткий отрезок (сглаживание)
        lex_val = result['LEX'] if "LEX" in self.parent_gui.emg_feed_window.active_chnames else 0
        # if lex_val < 0:
        #     lex_val = 0
        lfl_val = result['LFL'] if "LFL" in self.parent_gui.emg_feed_window.active_chnames else 0
        if lfl_val < 0:
            lfl_val = 0

        # Нормализация и отображение на индикаторах
        lex_scaled = int(50 + 50 * lex_val)
        lfl_scaled = int(50 + 50 * lfl_val)
        self.lex_bar.setValue(max(0, min(100, lex_scaled)))
        self.lfl_bar.setValue(max(0, min(100, lfl_scaled)))

        # Разность управляет движением
        diff = - lex_val # + lfl_val  # >0 → вправо, <0 → влево
        print ("diff:", diff)
        self.paddle_x += diff * 10  # чувствительность
        self.paddle_x = max(0, min(self.width() - self.paddle_width, self.paddle_x))
            
        # except Exception:
        #     pass

        self.update()

    def close_game(self):
        """Остановить таймер и закрыть окно."""
        self.timer.stop()
        self.close()
