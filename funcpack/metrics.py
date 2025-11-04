# metrics HRV and EMG
from funcpack.filters import bandpass_HRV, bandpass_EMG
import numpy as np
from scipy.signal import find_peaks

#   HRV

def compute_heart_params(sig, fs):
    # TODO process anomalies in the signal
    filtered = bandpass_HRV(sig, fs)
    prominence = 0.3 * np.std(sig)
    peaks, _ = find_peaks(filtered, distance=fs*0.3, prominence=prominence)
    
    peak_times = peaks / fs
    rr_intervals = np.diff(peak_times)  # in seconds    
    
    if len(rr_intervals) < 2:
        return None  # Not enough peaks to compute HRV
    
    hr = int(60 / np.median(rr_intervals))  # in bpm   
    mean_rr = np.mean(rr_intervals)
    sdnn = np.std(rr_intervals)
    rmssd = np.sqrt(np.mean(np.square(np.diff(rr_intervals))))
    rmssd_corrected = rmssd / (np.mean(mean_rr) ** 3)
    
    # signal features
    signal_mean = np.mean(sig)
    signal_std = np.std(sig)
    
    return {
        "mean_rr": mean_rr,
        "sdnn": sdnn,
        "rmssd": rmssd,
        "num_peaks": len(peaks),
        "peaks":peaks,
        "hr": hr,
        "signal_mean": signal_mean,
        "signal_std": signal_std,
        "rmssd_corrected": rmssd_corrected
    }
    
    
    
    
def get_baseline_PPG(sig, fs, duration=60):
    
    num_samples = duration * fs
    if len(sig) < num_samples:
        raise ValueError("Signal is shorter than the specified baseline duration.")
    
    baseline_sig = sig[:num_samples]
    params = compute_heart_params(baseline_sig, fs)
    if params is None:
        raise ValueError("Not enough peaks detected in the baseline signal.")
    
    return params


def get_online_PPG(sig, fs, baseline_params, window_size=5):
    
    num_samples = window_size * fs
    if len(sig) < num_samples:
        raise ValueError("Signal is shorter than the specified window size.")
    
    window_sig = sig[-num_samples:]
    params = compute_heart_params(window_sig, fs)
    if params is None:
        raise ValueError("Not enough peaks detected in the current signal window.")
    # TODO process anomalies in the signal
    
    # Compare with baseline
    hr_change = params["hr"] / baseline_params["hr"]
    sdnn_change = params["sdnn"] / baseline_params["sdnn"]
    rmssd_change = params["rmssd"] / baseline_params["rmssd"]
    rmssd_corrected_change = params["rmssd_corrected"] / baseline_params["rmssd_corrected"]
    
    return {
        #"current_params": params,
        "hr_change": hr_change,
        "sdnn_change": sdnn_change,
        "rmssd_change": rmssd_change,
        "rmssd_corrected_change": rmssd_corrected_change
    }
    
    
def compute_emg_params(sig, fs):
    
    filtered = bandpass_EMG(sig, fs)
    mean_emg = np.mean(filtered)
    std_emg = np.std(filtered)
    cumsum_emg = np.sum(np.square(filtered))

    return {
        "mean_emg": mean_emg,
        "std_emg": std_emg,
        "cumsum_emg": cumsum_emg
    }
        
        
def get_baseline_EMG(sig, fs, duration=60):
    
    num_samples = duration * fs
    if len(sig) < num_samples:
        raise Warning("Signal is shorter than the specified baseline duration.")
        return None
    
    baseline_sig = sig[:num_samples]
    params = compute_emg_params(baseline_sig, fs)
    return params

def get_online_EMG(sig, fs, baseline_params, window_size=15):
    
    num_samples = window_size * fs
    if len(sig) < num_samples:
        raise Warning("Signal is shorter than the specified window size.")
        return None
    
    window_sig = sig[-num_samples:]
    params = compute_emg_params(window_sig, fs)
    
    if baseline_params is None:
        return None
    
    # Compare with baseline
    mean_emg_change = params["mean_emg"] / baseline_params["mean_emg"]
    std_emg_change = params["std_emg"] / baseline_params["std_emg"]
    cumsum_emg_change = params["cumsum_emg"] / baseline_params["cumsum_emg"]
    
    return {
        "mean_emg_change": mean_emg_change,
        "std_emg_change": std_emg_change,
        "cumsum_emg_change": cumsum_emg_change
    }