#!/usr/bin/env python3
"""
BFSK Acoustic Sender
Encodes short text/data into a BFSK audio signal for acoustic transmission.

Packet Structure: [START:8][UNIT_ID:4][LENGTH:8][PAYLOAD:N*8][CHECKSUM:8][END:8]
"""

import argparse
import hashlib
import numpy as np
from scipy.io.wavfile import write

# Default parameters
DEFAULT_F0 = 17000       # Frequency for bit '0' (Hz)
DEFAULT_F1 = 18500       # Frequency for bit '1' (Hz)
DEFAULT_BIT_DURATION = 0.08  # 80ms per bit
DEFAULT_SAMPLE_RATE = 44100  # 44.1 kHz
DEFAULT_REPEAT = 1       # Bit repetition factor

# Preamble: alternating pattern for receiver sync
PREAMBLE = "10101010101010101010101010101010"  # 32 bits
# START_FLAG must be distinct from preamble pattern
START_FLAG = "11001100"  # Different from alternating 10101010
END_FLAG = "11111111"


def text_to_bits(text: str) -> str:
    """Convert text string to binary string."""
    return ''.join(format(ord(c), '08b') for c in text)


def compute_checksum(data_bytes: bytes) -> int:
    """Compute simple 8-bit checksum (sum mod 256)."""
    return sum(data_bytes) % 256


def generate_cpfsk(bitstream: str, f0: float, f1: float, 
                   bit_duration: float, fs: int) -> np.ndarray:
    """
    Generate continuous-phase FSK (CPFSK) waveform.
    
    Uses cumulative phase to avoid discontinuities at bit boundaries.
    """
    samples_per_bit = int(bit_duration * fs)
    total_samples = len(bitstream) * samples_per_bit
    
    signal = np.zeros(total_samples)
    phase = 0.0
    
    for i, bit in enumerate(bitstream):
        freq = f1 if bit == '1' else f0
        start_idx = i * samples_per_bit
        
        for j in range(samples_per_bit):
            signal[start_idx + j] = np.sin(phase)
            phase += 2 * np.pi * freq / fs
            # Keep phase bounded to avoid numerical issues
            if phase > 2 * np.pi:
                phase -= 2 * np.pi
    
    return signal


def build_packet(unit_id: int, payload: str) -> str:
    """
    Build complete packet bitstream.
    
    Structure: [START:8][UNIT_ID:4][LENGTH:8][PAYLOAD:N*8][CHECKSUM:8][END:8]
    """
    # Unit ID: 4 bits (0-15)
    unit_bits = format(unit_id & 0xF, '04b')
    
    # Payload: convert to bytes then bits
    payload_bytes = payload.encode('utf-8')
    payload_bits = ''.join(format(b, '08b') for b in payload_bytes)
    
    # Length: 8 bits (0-255 bytes)
    length_bits = format(len(payload_bytes) & 0xFF, '08b')
    
    # Checksum: 8-bit sum of payload bytes
    checksum = compute_checksum(payload_bytes)
    checksum_bits = format(checksum, '08b')
    
    # Assemble packet (preamble + packet)
    packet = PREAMBLE + START_FLAG + unit_bits + length_bits + payload_bits + checksum_bits + END_FLAG
    
    return packet


def build_auth_packet(unit_id: int, secret: str) -> str:
    """
    Build authentication packet with SHA-256 token.
    
    Structure: [START:8][UNIT_ID:4][TOKEN:32][CHECKSUM:8][END:8]
    """
    # Unit ID: 4 bits
    unit_bits = format(unit_id & 0xF, '04b')
    
    # Token: first 8 hex chars of SHA-256 hash -> 32 bits
    token_hex = hashlib.sha256(secret.encode()).hexdigest()[:8]
    token_int = int(token_hex, 16)
    token_bits = format(token_int, '032b')
    
    # Token as 4 bytes for checksum
    token_bytes = token_int.to_bytes(4, 'big')
    checksum = compute_checksum(token_bytes)
    checksum_bits = format(checksum, '08b')
    
    # Assemble packet (preamble + packet)
    packet = PREAMBLE + START_FLAG + unit_bits + token_bits + checksum_bits + END_FLAG
    
    return packet


