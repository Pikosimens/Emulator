# metrics HRV and EMG
from funcpack.filters import bandpass_HRV, bandpass_EMG
import numpy as np
from scipy.signal import find_peaks



# ================================= HRV ========================================

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
    


# ================================= EMG ========================================

def compute_emg_params(sig, fs, window_size=0.3, baseline = False):
    # Default bandpass 55-95 Hz, default window size 300 ms
    filtered = bandpass_EMG(sig, fs)
    
    if (len(sig)/fs) < window_size:
        raise Warning("Signal is shorter than the specified window size.")
        return None
    border = int(0.1*fs) # 100 ms border to avoid edge effects
    
    if baseline:
        
        cropped = filtered[border:-border]
        cropped = cropped - np.mean(cropped)  # remove DC offset
        mean_emg = np.mean(np.abs(cropped))
        std_emg = np.std(cropped)
        
        return {
        "mean_emg": mean_emg,
        "std_emg": std_emg,
        "cumsum_emg": cumsum_emg
        }
    
    
    cropped = filtered[border:-border]
    cropped = cropped - np.mean(cropped)  # remove DC offset
    cumsum_emg = np.sum(np.abs(cropped))
    return cumsum_emg


        
def get_baseline_EMG(sig, fs, duration=20, chunk_size=0.3):
    
    num_samples = int(duration * fs)
    # print("num_samples for baseline EMG:", num_samples)
    # print("len sig:", len(sig))
    # print(sig.shape)
    if len(sig) < num_samples:
        raise Warning("Signal is shorter than the specified baseline duration.")
        return None
    
    baseline_sig = sig[-num_samples:]
    samples_per_chunk = int(chunk_size * fs)
    chunks = np.array_split(baseline_sig, len(baseline_sig) // samples_per_chunk)
    
    cumsum_list = []
    
    for chunk in chunks:
        
        cumsum = compute_emg_params(chunk, fs)
        if cumsum is not None:
            cumsum_list.append(cumsum)
            
    mean_emg = np.mean(cumsum_list)
    std_emg = np.std(cumsum_list)
    
    params = {
        "mean_emg": mean_emg,
        "std_emg": std_emg
    }
    
    return params



def get_online_EMG(sig, fs, baseline_params, window_size=0.3):
    
    num_samples = int(window_size * fs)
    if len(sig) < num_samples:
        raise Warning("Signal is shorter than the specified window size.")
        return None
    
    window_sig = sig[-num_samples:]
    params = compute_emg_params(window_sig, fs)
    
    if baseline_params is None:
        return None
    
    # Compare with baseline
    mean_emg_change = (params - baseline_params["mean_emg"]) / baseline_params["std_emg"]
    
    return mean_emg_change