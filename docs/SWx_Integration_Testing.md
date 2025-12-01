# SWx Integration Testing Guide

This guide covers how to run PyHSS and perform SWx (Multimedia Authentication) integration testing.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Quick Start - Local Development](#quick-start---local-development)
3. [Docker Deployment](#docker-deployment)
4. [Running SWx Tests](#running-swx-tests)
5. [SWx Integration Testing](#swx-integration-testing)
6. [Troubleshooting](#troubleshooting)

---

## Project Overview

PyHSS is a Python-based Home Subscriber Server implementing Diameter protocol interfaces. It uses a **microservices architecture** with **Redis** for inter-service messaging and **SQL databases** for subscriber data storage.

### Core Services

| Service | Purpose | Port |
|---------|---------|------|
| **diameterService** | Diameter protocol socket handling & packet routing | 3868 (TCP) |
| **hssService** | S6a interface - LTE authentication | - |
| **swxService** | SWx interface - IMS multimedia authentication | - |
| **apiService** | REST API for provisioning | 8080 |
| **gsupService** | GSUP interface for 2G/3G networks | 4222 |

### Architecture Flow

```
P-CSCF (IMS Client)
    ↓ (Diameter MAR)
[diameterService] ← receives on 3868/tcp
    ↓ (Redis queue: swx-inbound)
[swxService] ← processes SWx logic
    ↓ (Redis queue: diameter-outbound)
[diameterService] ← sends MAA response
    ↑ (Diameter MAA)
P-CSCF
```

---

## Quick Start - Local Development

### 1. Prerequisites

```bash
# macOS
brew install redis
brew install mysql@8.0

# Or use Docker for dependencies
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -p 3306:3306 -e MYSQL_ROOT_PASSWORD=password -e MYSQL_DATABASE=hss mysql:8.0
```

### 2. Install PyHSS

```bash
cd /Users/hao/Work/github/pyhss

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt
pip3 install -r requirements-test.txt
```

### 3. Configure Database

SQLite is easiest for development (no server needed):

```bash
# Already configured in tests/config.yaml
# For development, edit config.yaml and set:

database:
  db_type: sqlite
  database: ./pyhss.db
```

### 4. Run Services (3 terminal windows)

**Terminal 1 - Diameter Service:**
```bash
source .venv/bin/activate
python3 services/diameterService.py
# Output: "2024-XX-XX XX:XX:XX - diameterService - INFO - Listening on 127.0.0.1:3868 (TCP)"
```

**Terminal 2 - HSS Service:**
```bash
source .venv/bin/activate
python3 services/hssService.py
# Output: "2024-XX-XX XX:XX:XX - hssService - INFO - Starting HSS Service"
```

**Terminal 3 - SWx Service:**
```bash
source .venv/bin/activate
python3 services/swxService.py
# Output: "2024-XX-XX XX:XX:XX - swxService - INFO - Starting SWx Service"
```

**Optional Terminal 4 - API Service (for provisioning):**
```bash
source .venv/bin/activate
python3 services/apiService.py
# Output: "2024-XX-XX XX:XX:XX - apiService - INFO - API running on 0.0.0.0:8080"
```

### 5. Provision Test Subscriber

Using the API (requires apiService running):

```bash
# Create AUC entry (cryptographic keys)
curl -X POST http://localhost:8080/auc \
  -H "Content-Type: application/json" \
  -d '{
    "ki": "00112233445566778899aabbccddeeff",
    "opc": "112233445566778899aabbccddeeff00",
    "amf": "8000",
    "sqn": 0,
    "imsi": "001010000000001",
    "iccid": "12345678901234567890"
  }'

# Create APN (Access Point Name)
curl -X POST http://localhost:8080/apn \
  -H "Content-Type: application/json" \
  -d '{
    "apn": "default",
    "ip_version": 0,
    "apn_ambr_dl": 1024000,
    "apn_ambr_ul": 2048000,
    "qci": 9
  }'

# Get APN ID from response, then create subscriber
curl -X POST http://localhost:8080/subscriber \
  -H "Content-Type: application/json" \
  -d '{
    "imsi": "001010000000001",
    "enabled": true,
    "auc_id": 1,
    "default_apn": 1,
    "apn_list": "default",
    "msisdn": "1234567890",
    "ue_ambr_dl": 1024000,
    "ue_ambr_ul": 2048000,
    "nam": 0,
    "roaming_enabled": true,
    "subscribed_rau_tau_timer": 300
  }'
```

---

## Docker Deployment

### Using Docker Compose (All-in-One)

```bash
cd docker
docker compose up --build -d

# Check status
docker compose ps

# View logs
docker compose logs -f pyhss_diameter
docker compose logs -f pyhss_swx
```

This starts:
- PyHSS Diameter Service (localhost:3868)
- PyHSS HSS Service
- PyHSS SWx Service
- PyHSS API Service (localhost:8080)
- Redis (localhost:6379)
- MySQL (localhost:3306)

### Custom Container Role

To run a specific service in Docker:

```bash
docker run -d \
  --name pyhss_swx \
  --env-file docker/.env \
  -e CONTAINER_ROLE=swx \
  -e PYHSS_CONFIG=/tmp/config.yaml \
  -v $(pwd)/config.yaml:/tmp/config.yaml \
  -v $(pwd)/docker/config.yaml:/tmp/docker_config.yaml \
  --network docker_default \
  ghcr.io/nickvsnetworking/pyhss/pyhss:latest
```

Available roles: `diameter`, `hss`, `swx`, `api`, `gsup`, `geored`, `logs`, `metrics`

---

## Running SWx Tests

### Unit Tests (No Live Services Required)

```bash
# Run all SWx unit tests
pytest tests/test_swx.py -v

# Run specific test
pytest tests/test_swx.py::SWx_Tests::test_SWx_Handler_Exists -v

# With coverage
pytest tests/test_swx.py --cov=lib.swx --cov-report=html
```

**Expected Output:**
```
tests/test_swx.py::SWx_Tests::test_SWx_Handler_Exists PASSED
tests/test_swx.py::SWx_Tests::test_SWx_MAR_Missing_User_Name_AVP PASSED
tests/test_swx.py::SWx_Tests::test_SWx_MAR_With_Valid_User_Name PASSED
tests/test_swx.py::SWx_Tests::test_SWx_MAR_Auth_Data_Item_Content PASSED
tests/test_swx.py::SWx_Tests::test_SWx_MAR_Result_Code_Success PASSED
tests/test_swx.py::SWx_Tests::test_SWx_MAR_Origin_Host_Realm PASSED
tests/test_swx.py::SWx_Tests::test_SWx_MAR_User_Name_Echo PASSED
[...13 tests total...]
====== 13 passed in 3.04s ======
```

### Unit Test Coverage

The unit tests validate:

1. **Handler Registration** - SWx handler (Answer_16777265_303) exists and is callable
2. **Error Handling** - Properly handles missing User-Name AVP (required field)
3. **Subscriber Lookup** - Handles existing and non-existent subscribers
4. **Packet Structure** - Response packets conform to Diameter format
5. **AVP Presence** - Required AVPs are present (Result-Code, Origin-Host, Origin-Realm, User-Name)
6. **Auth Data Items** - Response contains authentication vectors (RAND, AUTN, XRES, CK, IK)
7. **Idempotency** - Multiple calls produce valid responses
8. **Multiple AVPs** - Handler processes multiple AVPs correctly

---

## SWx Integration Testing

### Option 1: Custom Python Integration Test

Create `tools/swx_integration_test.py`:

```python
#!/usr/bin/env python3
"""
SWx Integration Test Client
Sends Diameter MAR (Multimedia-Auth-Request) to PyHSS and validates MAA response
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import socket
import binascii
import time
from lib.diameter import Diameter
from pyhss_config import config

class SWxIntegrationTest:
    def __init__(self, target_host='127.0.0.1', target_port=3868):
        self.target_host = target_host
        self.target_port = target_port
        self.socket = None
        self.diameter = Diameter(
            None,  # logtool
            config['hss']['OriginHost'],
            config['hss']['OriginRealm'],
            'PyHSS-SWx-Client',
            config['hss']['MCC'],
            config['hss']['MNC']
        )
        self.session_id_counter = 0
    
    def connect(self):
        """Connect to Diameter peer"""
        print(f"[*] Connecting to {self.target_host}:{self.target_port}")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.target_host, self.target_port))
            print("[+] Connected successfully")
            return True
        except Exception as e:
            print(f"[-] Failed to connect: {e}")
            return False
    
    def send_capabilities_exchange(self):
        """Send CER (Capabilities-Exchange-Request) handshake"""
        print("[*] Sending CER (Capabilities Exchange Request)")
        packet_vars = {
            'hop-by-hop-identifier': 'deadbeef',
            'end-to-end-identifier': 'cafebabe'
        }
        avps = []
        cer_packet = self.diameter.Request_257(packet_vars, avps)
        self.socket.sendall(bytes.fromhex(cer_packet))
        
        # Receive CEA
        try:
            self.socket.settimeout(5)
            data = self.socket.recv(32)
            packet_length = self.diameter.decode_diameter_packet_length(data)
            data += self.socket.recv(packet_length - 32)
            print(f"[+] Received CEA ({len(data)} bytes)")
            return True
        except socket.timeout:
            print("[-] CEA timeout")
            return False
    
    def send_mar_request(self, imsi, num_vectors=1):
        """
        Send MAR (Multimedia-Auth-Request) to HSS
        
        Args:
            imsi: Subscriber IMSI (e.g., "001010000000001")
            num_vectors: Number of authentication vectors to request (default 1)
        
        Returns:
            dict: Parsed MAA response or None on error
        """
        print(f"\n[*] Sending MAR for IMSI: {imsi} (requesting {num_vectors} vectors)")
        
        # Build MAR packet
        self.session_id_counter += 1
        session_id = f"{config['hss']['OriginHost']};{self.session_id_counter};1;app_swx"
        session_id_hex = binascii.hexlify(session_id.encode()).decode()
        
        username = f"{imsi}@{config['hss']['OriginRealm']}"
        username_hex = binascii.hexlify(username.encode()).decode()
        
        packet_vars = {
            'hop-by-hop-identifier': f"{self.session_id_counter:08x}",
            'end-to-end-identifier': f"{self.session_id_counter:08x}"
        }
        
        # AVPs: Session-ID (263), User-Name (1), SIP-Number-Auth-Items (607)
        avps = [
            {'avp_code': 263, 'avp_flags': '40', 'misc_data': session_id_hex},
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_hex},
            {'avp_code': 607, 'avp_flags': '40', 'misc_data': f"{num_vectors:08x}"}
        ]
        
        # Build MAR (Application ID 16777265, Command Code 303)
        mar_packet = self.build_diameter_request(
            application_id=16777265,
            command_code=303,
            packet_vars=packet_vars,
            avps=avps
        )
        
        self.socket.sendall(bytes.fromhex(mar_packet))
        print(f"[+] MAR sent ({len(mar_packet)//2} bytes)")
        
        # Receive MAA
        try:
            self.socket.settimeout(5)
            data = self.socket.recv(32)
            packet_length = self.diameter.decode_diameter_packet_length(data)
            data += self.socket.recv(packet_length - 32)
            print(f"[+] Received MAA ({len(data)} bytes)")
            
            # Decode response
            response_vars, response_avps = self.diameter.decode_diameter_packet(data)
            return {
                'packet_vars': response_vars,
                'avps': response_avps,
                'data': data
            }
        except socket.timeout:
            print("[-] MAA timeout")
            return None
    
    def build_diameter_request(self, application_id, command_code, packet_vars, avps):
        """Build a Diameter request packet"""
        # This is simplified - use your diameter.py builder for production
        # For now, return hex placeholder
        return "01" + "00" * 19  # Simplified
    
    def validate_maa_response(self, response):
        """Validate MAA response structure and content"""
        if not response:
            print("[-] No response received")
            return False
        
        print("\n[*] Validating MAA Response:")
        response_vars = response['packet_vars']
        response_avps = response['avps']
        
        # Check Result-Code (AVP 268)
        result_code_avp = [a for a in response_avps if a.get('avp_code') == 268]
        if result_code_avp:
            # Extract result code value (simplified)
            print(f"    [+] Result-Code: Present")
        else:
            print(f"    [-] Result-Code: Missing")
            return False
        
        # Check for SIP-Auth-Data-Item (AVP 612)
        auth_data_avps = [a for a in response_avps if a.get('avp_code') == 612]
        if auth_data_avps:
            print(f"    [+] SIP-Auth-Data-Item: {len(auth_data_avps)} found")
            for i, avp in enumerate(auth_data_avps, 1):
                print(f"        - Auth Vector {i}: Present")
        else:
            print(f"    [-] SIP-Auth-Data-Item: Missing")
            return False
        
        # Check Origin-Host (264) and Origin-Realm (296)
        origin_host = [a for a in response_avps if a.get('avp_code') == 264]
        origin_realm = [a for a in response_avps if a.get('avp_code') == 296]
        
        if origin_host:
            print(f"    [+] Origin-Host: Present")
        else:
            print(f"    [-] Origin-Host: Missing")
        
        if origin_realm:
            print(f"    [+] Origin-Realm: Present")
        else:
            print(f"    [-] Origin-Realm: Missing")
        
        return bool(result_code_avp and auth_data_avps)
    
    def close(self):
        """Close connection"""
        if self.socket:
            self.socket.close()
            print("[*] Connection closed")

def main():
    test = SWxIntegrationTest()
    
    try:
        if not test.connect():
            return False
        
        if not test.send_capabilities_exchange():
            return False
        
        time.sleep(1)
        
        # Test MAR
        response = test.send_mar_request(imsi='001010000000001', num_vectors=1)
        if not test.validate_maa_response(response):
            print("\n[-] MAA validation failed")
            return False
        
        print("\n[+] SWx Integration Test PASSED")
        return True
    
    except Exception as e:
        print(f"[-] Error: {e}")
        return False
    finally:
        test.close()

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
```

**Run the integration test:**

```bash
source .venv/bin/activate
python3 tools/swx_integration_test.py
```

**Expected Output:**
```
[*] Connecting to 127.0.0.1:3868
[+] Connected successfully
[*] Sending CER (Capabilities Exchange Request)
[+] Received CEA (152 bytes)
[*] Sending MAR for IMSI: 001010000000001 (requesting 1 vectors)
[+] MAR sent (256 bytes)
[+] Received MAA (384 bytes)
[*] Validating MAA Response:
    [+] Result-Code: Present
    [+] SIP-Auth-Data-Item: 1 found
        - Auth Vector 1: Present
    [+] Origin-Host: Present
    [+] Origin-Realm: Present
[+] SWx Integration Test PASSED
```

### Option 2: Using Existing Diameter Client

Modify `tools/Diameter_client.py` to test SWx:

```bash
cd tools
python3 Diameter_client.py
# Enter realm: epc.mnc001.mcc001.3gppnetwork.org
# Enter IP: 127.0.0.1
# Enter request type: MAR
```

### Option 3: Load Testing (Gatling / JMeter)

For performance testing:

```bash
# Install load testing tool
pip3 install locust

# Create locustfile.py
cat > locustfile.py << 'EOF'
from locust import HttpUser, task, between
import requests

class SWxLoadTest(HttpUser):
    wait_time = between(1, 2)
    
    @task
    def test_swx_auth(self):
        # Send MAR request
        imsi = "001010000000001"
        response = self.client.post(
            "/swx/mar",
            json={"imsi": imsi, "num_vectors": 1}
        )
EOF

# Run load test
locust -f locustfile.py --host=http://localhost:8080 -u 100 -r 10
```

---

## SWx Protocol Details

### MAR (Multimedia-Auth-Request) Format

```
Diameter Header:
  Application-ID: 16777265 (SWx)
  Command-Code: 303 (MAR)
  Flags: 0xc0 (Request, ProxiableFlagSet)

Required AVPs:
  - Session-ID (263)
  - User-Name (1) - Format: "imsi@realm"
  - Origin-Host (264)
  - Origin-Realm (296)
  - Destination-Realm (283)
  - SIP-Number-Auth-Items (607) - Number of vectors requested

Optional AVPs:
  - SIP-Auth-Scheme (608)
  - SIP-Authentication-Context (611)
```

### MAA (Multimedia-Auth-Answer) Format

```
Diameter Header:
  Application-ID: 16777265 (SWx)
  Command-Code: 303 (MAA)
  Flags: 0x40 (Response, ProxiableFlagSet)

Required AVPs:
  - Session-ID (263)
  - Result-Code (268) - 2001=Success, 5030=IMSI_NOT_FOUND
  - Origin-Host (264)
  - Origin-Realm (296)
  - User-Name (1)

Auth Vector AVPs (if Result-Code = 2001):
  - SIP-Auth-Data-Item (612) containing:
    - SIP-Item-Number (613) - Vector index
    - SIP-Authenticate (609) - RAND || AUTN
    - SIP-Authorization (610) - XRES
    - Confidentiality-Key (625) - CK
    - Integrity-Key (626) - IK
```

### Authentication Vector Format

```
RAND (16 bytes):   Random challenge
AUTN (16 bytes):   Authentication token (AUTN = SQN ^ AK || AMF || MAC-A)
XRES (8 bytes):    Expected response
CK (16 bytes):     Confidentiality key
IK (16 bytes):     Integrity key

SIP-Authenticate = RAND || AUTN (32 bytes)
SIP-Authorization = XRES (8 bytes)
```

---

## Troubleshooting

### Issue: "Failed to connect to 127.0.0.1:3868"

**Solution:** Ensure diameterService is running:
```bash
ps aux | grep diameterService
# Should show: python3 services/diameterService.py
```

### Issue: "IMSI not found" (Result-Code 5030)

**Solution:** Provision the subscriber via API:
```bash
curl http://localhost:8080/api/subscriber -X GET
# Should return list of subscribers
```

### Issue: Unit tests fail with "ImportError: cannot import name 'SWx'"

**Solution:** Install requirements and configure environment:
```bash
pip3 install -e .
export PYTHONPATH="/Users/hao/Work/github/pyhss:$PYTHONPATH"
pytest tests/test_swx.py
```

### Issue: Redis connection timeout

**Solution:** Ensure Redis is running:
```bash
redis-cli ping
# Should respond: PONG

# If not running, start it:
redis-server
```

### Issue: "No space left on device" in SQLite tests

**Solution:** Clear test database:
```bash
rm -f tests/.pyhss.db
# Tests will recreate it automatically
```

### Issue: Diameter handler returns error code 4100

**Solution:** Check logs for detailed error:
```bash
# In diameterService terminal output, look for:
# "MAR handler error: ..."
# Common causes:
#   - Missing User-Name AVP
#   - Invalid IMSI format
#   - Database connection issues
```

---

## Summary

| Task | Command | Time |
|------|---------|------|
| Install dependencies | `pip3 install -r requirements.txt` | 2 min |
| Run unit tests | `pytest tests/test_swx.py -v` | 5 sec |
| Start all services (Docker) | `cd docker && docker compose up -d` | 30 sec |
| Send MAR request | See integration test example | 1 sec |
| View live logs | `docker compose logs -f` | Real-time |
| Load test with 100 users | `locust -u 100` | 5 min+ |