def main():
    parser = argparse.ArgumentParser(
        description="BFSK Acoustic Sender - Encode data into FSK audio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send custom message
  python sender.py --unit-id 1 --data "Hello"
  
  # Send authentication token
  python sender.py --unit-id 1 --secret "my_secret" --auth-mode
  
  # Custom frequencies
  python sender.py --unit-id 1 --data "Test" --f0 16000 --f1 17500
        """
    )
    
    parser.add_argument('--unit-id', type=int, default=1,
                        help='Unit ID (0-15, default: 1)')
    parser.add_argument('--data', type=str, default=None,
                        help='Short text/data to transmit (max 255 bytes)')
    parser.add_argument('--secret', type=str, default=None,
                        help='Secret passphrase for auth token')
    parser.add_argument('--auth-mode', action='store_true',
                        help='Use 32-bit auth token mode instead of data mode')
    parser.add_argument('--output', type=str, default='packet.wav',
                        help='Output WAV file (default: packet.wav)')
    parser.add_argument('--f0', type=float, default=DEFAULT_F0,
                        help=f'Frequency for bit 0 (default: {DEFAULT_F0} Hz)')
    parser.add_argument('--f1', type=float, default=DEFAULT_F1,
                        help=f'Frequency for bit 1 (default: {DEFAULT_F1} Hz)')
    parser.add_argument('--bit-duration', type=float, default=DEFAULT_BIT_DURATION,
                        help=f'Bit duration in seconds (default: {DEFAULT_BIT_DURATION})')
    parser.add_argument('--sample-rate', type=int, default=DEFAULT_SAMPLE_RATE,
                        help=f'Sample rate (default: {DEFAULT_SAMPLE_RATE} Hz)')
    parser.add_argument('--repeat', type=int, default=DEFAULT_REPEAT,
                        help=f'Repeat each bit N times for noise resistance (default: {DEFAULT_REPEAT})')
    
    args = parser.parse_args()
    
    # Validate inputs
    if args.auth_mode:
        if not args.secret:
            parser.error("--secret is required in auth mode")
        packet = build_auth_packet(args.unit_id, args.secret)
        print(f"[AUTH MODE] Unit ID: {args.unit_id}")
        print(f"[AUTH MODE] Token derived from secret")
    else:
        if not args.data:
            parser.error("--data is required (or use --auth-mode with --secret)")
        if len(args.data.encode('utf-8')) > 255:
            parser.error("Data too long (max 255 bytes)")
        packet = build_packet(args.unit_id, args.data)
        print(f"[DATA MODE] Unit ID: {args.unit_id}")
        print(f"[DATA MODE] Payload: {args.data}")
    
    # Apply bit repetition if requested
    if args.repeat > 1:
        packet = ''.join(bit * args.repeat for bit in packet)
        print(f"[INFO] Bit repetition: {args.repeat}x")
    
    print(f"[INFO] Packet length: {len(packet)} bits (including preamble)")
    print(f"[INFO] Frequencies: f0={args.f0} Hz, f1={args.f1} Hz")
    print(f"[INFO] Bit duration: {args.bit_duration * 1000:.0f} ms")
    print(f"[INFO] Total TX time: {len(packet) * args.bit_duration:.2f} seconds")
    
    # Generate CPFSK signal
    signal = generate_cpfsk(
        packet, 
        args.f0, args.f1, 
        args.bit_duration, 
        args.sample_rate
    )
    
    # Normalize to 16-bit PCM
    signal = signal / np.max(np.abs(signal))  # Normalize to [-1, 1]
    signal_int16 = (signal * 32767).astype(np.int16)
    
    # Write WAV file
    write(args.output, args.sample_rate, signal_int16)
    print(f"[SUCCESS] Wrote {args.output}")


if __name__ == "__main__":
    main()
