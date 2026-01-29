#!/usr/bin/env python3
"""
BFSK Acoustic Communication System - GUI
Graphical interface for sending and receiving FSK-modulated audio.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import numpy as np
import hashlib

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

# Matplotlib for visualization
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    
from scipy.io.wavfile import write as wav_write, read as wav_read
from scipy import signal as scipy_signal

# Default parameters
DEFAULT_F0 = 17000
DEFAULT_F1 = 18500
DEFAULT_BIT_DURATION = 0.08
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_REPEAT = 1

# Preamble and flags
PREAMBLE = "10101010101010101010101010101010"  # 32 bits
START_FLAG = "11001100"  # Distinct from preamble
END_FLAG = "11111111"


class BFSKApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BFSK Acoustic Communication")
        self.root.geometry("900x800")
        self.root.resizable(True, True)
        
        # Style configuration
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'))
        style.configure('Header.TLabel', font=('Segoe UI', 11, 'bold'))
        
        self.is_recording = False
        self.recorded_signal = None
        
        self.create_widgets()
        self.refresh_devices()
    
    def create_widgets(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = ttk.Label(main_frame, text="BFSK Acoustic Communication", style='Title.TLabel')
        title.pack(pady=(0, 15))
        
        # ===== DEVICE SELECTION =====
        device_frame = ttk.LabelFrame(main_frame, text="Audio Devices", padding="10")
        device_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Output device
        ttk.Label(device_frame, text="Playback Device:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.output_device_var = tk.StringVar()
        self.output_device_combo = ttk.Combobox(device_frame, textvariable=self.output_device_var, 
                                                 state='readonly', width=50)
        self.output_device_combo.grid(row=0, column=1, padx=5, pady=2)
        
        # Input device
        ttk.Label(device_frame, text="Recording Device:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.input_device_var = tk.StringVar()
        self.input_device_combo = ttk.Combobox(device_frame, textvariable=self.input_device_var,
                                                state='readonly', width=50)
        self.input_device_combo.grid(row=1, column=1, padx=5, pady=2)
        
        # Refresh button
        ttk.Button(device_frame, text="Refresh", command=self.refresh_devices).grid(row=0, column=2, rowspan=2, padx=10)
        
        # ===== PARAMETERS =====
        param_frame = ttk.LabelFrame(main_frame, text="Parameters", padding="10")
        param_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Row 1
        ttk.Label(param_frame, text="F0 (Hz):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.f0_var = tk.StringVar(value=str(DEFAULT_F0))
        ttk.Entry(param_frame, textvariable=self.f0_var, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(param_frame, text="F1 (Hz):").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.f1_var = tk.StringVar(value=str(DEFAULT_F1))
        ttk.Entry(param_frame, textvariable=self.f1_var, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(param_frame, text="Bit Duration (s):").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.bit_duration_var = tk.StringVar(value=str(DEFAULT_BIT_DURATION))
        ttk.Entry(param_frame, textvariable=self.bit_duration_var, width=10).grid(row=0, column=5, padx=5)
        
        # Row 2 - Repeat factor
        ttk.Label(param_frame, text="Repeat (noise):").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.repeat_var = tk.StringVar(value=str(DEFAULT_REPEAT))
        ttk.Entry(param_frame, textvariable=self.repeat_var, width=10).grid(row=1, column=1, padx=5)
        
        # ===== SENDER SECTION =====
        sender_frame = ttk.LabelFrame(main_frame, text="Sender", padding="10")
        sender_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Mode selection
        self.mode_var = tk.StringVar(value="data")
        ttk.Radiobutton(sender_frame, text="Data Mode", variable=self.mode_var, 
                        value="data", command=self.toggle_mode).grid(row=0, column=0, padx=5)
        ttk.Radiobutton(sender_frame, text="Auth Mode", variable=self.mode_var,
                        value="auth", command=self.toggle_mode).grid(row=0, column=1, padx=5)
        
        # Unit ID
        ttk.Label(sender_frame, text="Unit ID (0-15):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.unit_id_var = tk.StringVar(value="1")
        ttk.Entry(sender_frame, textvariable=self.unit_id_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # Data/Secret input
        self.data_label = ttk.Label(sender_frame, text="Data:")
        self.data_label.grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.data_var = tk.StringVar()
        self.data_entry = ttk.Entry(sender_frame, textvariable=self.data_var, width=40)
        self.data_entry.grid(row=2, column=1, columnspan=3, sticky=tk.W, padx=5)
        
        # Buttons
        btn_frame = ttk.Frame(sender_frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=10)
        
        ttk.Button(btn_frame, text="Generate WAV", command=self.generate_wav).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Play Audio", command=self.play_audio).pack(side=tk.LEFT, padx=5)
        
        # ===== RECEIVER SECTION =====
        receiver_frame = ttk.LabelFrame(main_frame, text="Receiver", padding="10")
        receiver_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Duration
        ttk.Label(receiver_frame, text="Record Duration (s):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.duration_var = tk.StringVar(value="6")
        ttk.Entry(receiver_frame, textvariable=self.duration_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Auth secret for verification
        ttk.Label(receiver_frame, text="Expected Secret (auth):").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.rx_secret_var = tk.StringVar()
        ttk.Entry(receiver_frame, textvariable=self.rx_secret_var, width=20).grid(row=0, column=3, sticky=tk.W, padx=5)
        
        # Buttons
        rx_btn_frame = ttk.Frame(receiver_frame)
        rx_btn_frame.grid(row=1, column=0, columnspan=4, pady=10)
        
        self.record_btn = ttk.Button(rx_btn_frame, text="Start Recording", command=self.toggle_recording)
        self.record_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(rx_btn_frame, text="Load WAV", command=self.load_wav).pack(side=tk.LEFT, padx=5)
        ttk.Button(rx_btn_frame, text="Decode", command=self.decode_signal).pack(side=tk.LEFT, padx=5)
        
        # ===== OUTPUT LOG =====
        log_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=10, font=('Consolas', 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # ===== VISUALIZATION =====
        if HAS_MATPLOTLIB:
            viz_frame = ttk.LabelFrame(main_frame, text="Audio Visualization", padding="5")
            viz_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            
            # Create matplotlib figure with two subplots
            self.fig = Figure(figsize=(8, 3), dpi=100)
            self.fig.patch.set_facecolor('#2b2b2b')
            
            # Waveform subplot
            self.ax_wave = self.fig.add_subplot(121)
            self.ax_wave.set_facecolor('#1e1e1e')
            self.ax_wave.set_title('Waveform', color='white', fontsize=10)
            self.ax_wave.set_xlabel('Time (s)', color='#aaa', fontsize=8)
            self.ax_wave.set_ylabel('Amplitude', color='#aaa', fontsize=8)
            self.ax_wave.tick_params(colors='#888', labelsize=7)
            for spine in self.ax_wave.spines.values():
                spine.set_color('#444')
            
            # Spectrogram subplot
            self.ax_spec = self.fig.add_subplot(122)
            self.ax_spec.set_facecolor('#1e1e1e')
            self.ax_spec.set_title('Spectrogram', color='white', fontsize=10)
            self.ax_spec.set_xlabel('Time (s)', color='#aaa', fontsize=8)
            self.ax_spec.set_ylabel('Frequency (kHz)', color='#aaa', fontsize=8)
            self.ax_spec.tick_params(colors='#888', labelsize=7)
            for spine in self.ax_spec.spines.values():
                spine.set_color('#444')
            
            self.fig.tight_layout()
            
            # Embed in tkinter
            self.canvas = FigureCanvasTkAgg(self.fig, master=viz_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
    
    def toggle_mode(self):
        if self.mode_var.get() == "auth":
            self.data_label.config(text="Secret:")
        else:
            self.data_label.config(text="Data:")
    
    def refresh_devices(self):
        if not HAS_SOUNDDEVICE:
            messagebox.showerror("Error", "sounddevice not installed")
            return
        
        devices = sd.query_devices()
        
        output_devices = []
        input_devices = []
        
        for i, dev in enumerate(devices):
            name = f"{i}: {dev['name']}"
            if dev['max_output_channels'] > 0:
                output_devices.append(name)
            if dev['max_input_channels'] > 0:
                input_devices.append(name)
        
        self.output_device_combo['values'] = output_devices
        self.input_device_combo['values'] = input_devices
        
        # Set defaults
        if output_devices:
            default_out = sd.query_devices(kind='output')
            for od in output_devices:
                if default_out['name'] in od:
                    self.output_device_var.set(od)
                    break
            else:
                self.output_device_var.set(output_devices[0])
        
        if input_devices:
            default_in = sd.query_devices(kind='input')
            for id_ in input_devices:
                if default_in['name'] in id_:
                    self.input_device_var.set(id_)
                    break
            else:
                self.input_device_var.set(input_devices[0])
        
        self.log("[INFO] Devices refreshed")
    
    def get_device_index(self, device_str):
        """Extract device index from combo string."""
        if device_str:
            return int(device_str.split(":")[0])
        return None
    
    def get_params(self):
        """Get current parameters."""
        return {
            'f0': float(self.f0_var.get()),
            'f1': float(self.f1_var.get()),
            'bit_duration': float(self.bit_duration_var.get()),
            'fs': DEFAULT_SAMPLE_RATE
        }
    
    def generate_cpfsk(self, bitstream, params):
        """Generate CPFSK waveform."""
        samples_per_bit = int(params['bit_duration'] * params['fs'])
        total_samples = len(bitstream) * samples_per_bit
        
        signal = np.zeros(total_samples)
        phase = 0.0
        
        for i, bit in enumerate(bitstream):
            freq = params['f1'] if bit == '1' else params['f0']
            start_idx = i * samples_per_bit
            
            for j in range(samples_per_bit):
                signal[start_idx + j] = np.sin(phase)
                phase += 2 * np.pi * freq / params['fs']
                if phase > 2 * np.pi:
                    phase -= 2 * np.pi
        
        return signal
    
    def build_packet(self, unit_id, payload, is_auth=False, secret=None):
        """Build packet bitstream."""
        unit_bits = format(unit_id & 0xF, '04b')
        
        if is_auth:
            token_hex = hashlib.sha256(secret.encode()).hexdigest()[:8]
            token_int = int(token_hex, 16)
            payload_bits = format(token_int, '032b')
            data_bytes = token_int.to_bytes(4, 'big')
        else:
            payload_bytes = payload.encode('utf-8')
            payload_bits = ''.join(format(b, '08b') for b in payload_bytes)
            length_bits = format(len(payload_bytes) & 0xFF, '08b')
            payload_bits = length_bits + payload_bits
            data_bytes = payload_bytes
        
        checksum = sum(data_bytes) % 256
        checksum_bits = format(checksum, '08b')
        
        # Build packet with preamble
        packet = PREAMBLE + START_FLAG + unit_bits + payload_bits + checksum_bits + END_FLAG
        
        # Apply bit repetition if requested
        repeat = int(self.repeat_var.get())
        if repeat > 1:
            packet = ''.join(bit * repeat for bit in packet)
        
        return packet
    
    def generate_wav(self):
        """Generate and save WAV file."""
        try:
            unit_id = int(self.unit_id_var.get())
            data = self.data_var.get()
            is_auth = self.mode_var.get() == "auth"
            
            if not data:
                messagebox.showerror("Error", "Please enter data/secret")
                return
            
            packet = self.build_packet(unit_id, data, is_auth, data if is_auth else None)
            params = self.get_params()
            
            signal = self.generate_cpfsk(packet, params)
            signal = signal / np.max(np.abs(signal))
            signal_int16 = (signal * 32767).astype(np.int16)
            
            filepath = filedialog.asksaveasfilename(
                defaultextension=".wav",
                filetypes=[("WAV files", "*.wav")],
                initialfile="packet.wav"
            )
            
            if filepath:
                wav_write(filepath, params['fs'], signal_int16)
                self.log(f"[SUCCESS] Saved: {filepath}")
                self.log(f"[INFO] Packet: {len(packet)} bits, {len(packet) * params['bit_duration']:.2f}s")
                self.current_signal = signal
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def play_audio(self):
        """Play generated audio."""
        if not HAS_SOUNDDEVICE:
            messagebox.showerror("Error", "sounddevice not installed")
            return
        
        try:
            unit_id = int(self.unit_id_var.get())
            data = self.data_var.get()
            is_auth = self.mode_var.get() == "auth"
            
            if not data:
                messagebox.showerror("Error", "Please enter data/secret")
                return
            
            packet = self.build_packet(unit_id, data, is_auth, data if is_auth else None)
            params = self.get_params()
            
            signal = self.generate_cpfsk(packet, params)
            signal = signal / np.max(np.abs(signal))
            
            device_idx = self.get_device_index(self.output_device_var.get())
            
            self.log(f"[INFO] Playing on device {device_idx}...")
            
            def play_thread():
                sd.play(signal, params['fs'], device=device_idx)
                sd.wait()
                self.log("[INFO] Playback complete")
            
            threading.Thread(target=play_thread, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def toggle_recording(self):
        """Start/stop recording."""
        if not HAS_SOUNDDEVICE:
            messagebox.showerror("Error", "sounddevice not installed")
            return
        
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """Start audio recording."""
        try:
            duration = float(self.duration_var.get())
            params = self.get_params()
            device_idx = self.get_device_index(self.input_device_var.get())
            
            self.is_recording = True
            self.record_btn.config(text="Stop Recording")
            self.log(f"[INFO] Recording from device {device_idx} for {duration}s...")
            
            def record_thread():
                try:
                    self.recorded_signal = sd.rec(
                        int(duration * params['fs']),
                        samplerate=params['fs'],
                        channels=1,
                        device=device_idx,
                        dtype='float64'
                    )
                    sd.wait()
                    self.recorded_signal = self.recorded_signal[:, 0]
                    self.log("[INFO] Recording complete")
                    # Update visualization on main thread
                    self.root.after(0, lambda: self.update_visualization(self.recorded_signal, params['fs']))
                except Exception as e:
                    self.log(f"[ERROR] {e}")
                finally:
                    self.is_recording = False
                    self.root.after(0, lambda: self.record_btn.config(text="Start Recording"))
            
            threading.Thread(target=record_thread, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.is_recording = False
            self.record_btn.config(text="Start Recording")
    
    def stop_recording(self):
        """Stop recording."""
        sd.stop()
        self.is_recording = False
        self.record_btn.config(text="Start Recording")
        self.log("[INFO] Recording stopped")
    
    def load_wav(self):
        """Load WAV file."""
        filepath = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if filepath:
            try:
                fs, data = wav_read(filepath)
                if len(data.shape) > 1:
                    data = data[:, 0]
                if data.dtype == np.int16:
                    data = data.astype(np.float64) / 32768.0
                self.recorded_signal = data
                self.log(f"[INFO] Loaded: {filepath}")
                self.log(f"[INFO] {len(data)} samples, {len(data)/fs:.2f}s")
                self.update_visualization(data, fs)
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def update_visualization(self, signal, fs):
        """Update waveform and spectrogram displays."""
        if not HAS_MATPLOTLIB:
            self.log("[WARN] Matplotlib not available for visualization")
            return
        
        if not hasattr(self, 'ax_wave') or not hasattr(self, 'ax_spec'):
            self.log("[WARN] Visualization axes not initialized")
            return
        
        self.log("[INFO] Updating visualization...")
        
        try:
            # Clear previous plots
            self.ax_wave.clear()
            self.ax_spec.clear()
            
            # Waveform
            duration = len(signal) / fs
            time_axis = np.linspace(0, duration, len(signal))
            
            # Downsample for display if too many points
            max_points = 10000
            if len(signal) > max_points:
                step = len(signal) // max_points
                time_display = time_axis[::step]
                signal_display = signal[::step]
            else:
                time_display = time_axis
                signal_display = signal
            
            self.ax_wave.plot(time_display, signal_display, color='#00ff88', linewidth=0.5)
            self.ax_wave.set_title('Waveform', color='white', fontsize=10)
            self.ax_wave.set_xlabel('Time (s)', color='#aaa', fontsize=8)
            self.ax_wave.set_ylabel('Amplitude', color='#aaa', fontsize=8)
            self.ax_wave.set_facecolor('#1e1e1e')
            self.ax_wave.tick_params(colors='#888', labelsize=7)
            self.ax_wave.set_xlim(0, duration)
            for spine in self.ax_wave.spines.values():
                spine.set_color('#444')
            
            # Mark F0 and F1 frequency bands
            f0 = float(self.f0_var.get())
            f1 = float(self.f1_var.get())
            
            # Spectrogram
            nperseg = min(1024, len(signal) // 4)
            if nperseg > 0:
                f, t, Sxx = scipy_signal.spectrogram(signal, fs, nperseg=nperseg, noverlap=nperseg//2)
                
                # Focus on frequency range around F0 and F1
                freq_mask = (f >= 0) & (f <= 25000)  # Up to 25kHz
                f_display = f[freq_mask] / 1000  # Convert to kHz
                Sxx_display = Sxx[freq_mask, :]
                
                # Log scale for better visualization
                Sxx_db = 10 * np.log10(Sxx_display + 1e-10)
                
                self.ax_spec.pcolormesh(t, f_display, Sxx_db, shading='gouraud', cmap='viridis')
                
                # Mark target frequencies
                self.ax_spec.axhline(y=f0/1000, color='#ff4444', linestyle='--', linewidth=1, alpha=0.7, label=f'F0={f0/1000:.1f}kHz')
                self.ax_spec.axhline(y=f1/1000, color='#44ff44', linestyle='--', linewidth=1, alpha=0.7, label=f'F1={f1/1000:.1f}kHz')
                self.ax_spec.legend(loc='upper right', fontsize=7, facecolor='#2b2b2b', edgecolor='#444', labelcolor='white')
            
            self.ax_spec.set_title('Spectrogram', color='white', fontsize=10)
            self.ax_spec.set_xlabel('Time (s)', color='#aaa', fontsize=8)
            self.ax_spec.set_ylabel('Frequency (kHz)', color='#aaa', fontsize=8)
            self.ax_spec.set_facecolor('#1e1e1e')
            self.ax_spec.tick_params(colors='#888', labelsize=7)
            for spine in self.ax_spec.spines.values():
                spine.set_color('#444')
            
            self.fig.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            self.log(f"[WARN] Visualization error: {e}")
    
    def demodulate_fsk(self, signal, params):
        """Demodulate FSK signal."""
        samples_per_bit = int(params['bit_duration'] * params['fs'])
        num_bits = len(signal) // samples_per_bit
        
        bitstream = []
        for i in range(num_bits):
            start = i * samples_per_bit
            end = start + samples_per_bit
            window = signal[start:end] * np.hanning(samples_per_bit)
            
            spectrum = np.fft.fft(window)
            freqs = np.fft.fftfreq(len(window), 1/params['fs'])
            magnitudes = np.abs(spectrum)
            
            idx_f0 = np.argmin(np.abs(freqs - params['f0']))
            idx_f1 = np.argmin(np.abs(freqs - params['f1']))
            
            bit = '1' if magnitudes[idx_f1] > magnitudes[idx_f0] else '0'
            bitstream.append(bit)
        
        return ''.join(bitstream)
    
    def decode_signal(self):
        """Decode recorded/loaded signal."""
        if self.recorded_signal is None:
            messagebox.showerror("Error", "No signal to decode. Record or load a WAV file first.")
            return
        
        try:
            params = self.get_params()
            bitstream = self.demodulate_fsk(self.recorded_signal, params)
            
            # Apply majority voting if repeat > 1
            repeat = int(self.repeat_var.get())
            if repeat > 1:
                voted = []
                for i in range(0, len(bitstream), repeat):
                    group = bitstream[i:i+repeat]
                    ones = group.count('1')
                    zeros = group.count('0')
                    voted.append('1' if ones > zeros else '0')
                bitstream = ''.join(voted)
                self.log(f"[INFO] Applied majority voting (repeat={repeat})")
            
            # Find start (skip preamble region)
            preamble_bits = 32 // repeat if repeat > 1 else 32
            search_start = max(0, preamble_bits - 8)
            start_idx = bitstream.find(START_FLAG, search_start)
            if start_idx < 0:
                start_idx = bitstream.find(START_FLAG)
            if start_idx < 0:
                self.log("[ERROR] START flag not found")
                return
            
            self.log(f"[INFO] START flag at bit {start_idx}")
            
            pos = start_idx + 8
            unit_id = int(bitstream[pos:pos+4], 2)
            pos += 4
            
            # Try to determine mode by checking if it's a valid auth packet
            rx_secret = self.rx_secret_var.get()
            
            if rx_secret:
                # Auth mode
                token_bits = bitstream[pos:pos+32]
                token_int = int(token_bits, 2)
                token_hex = format(token_int, '08x')
                pos += 32
                
                checksum_rx = int(bitstream[pos:pos+8], 2)
                pos += 8
                end_flag = bitstream[pos:pos+8]
                
                token_bytes = token_int.to_bytes(4, 'big')
                checksum_calc = sum(token_bytes) % 256
                
                expected_token = hashlib.sha256(rx_secret.encode()).hexdigest()[:8]
                
                self.log("=" * 40)
                self.log("DECODED PACKET (AUTH MODE)")
                self.log("=" * 40)
                self.log(f"Unit ID: {unit_id}")
                self.log(f"Token: {token_hex}")
                self.log(f"Checksum: rx={checksum_rx}, calc={checksum_calc}")
                self.log(f"End Flag Valid: {end_flag == END_FLAG}")
                
                if checksum_rx == checksum_calc and end_flag == END_FLAG:
                    if token_hex == expected_token:
                        self.log("✓ ACCESS GRANTED")
                    else:
                        self.log("✗ ACCESS DENIED (token mismatch)")
                else:
                    self.log("✗ PACKET INVALID")
            else:
                # Data mode
                length = int(bitstream[pos:pos+8], 2)
                pos += 8
                
                payload_bits = bitstream[pos:pos+(length*8)]
                pos += length * 8
                
                checksum_rx = int(bitstream[pos:pos+8], 2)
                pos += 8
                end_flag = bitstream[pos:pos+8]
                
                payload_bytes = bytes([int(payload_bits[i:i+8], 2) for i in range(0, len(payload_bits), 8)])
                try:
                    payload_text = payload_bytes.decode('utf-8')
                except:
                    payload_text = payload_bytes.hex()
                
                checksum_calc = sum(payload_bytes) % 256
                
                self.log("=" * 40)
                self.log("DECODED PACKET (DATA MODE)")
                self.log("=" * 40)
                self.log(f"Unit ID: {unit_id}")
                self.log(f"Payload: {payload_text}")
                self.log(f"Checksum: rx={checksum_rx}, calc={checksum_calc}")
                self.log(f"End Flag Valid: {end_flag == END_FLAG}")
                
                if checksum_rx == checksum_calc and end_flag == END_FLAG:
                    self.log("✓ PACKET VALID")
                else:
                    self.log("✗ PACKET INVALID")
                    
        except Exception as e:
            self.log(f"[ERROR] {e}")


def main():
    root = tk.Tk()
    app = BFSKApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
