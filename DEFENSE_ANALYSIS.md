# DHWANI - Defense & Security Analysis

## Current Implementation Explained

### 1. Ultrasonic Frequencies (17-18.5 kHz)
**What it is:** Sound waves above normal speech range but still within hearing threshold.

**How it works in DHWANI:**
- F0 = 17,000 Hz (represents binary '0')
- F1 = 18,500 Hz (represents binary '1')
- Human hearing typically ranges 20 Hz - 20,000 Hz
- Most adults can't hear above 16,000 Hz

**Military Advantage:** Communication is nearly inaudible to humans, making it covert.

---

### 2. FSK (Frequency Shift Keying)
**What it is:** A modulation technique where digital data is represented by shifting between two frequencies.

**How it works:**
```
Binary: 1 0 1 1 0 0 1
Sound:  ~~~ ___ ~~~ ~~~ ___ ___ ~~~
        18.5kHz  17kHz  18.5kHz...
```

**Why CPFSK (Continuous Phase):** Phase doesn't jump abruptly between bits, making the signal:
- Harder to detect via spectral analysis
- More resistant to noise
- Smoother audio (less clicking)

---

### 3. Token-Based Authentication (Current)
**What it is:** A shared secret is hashed and transmitted as proof of identity.

**How it works:**
```
Sender: secret = "password123"
        token = SHA256("password123")[:8] = "ef92b778"
        → Transmits token

Receiver: expected = SHA256("password123")[:8] = "ef92b778"
          → Compares: received == expected?
```

**Flaw:** Same secret always produces same token → can be recorded and replayed.

---

## Security Flaws Explained

### ❌ Flaw 1: No Encryption
**Problem:** Payload is transmitted as plain binary.
```
Message: "ATTACK AT DAWN"
Transmitted: 01000001 01010100 01010100 01000001 01000011 01001011...
             (A)      (T)      (T)      (A)      (C)      (K)
```
**Risk:** Anyone with this software can decode the message.

**Solution:** AES-256 encryption before transmission.

---

### ❌ Flaw 2: Fixed Frequencies
**Problem:** F0=17kHz and F1=18.5kHz are always the same.

**Risk:** 
1. Enemy can tune radio to 17-19kHz to intercept
2. Easy to jam by broadcasting noise at those frequencies

**Solution:** Frequency Hopping Spread Spectrum (FHSS)
```
Time 0: F0=17000, F1=18500
Time 1: F0=16500, F1=18000  (hop based on shared key)
Time 2: F0=17500, F1=19000
...
```

---

### ❌ Flaw 3: Replay Attack Vulnerability
**Problem:** Auth token is always the same for the same password.

**Attack Scenario:**
1. Enemy records: `AUTH_PACKET` with valid token
2. Enemy replays: Same packet 1 hour later
3. System accepts: ✓ (token matches)

**Solution:** Include timestamp or nonce (number used once)
```
token = SHA256(password + timestamp)
        → Different every time
        → Receiver rejects if timestamp is old
```

---

### ❌ Flaw 4: No Cryptographic Signature
**Problem:** Current checksum is just: `sum(bytes) % 256`

**Attack:** Enemy can modify payload and recalculate checksum.
```
Original: "RETREAT" + checksum=180
Modified: "ADVANCE" + checksum=XXX (recalculated)
```

**Solution:** HMAC (Hash-based Message Authentication Code)
```
signature = HMAC-SHA256(secret_key, message)
            → Cannot be forged without the key
```

---

## Recommended Military-Grade Upgrades

### 🔒 AES-256 Encryption
```python
from Crypto.Cipher import AES
cipher = AES.new(key, AES.MODE_GCM)
encrypted = cipher.encrypt(plaintext)
# Now payload is unreadable without key
```

### 📡 Frequency Hopping
```python
def get_frequencies(key, time_slot):
    seed = hash(key + str(time_slot))
    f0 = 15000 + (seed % 3000)      # 15-18 kHz
    f1 = f0 + 1000 + (seed % 1000)  # +1-2 kHz gap
    return f0, f1
```

### ⏱️ Anti-Replay (Timestamp)
```python
import time
nonce = int(time.time())  # Current Unix timestamp
token = sha256(password + str(nonce))
# Receiver rejects if nonce is > 30 seconds old
```

### ✍️ HMAC Signature
```python
import hmac
signature = hmac.new(key, message, 'sha256').digest()
# Append to packet; receiver verifies before accepting
```

---

## Summary: Current vs. Military-Grade

| Feature | Current DHWANI | Military-Grade |
|---------|----------------|----------------|
| Encryption | ❌ None | ✅ AES-256-GCM |
| Frequency | Fixed | Hopping (FHSS) |
| Anti-Replay | ❌ None | ✅ Timestamp/Nonce |
| Integrity | Checksum | HMAC-SHA256 |
| Key Exchange | Manual | Diffie-Hellman |

---

## Practical Use Cases

1. **Indoor Tactical Comms**: Squad-level commands in buildings where radio might be jammed
2. **Covert Authentication**: Acoustic NFC alternative for access control
3. **Air-Gapped Systems**: Transfer data to isolated computers via speaker/mic
4. **Emergency Backup**: When all RF communications are compromised
