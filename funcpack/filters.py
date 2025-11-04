import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

def bandpass_HRV(sig, fs, low=0.5, high=8.0, order=3):
    nyq = 0.5 * fs
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    return filtfilt(b, a, sig)

def bandpass_EMG(sig, fs, low=55, high=95, order=3):
    nyq = 0.5 * fs
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    return filtfilt(b, a, sig)

