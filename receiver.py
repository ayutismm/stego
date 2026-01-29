#!/usr/bin/env python3
"""
BFSK Acoustic Receiver
Demodulates FSK audio to recover transmitted data/authentication tokens.

Supports two packet formats:
- Data mode: [START:8][UNIT_ID:4][LENGTH:8][PAYLOAD:N*8][CHECKSUM:8][END:8]
- Auth mode: [START:8][UNIT_ID:4][TOKEN:32][CHECKSUM:8][END:8]
"""

import argparse
import hashlib
import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

from scipy.io.wavfile import read as wav_read

# Default parameters (must match sender)
DEFAULT_F0 = 17000
DEFAULT_F1 = 18500
DEFAULT_BIT_DURATION = 0.08
DEFAULT_SAMPLE_RATE = 44100

START_FLAG = "10101010"
END_FLAG = "11111111"


def compute_checksum(data_bytes: bytes) -> int:
    """Compute simple 8-bit checksum (sum mod 256)."""
    return sum(data_bytes) % 256


def bits_to_bytes(bits: str) -> bytes:
    """Convert binary string to bytes."""
    byte_list = []
    for i in range(0, len(bits), 8):
        byte_str = bits[i:i+8]
        if len(byte_str) == 8:
            byte_list.append(int(byte_str, 2))
    return bytes(byte_list)


def demodulate_fsk(signal: np.ndarray, f0: float, f1: float,
                   bit_duration: float, fs: int) -> str:
    """
    Demodulate FSK signal using FFT.
    
    Splits signal into bit-length windows and compares energy at f0 vs f1.
    """
    samples_per_bit = int(bit_duration * fs)
    num_bits = len(signal) // samples_per_bit
    
    bitstream = []
    
    for i in range(num_bits):
        start = i * samples_per_bit
        end = start + samples_per_bit
        window = signal[start:end]
        
        # Apply Hanning window to reduce spectral leakage
        window = window * np.hanning(len(window))
        
        # Compute FFT
        N = len(window)
        spectrum = np.fft.fft(window)
        freqs = np.fft.fftfreq(N, 1/fs)
        magnitudes = np.abs(spectrum)
        
        # Find indices closest to f0 and f1
        idx_f0 = np.argmin(np.abs(freqs - f0))
        idx_f1 = np.argmin(np.abs(freqs - f1))
        
        # Compare magnitudes
        mag_f0 = magnitudes[idx_f0]
        mag_f1 = magnitudes[idx_f1]
        
        bit = '1' if mag_f1 > mag_f0 else '0'
        bitstream.append(bit)
    
    return ''.join(bitstream)


def find_packet_start(bitstream: str) -> int:
    """Find the START flag in the bitstream."""
    idx = bitstream.find(START_FLAG)
    return idx


def parse_data_packet(bitstream: str, start_idx: int) -> dict:
    """
    Parse data mode packet.
    
    Format: [START:8][UNIT_ID:4][LENGTH:8][PAYLOAD:N*8][CHECKSUM:8][END:8]
    """
    pos = start_idx + 8  # Skip START
    
    # Unit ID: 4 bits
    unit_id = int(bitstream[pos:pos+4], 2)
    pos += 4
    
    # Length: 8 bits
    length = int(bitstream[pos:pos+8], 2)
    pos += 8
    
    # Payload: length * 8 bits
    payload_bits = bitstream[pos:pos+(length*8)]
    pos += length * 8
    
    # Checksum: 8 bits
    checksum_received = int(bitstream[pos:pos+8], 2)
    pos += 8
    
    # End flag: 8 bits
    end_flag = bitstream[pos:pos+8]
    
    # Convert payload to bytes and text
    payload_bytes = bits_to_bytes(payload_bits)
    try:
        payload_text = payload_bytes.decode('utf-8')
    except:
        payload_text = payload_bytes.hex()
    
    # Verify checksum
    computed_checksum = compute_checksum(payload_bytes)
    checksum_valid = (checksum_received == computed_checksum)
    
    # Verify end flag
    end_valid = (end_flag == END_FLAG)
    
    return {
        'mode': 'data',
        'unit_id': unit_id,
        'payload': payload_text,
        'payload_bytes': payload_bytes,
        'checksum_received': checksum_received,
        'checksum_computed': computed_checksum,
        'checksum_valid': checksum_valid,
        'end_valid': end_valid,
        'valid': checksum_valid and end_valid
    }


def parse_auth_packet(bitstream: str, start_idx: int, expected_secret: str = None) -> dict:
    """
    Parse auth mode packet.
    
    Format: [START:8][UNIT_ID:4][TOKEN:32][CHECKSUM:8][END:8]
    """
    pos = start_idx + 8  # Skip START
    
    # Unit ID: 4 bits
    unit_id = int(bitstream[pos:pos+4], 2)
    pos += 4
    
    # Token: 32 bits
    token_bits = bitstream[pos:pos+32]
    token_int = int(token_bits, 2)
    token_hex = format(token_int, '08x')
    pos += 32
    
    # Checksum: 8 bits
    checksum_received = int(bitstream[pos:pos+8], 2)
    pos += 8
    
    # End flag: 8 bits
    end_flag = bitstream[pos:pos+8]
    
    # Verify checksum
    token_bytes = token_int.to_bytes(4, 'big')
    computed_checksum = compute_checksum(token_bytes)
    checksum_valid = (checksum_received == computed_checksum)
    
    # Verify end flag
    end_valid = (end_flag == END_FLAG)
    
    # Verify token against expected secret if provided
    auth_valid = None
    if expected_secret:
        expected_token = hashlib.sha256(expected_secret.encode()).hexdigest()[:8]
        auth_valid = (token_hex == expected_token)
    
    return {
        'mode': 'auth',
        'unit_id': unit_id,
        'token': token_hex,
        'checksum_received': checksum_received,
        'checksum_computed': computed_checksum,
        'checksum_valid': checksum_valid,
        'end_valid': end_valid,
        'auth_valid': auth_valid,
        'valid': checksum_valid and end_valid
    }


