# BFSK Acoustic Communication System
## How It Works - Technical Documentation

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Sender Module](#3-sender-module)
4. [Receiver Module](#4-receiver-module)
5. [Encryption System](#5-encryption-system)
6. [Packet Formats](#6-packet-formats)
7. [Usage Examples](#7-usage-examples)

---

## 1. System Overview

### What is this project?

This is a **Binary Frequency-Shift Keying (BFSK) Acoustic Communication System** that transmits data through sound waves. It encodes binary data into audio frequencies and transmits it through speakers, which can then be received and decoded by a microphone.

### Key Features

| Feature | Description |
|---------|-------------|
| **Data Transmission** | Send text messages through sound |
| **Authentication** | SHA-256 based token verification |
| **Encryption** | AES-256-GCM payload encryption |
| **Near-Ultrasonic** | Uses 17-18.5 kHz (barely audible) |
| **GUI Interface** | User-friendly graphical interface |

### How Data Flows

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   SENDER    │     │   CHANNEL   │     │  RECEIVER   │
│             │     │             │     │             │
│ Text/Secret │────▶│ Sound Waves │────▶│ Decode Data │
│     ↓       │     │ (17-18.5kHz)│     │     ↑       │
│ Encode Bits │     │             │     │ Analyze FFT │
│     ↓       │     │             │     │     ↑       │
│ Generate    │     │             │     │ Record Audio│
│ Audio (FSK) │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## 2. Architecture

### System Components

```
┌──────────────────────────────────────────────────────┐
│                    GUI (gui.py)                      │
│  ┌─────────────────┐     ┌─────────────────┐        │
│  │  Sender Panel   │     │ Receiver Panel  │        │
│  │  - Enter data   │     │ - Record audio  │        │
│  │  - Set options  │     │ - Load WAV file │        │
│  │  - Generate WAV │     │ - Decode packet │        │
│  └────────┬────────┘     └────────┬────────┘        │
└───────────┼──────────────────────┼──────────────────┘
            │                      │
            ▼                      ▼
┌───────────────────┐    ┌───────────────────┐
│   sender.py       │    │   receiver.py     │
│                   │    │                   │
│ • Text → Bits     │    │ • Audio → Bits    │
│ • Bits → Audio    │    │ • Bits → Text     │
│ • Encryption      │    │ • Decryption      │
│ • WAV Output      │    │ • Authentication  │
└───────────────────┘    └───────────────────┘
```

### File Structure

```
v2/
├── sender.py          # Encoding and transmission
├── receiver.py        # Decoding and reception
├── gui.py             # Graphical user interface
├── README.md          # Quick start guide
└── topics_and_theory.txt  # Detailed theory
```

---

## 3. Sender Module

### Encoding Process

The sender converts your message into audio through these steps:

```
Step 1: TEXT TO BINARY
┌─────────────────────────────────────────────┐
│ Input: "Hi"                                 │
│ ASCII: H=72, i=105                          │
│ Binary: 01001000 01101001                   │
└─────────────────────────────────────────────┘
                    ↓
Step 2: BUILD PACKET
┌─────────────────────────────────────────────┐
│ Preamble:  10101010101010101010101010101010 │
│ Start:     11001100                         │
│ Unit ID:   0001                             │
│ Length:    00000010                         │
│ Payload:   01001000 01101001                │
│ Checksum:  10110001                         │
│ End:       11111111                         │
└─────────────────────────────────────────────┘
                    ↓
Step 3: GENERATE AUDIO (CPFSK)
┌─────────────────────────────────────────────┐
│ For each bit:                               │
│   • Bit '0' → 17000 Hz sine wave            │
│   • Bit '1' → 18500 Hz sine wave            │
│   • Duration: 80ms per bit                  │
│   • Phase: Continuous (no discontinuities)  │
└─────────────────────────────────────────────┘
                    ↓
Step 4: SAVE/PLAY
┌─────────────────────────────────────────────┐
│ Output: packet.wav (16-bit PCM, 44100 Hz)   │
└─────────────────────────────────────────────┘
```

### Frequency Modulation

```
             f0 = 17000 Hz          f1 = 18500 Hz
                  │                      │
Bit 0: ∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿   Bit 1: ∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿
        (lower freq)              (higher freq)
```

### Command Line Usage

```bash
# Send text message
python sender.py --data "Hello World" --output message.wav

# Send with encryption
python sender.py --data "Secret" --encrypt --key "password123"

# Send authentication token
python sender.py --secret "my_key" --auth-mode
```

---

## 4. Receiver Module

### Decoding Process

The receiver converts audio back to your message:

```
Step 1: CAPTURE AUDIO
┌─────────────────────────────────────────────┐
│ Input: packet.wav or microphone recording   │
│ Sample Rate: 44100 Hz                       │
│ Format: 16-bit PCM                          │
└─────────────────────────────────────────────┘
                    ↓
Step 2: SEGMENT INTO BITS
┌─────────────────────────────────────────────┐
│ Each 80ms window = 3528 samples = 1 bit     │
│ Apply Hanning window to reduce leakage      │
└─────────────────────────────────────────────┘
                    ↓
Step 3: FFT ANALYSIS (for each window)
┌─────────────────────────────────────────────┐
│ Compute FFT of 3528 samples                 │
│ Measure energy at f0 (17000 Hz)             │
│ Measure energy at f1 (18500 Hz)             │
│ If energy_f1 > energy_f0: bit = '1'         │
│ Else: bit = '0'                             │
└─────────────────────────────────────────────┘
                    ↓
Step 4: FIND PACKET
┌─────────────────────────────────────────────┐
│ Search for START_FLAG (11001100)            │
│ or ENCRYPTED_FLAG (11110000)                │
└─────────────────────────────────────────────┘
                    ↓
Step 5: PARSE & VERIFY
┌─────────────────────────────────────────────┐
│ Extract: Unit ID, Length, Payload, Checksum │
│ Verify: Checksum matches                    │
│ Decrypt: If encrypted and key provided      │
│ Output: Decoded message                     │
└─────────────────────────────────────────────┘
```

### FFT Bit Detection

```
        Frequency Spectrum for Bit Window
        
Magnitude
    │
    │    ┌───┐
    │    │   │                        ┌───┐
    │    │   │                        │   │
    │    │ f0│                        │f1 │
    └────┴───┴────────────────────────┴───┴────▶ Frequency
         17kHz                       18.5kHz
         
    If f1 peak > f0 peak → Bit is '1'
    If f0 peak > f1 peak → Bit is '0'
```

### Command Line Usage

```bash
# Decode from file
python receiver.py --input packet.wav

# Decode with decryption
python receiver.py --input packet.wav --key "password123"

# Record from microphone
python receiver.py --record 10

# Verify authentication
python receiver.py --input auth.wav --auth-mode --secret "my_key"
```

---

## 5. Encryption System

### Why Encryption?

Without encryption, anyone listening can decode your message:

```
UNENCRYPTED:
┌─────────┐    Sound    ┌─────────┐    Sound    ┌─────────┐
│ Sender  │────Waves───▶│Attacker │────Waves───▶│Receiver │
│         │             │CAN READ │             │         │
└─────────┘             └─────────┘             └─────────┘

ENCRYPTED:
┌─────────┐    Sound    ┌─────────┐    Sound    ┌─────────┐
│ Sender  │────Waves───▶│Attacker │────Waves───▶│Receiver │
│(has key)│             │GIBBERISH│             │(has key)│
└─────────┘             └─────────┘             └─────────┘
```

### AES-256-GCM Encryption Flow

```
ENCRYPTION (Sender):
┌──────────────────────────────────────────────────────┐
│                                                      │
│  Password: "mypassword"                              │
│       │                                              │
│       ▼                                              │
│  ┌─────────────────────────────────────────┐        │
│  │ PBKDF2 (100,000 iterations)             │        │
│  │ + Random Salt (16 bytes)                │        │
│  └─────────────────────────────────────────┘        │
│       │                                              │
│       ▼                                              │
│  256-bit AES Key                                     │
│       │                                              │
│       ▼                                              │
│  ┌─────────────────────────────────────────┐        │
│  │ AES-256-GCM Encryption                  │        │
│  │ + Random Nonce (12 bytes)               │        │
│  └─────────────────────────────────────────┘        │
│       │                                              │
│       ▼                                              │
│  Output: Salt + Nonce + Ciphertext + AuthTag        │
│          (16)   (12)    (variable)    (16)          │
│                                                      │
└──────────────────────────────────────────────────────┘

DECRYPTION (Receiver):
┌──────────────────────────────────────────────────────┐
│                                                      │
│  Received: Salt + Nonce + Ciphertext + AuthTag       │
│                                                      │
│  Password: "mypassword" (must match!)                │
│       │                                              │
│       ▼                                              │
│  ┌─────────────────────────────────────────┐        │
│  │ PBKDF2 with received Salt               │        │
│  └─────────────────────────────────────────┘        │
│       │                                              │
│       ▼                                              │
│  Same 256-bit AES Key                                │
│       │                                              │
│       ▼                                              │
│  ┌─────────────────────────────────────────┐        │
│  │ AES-256-GCM Decryption                  │        │
│  │ (Verifies AuthTag - fails if wrong key) │        │
│  └─────────────────────────────────────────┘        │
│       │                                              │
│       ▼                                              │
│  Original Plaintext                                  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Security Properties

| Property | Provided By | Description |
|----------|-------------|-------------|
| Confidentiality | AES-256 | Data is encrypted |
| Integrity | GCM Auth Tag | Tampering detected |
| Key Strength | PBKDF2 | Slow brute-force |
| Uniqueness | Random Salt/Nonce | Same message encrypts differently |

---

## 6. Packet Formats

### Data Mode Packet

```
┌────────────────────────────────────────────────────────────┐
│                      DATA PACKET                           │
├──────────┬───────────┬─────────┬────────┬─────────────────┤
│ PREAMBLE │ START     │ UNIT_ID │ LENGTH │    PAYLOAD      │
│ 32 bits  │ 8 bits    │ 4 bits  │ 8 bits │    N×8 bits     │
│10101010..│ 11001100  │  0-15   │  0-255 │   UTF-8 data    │
├──────────┴───────────┴─────────┴────────┴─────────────────┤
│                                                            │
├────────────────────────────────────┬──────────┬───────────┤
│              (continued)           │ CHECKSUM │    END    │
│                                    │  8 bits  │  8 bits   │
│                                    │ sum%256  │ 11111111  │
└────────────────────────────────────┴──────────┴───────────┘
```

### Auth Mode Packet

```
┌────────────────────────────────────────────────────────────┐
│                   AUTHENTICATION PACKET                    │
├──────────┬───────────┬─────────┬────────────┬─────────────┤
│ PREAMBLE │ START     │ UNIT_ID │   TOKEN    │  CHECKSUM   │
│ 32 bits  │ 8 bits    │ 4 bits  │  32 bits   │   8 bits    │
│10101010..│ 11001100  │  0-15   │SHA256[:8]  │  sum%256    │
├──────────┴───────────┴─────────┴────────────┴─────────────┤
│                                                            │
├────────────────────────────────────────────────┬──────────┤
│                  (continued)                   │   END    │
│                                                │  8 bits  │
│                                                │ 11111111 │
└────────────────────────────────────────────────┴──────────┘

Total: 92 bits fixed
```

### Encrypted Mode Packet

```
┌────────────────────────────────────────────────────────────┐
│                    ENCRYPTED PACKET                        │
├──────────┬───────────┬─────────┬────────┬─────────────────┤
│ PREAMBLE │ ENC_FLAG  │ UNIT_ID │ LENGTH │ ENCRYPTED_DATA  │
│ 32 bits  │ 8 bits    │ 4 bits  │ 8 bits │    N×8 bits     │
│10101010..│ 11110000  │  0-15   │  bytes │ salt+nonce+...  │
├──────────┴───────────┴─────────┴────────┴─────────────────┤
│                                                            │
├────────────────────────────────────┬──────────┬───────────┤
│              (continued)           │ CHECKSUM │    END    │
│                                    │  8 bits  │  8 bits   │
│                                    │ sum%256  │ 11111111  │
└────────────────────────────────────┴──────────┴───────────┘

ENCRYPTED_DATA contains:
┌──────────┬────────┬────────────┬──────────┐
│   SALT   │ NONCE  │ CIPHERTEXT │ AUTH TAG │
│ 16 bytes │12 bytes│  variable  │ 16 bytes │
└──────────┴────────┴────────────┴──────────┘
```

---

## 7. Usage Examples

### Example 1: Send Text Message

```bash
# Sender (Terminal 1)
python sender.py --data "Hello World" --output hello.wav
# Creates: hello.wav
# Transmission time: ~8.6 seconds

# Receiver (Terminal 2)  
python receiver.py --input hello.wav
# Output:
# Mode: DATA
# Payload: Hello World
# ✓ PACKET VALID
```

### Example 2: Encrypted Communication

```bash
# Sender
python sender.py --data "Secret Message" --encrypt --key "password123"
# Creates: packet.wav (encrypted)

# Receiver (with correct key)
python receiver.py --input packet.wav --key "password123"
# Output:
# 🔓 Decrypted: Secret Message
# ✓ PACKET VALID & DECRYPTED

# Receiver (without key)
python receiver.py --input packet.wav
# Output:
# 🔒 Encrypted (use --key to decrypt)

# Receiver (wrong key)
python receiver.py --input packet.wav --key "wrongpass"
# Output:
# 🔒 Decryption Failed
```

### Example 3: Authentication

```bash
# Sender (generates token from secret)
python sender.py --secret "door_key_123" --auth-mode
# Creates: packet.wav with authentication token

# Receiver (verifies against expected secret)
python receiver.py --input packet.wav --auth-mode --secret "door_key_123"
# Output:
# ✓ ACCESS GRANTED

# Receiver (wrong secret)
python receiver.py --input packet.wav --auth-mode --secret "wrong_secret"
# Output:
# ✗ ACCESS DENIED
```

### Example 4: Live Recording

```bash
# Record from microphone for 10 seconds
python receiver.py --record 10

# With encryption decryption
python receiver.py --record 10 --key "password123"
```

### Example 5: Using GUI

```bash
python gui.py
```

The GUI provides:
- **Sender Panel**: Enter text, choose mode, generate/play audio
- **Receiver Panel**: Record from mic or load file, decode
- **Device Selection**: Choose specific audio devices
- **Live Output Log**: See decoded results in real-time

---

## Technical Specifications

| Parameter | Value | Notes |
|-----------|-------|-------|
| Frequency f0 | 17000 Hz | Bit '0' |
| Frequency f1 | 18500 Hz | Bit '1' |
| Bit Duration | 80 ms | Per bit |
| Sample Rate | 44100 Hz | CD quality |
| Bit Depth | 16-bit | PCM |
| Data Rate | 12.5 bps | Effective |
| Encryption | AES-256-GCM | Optional |
| Key Derivation | PBKDF2 | 100,000 iterations |
| Hash Algorithm | SHA-256 | For auth tokens |

---

## Dependencies

```
numpy          # Signal processing
scipy          # WAV file I/O
sounddevice    # Audio recording/playback
cryptography   # AES encryption
```

Install all:
```bash
pip install numpy scipy sounddevice cryptography
```

---

*Document Version: 1.0*  
*Last Updated: January 2026*