def record_audio(duration: float, fs: int) -> np.ndarray:
    """Record audio from microphone."""
    if not HAS_SOUNDDEVICE:
        raise ImportError("sounddevice not installed. Use --input to read from WAV file.")
    
    print(f"[RECORDING] Recording for {duration} seconds...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float64')
    sd.wait()
    print("[RECORDING] Done.")
    return recording[:, 0]


def load_wav(filepath: str, target_fs: int) -> np.ndarray:
    """Load audio from WAV file."""
    fs, data = wav_read(filepath)
    
    # Convert to mono if stereo
    if len(data.shape) > 1:
        data = data[:, 0]
    
    # Normalize to float
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    
    if fs != target_fs:
        print(f"[WARNING] WAV sample rate ({fs}) differs from expected ({target_fs})")
    
    return data


def main():
    parser = argparse.ArgumentParser(
        description="BFSK Acoustic Receiver - Decode FSK audio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Decode from WAV file (data mode)
  python receiver.py --input packet.wav
  
  # Decode from WAV file (auth mode with verification)
  python receiver.py --input packet.wav --auth-mode --secret "my_secret"
  
  # Record from microphone
  python receiver.py --record 6
        """
    )
    
    parser.add_argument('--input', type=str, default=None,
                        help='Input WAV file to decode')
    parser.add_argument('--record', type=float, default=None,
                        help='Record duration in seconds (requires sounddevice)')
    parser.add_argument('--auth-mode', action='store_true',
                        help='Parse as 32-bit auth token packet')
    parser.add_argument('--secret', type=str, default=None,
                        help='Expected secret for auth verification')
    parser.add_argument('--f0', type=float, default=DEFAULT_F0,
                        help=f'Frequency for bit 0 (default: {DEFAULT_F0} Hz)')
    parser.add_argument('--f1', type=float, default=DEFAULT_F1,
                        help=f'Frequency for bit 1 (default: {DEFAULT_F1} Hz)')
    parser.add_argument('--bit-duration', type=float, default=DEFAULT_BIT_DURATION,
                        help=f'Bit duration in seconds (default: {DEFAULT_BIT_DURATION})')
    parser.add_argument('--sample-rate', type=int, default=DEFAULT_SAMPLE_RATE,
                        help=f'Sample rate (default: {DEFAULT_SAMPLE_RATE} Hz)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show decoded bitstream')
    
    args = parser.parse_args()
    
    # Get audio data
    if args.input:
        print(f"[INFO] Loading {args.input}")
        signal = load_wav(args.input, args.sample_rate)
    elif args.record:
        signal = record_audio(args.record, args.sample_rate)
    else:
        parser.error("Specify --input or --record")
    
    print(f"[INFO] Signal length: {len(signal)} samples ({len(signal)/args.sample_rate:.2f} seconds)")
    print(f"[INFO] Frequencies: f0={args.f0} Hz, f1={args.f1} Hz")
    
    # Demodulate
    bitstream = demodulate_fsk(signal, args.f0, args.f1, 
                               args.bit_duration, args.sample_rate)
    
    if args.verbose:
        print(f"[DEBUG] Bitstream ({len(bitstream)} bits): {bitstream}")
    
    # Find packet start
    start_idx = find_packet_start(bitstream)
    
    if start_idx < 0:
        print("[ERROR] START flag not found in signal")
        return
    
    print(f"[INFO] START flag found at bit {start_idx}")
    
    # Parse packet
    if args.auth_mode:
        result = parse_auth_packet(bitstream, start_idx, args.secret)
    else:
        result = parse_data_packet(bitstream, start_idx)
    
    # Display results
    print("\n" + "="*50)
    print("DECODED PACKET")
    print("="*50)
    print(f"Mode: {result['mode'].upper()}")
    print(f"Unit ID: {result['unit_id']}")
    
    if result['mode'] == 'data':
        print(f"Payload: {result['payload']}")
    else:
        print(f"Token: {result['token']}")
    
    print(f"Checksum: received={result['checksum_received']}, computed={result['checksum_computed']}")
    print(f"Checksum Valid: {result['checksum_valid']}")
    print(f"End Flag Valid: {result['end_valid']}")
    
    print("="*50)
    
    if result['valid']:
        if result['mode'] == 'auth' and result['auth_valid'] is not None:
            if result['auth_valid']:
                print("✓ ACCESS GRANTED")
            else:
                print("✗ ACCESS DENIED (token mismatch)")
        else:
            print("✓ PACKET VALID")
    else:
        print("✗ PACKET INVALID")


if __name__ == "__main__":
    main()
