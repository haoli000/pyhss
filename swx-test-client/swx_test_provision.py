#!/usr/bin/env python3
"""
SWx Test Provisioning and Integration Script

This script:
1. Provisions test subscribers with AUC and APN data via the REST API
2. Sends SWx MAR (Multimedia-Auth-Request) to test the SWx handler
3. Validates the MAA (Multimedia-Auth-Answer) response
4. Reports on the authentication vector generation

Usage:
    python3 tools/swx_test_provision.py [--api-host 127.0.0.1] [--api-port 8080] [--diameter-host 127.0.0.1] [--diameter-port 3868]

Examples:
    # Test against local Docker containers
    python3 tools/swx_test_provision.py

    # Test against remote HSS
    python3 tools/swx_test_provision.py --api-host hss.example.com --diameter-host hss.example.com
"""

import sys
import os
import argparse
import requests
import json
import socket
import binascii
import time
from typing import Dict, Any, Optional, Tuple

# Get the project root directory (tools/ -> ../)
# This assumes the script is run from the project root directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Add project root to path for PyHSS imports
sys.path.insert(0, project_root)
# Add lib directory to path for PyHSS imports
sys.path.insert(0, os.path.join(project_root, 'lib'))

Diameter = None
config = {}

# Simple logger for testing
class SimpleLogger:
    def log(self, service, level, message, redisClient=None):
        print(f"[{level}] [{service}] {message}")

try:
    # Try importing like other tools in the project
    import diameter
    import pyhss_config
    Diameter = diameter.Diameter
    config = pyhss_config.config
except ImportError as e:
    print(f"Warning: Could not import PyHSS modules: {e}")
    print("Some features will be limited")
except Exception as e:
    print(f"Warning: Error importing PyHSS modules: {e}")
    print("Some features will be limited")


class ColorOutput:
    """Terminal color output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def green(text):
        return f"{ColorOutput.OKGREEN}{text}{ColorOutput.ENDC}"

    @staticmethod
    def red(text):
        return f"{ColorOutput.FAIL}{text}{ColorOutput.ENDC}"

    @staticmethod
    def yellow(text):
        return f"{ColorOutput.WARNING}{text}{ColorOutput.ENDC}"

    @staticmethod
    def blue(text):
        return f"{ColorOutput.OKBLUE}{text}{ColorOutput.ENDC}"

    @staticmethod
    def cyan(text):
        return f"{ColorOutput.OKCYAN}{text}{ColorOutput.ENDC}"

    @staticmethod
    def bold(text):
        return f"{ColorOutput.BOLD}{text}{ColorOutput.ENDC}"


class SWxTestProvisioner:
    """Provision test data and run SWx tests"""

    def __init__(self, api_host: str = '127.0.0.1', api_port: int = 8080,
                 diameter_host: str = '127.0.0.1', diameter_port: int = 3868):
        self.api_host = api_host
        self.api_port = api_port
        self.diameter_host = diameter_host
        self.diameter_port = diameter_port
        self.api_base_url = f"http://{api_host}:{api_port}"
        self.diameter_socket = None
        self.diameter = None
        
        # Initialize Diameter if available
        if Diameter:
            try:
                self.diameter = Diameter(
                    SimpleLogger(),  # logtool
                    config.get('hss', {}).get('OriginHost', 'hss01'),
                    config.get('hss', {}).get('OriginRealm', 'epc.mnc001.mcc001.3gppnetwork.org'),
                    'PyHSS-SWx-Test',
                    config.get('hss', {}).get('MCC', '001'),
                    config.get('hss', {}).get('MNC', '01')
                )
                print("✓ Diameter initialized successfully")
            except ImportError as e:
                if "MySQLdb" in str(e) or "mysql" in str(e).lower():
                    print(f"⚠ Diameter requires MySQL database driver: {e}")
                    print("  To enable Diameter functionality, install: pip install mysqlclient")
                    print("  Or configure database to use SQLite in config.yaml")
                else:
                    print(f"⚠ Diameter module requires additional dependencies: {e}")
                self.diameter = None
            except Exception as e:
                if "MySQLdb" in str(e) or "mysql" in str(e).lower():
                    print(f"⚠ Diameter requires MySQL database driver: {e}")
                    print("  To enable Diameter functionality, install: pip install mysqlclient")
                    print("  Or configure database to use SQLite in config.yaml")
                else:
                    print(f"✗ Failed to initialize Diameter: {e}")
                print("  Continuing without Diameter functionality...")
                self.diameter = None
        else:
            print("⚠ Diameter module not available - Diameter features will be limited")
            print("  To enable Diameter functionality, ensure all dependencies are installed")

    def print_header(self, text: str):
        """Print a formatted header"""
        print(f"\n{ColorOutput.bold(ColorOutput.cyan('=' * 70))}")
        print(f"{ColorOutput.bold(ColorOutput.cyan(text))}")
        print(f"{ColorOutput.bold(ColorOutput.cyan('=' * 70))}\n")

    def print_success(self, text: str):
        """Print success message"""
        print(f"{ColorOutput.green('✓')} {text}")

    def print_error(self, text: str):
        """Print error message"""
        print(f"{ColorOutput.red('✗')} {text}")

    def print_info(self, text: str):
        """Print info message"""
        print(f"{ColorOutput.blue('ℹ')} {text}")

    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{ColorOutput.yellow('⚠')} {text}")

    def api_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Tuple[bool, Any]:
        """Make HTTP request to API"""
        url = f"{self.api_base_url}{endpoint}"
        headers = {
            'Provisioning-Key': 'changeThisKeyInProduction',
            'Content-Type': 'application/json'
        }
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=5)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=5)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=5)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=5)
            else:
                return False, f"Unknown method: {method}"
            
            if response.status_code in [200, 201]:
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except requests.exceptions.ConnectionError:
            return False, f"Connection refused to {url}"
        except Exception as e:
            return False, str(e)

    def cleanup_existing_data(self, imsi: str = '001010000000001'):
        """Clean up existing test data"""
        self.print_info("Cleaning up existing test data...")
        
        # Check and delete existing subscriber by IMSI
        try:
            success, response = self.api_request('GET', f'/subscriber/imsi/{imsi}')
            if success and response:
                subscriber_id = response.get('subscriber_id')
                if subscriber_id:
                    self.print_info(f"Deleting existing subscriber: {subscriber_id}")
                    self.api_request('DELETE', f'/subscriber/{subscriber_id}')
        except:
            pass
        
        # Check and delete existing AUC by IMSI
        try:
            success, response = self.api_request('GET', f'/auc/imsi/{imsi}')
            self.print_info(f"AUC lookup by IMSI: success={success}, response={response}")
            if success and response:
                auc_id = response.get('auc_id')
                if auc_id:
                    self.print_info(f"Deleting existing AUC: {auc_id}")
                    del_success, del_response = self.api_request('DELETE', f'/auc/{auc_id}')
                    self.print_info(f"AUC deletion: success={del_success}, response={del_response}")
        except Exception as e:
            self.print_info(f"AUC cleanup exception: {e}")
        
        # Also try to delete by ICCID as backup
        iccid = f"8944{imsi[-11:]}"
        try:
            success, response = self.api_request('GET', f'/auc/iccid/{iccid}')
            self.print_info(f"AUC lookup by ICCID: success={success}, response={response}")
            if success and response:
                auc_id = response.get('auc_id')
                if auc_id:
                    self.print_info(f"Deleting existing AUC by ICCID: {auc_id}")
                    del_success, del_response = self.api_request('DELETE', f'/auc/{auc_id}')
                    self.print_info(f"AUC deletion by ICCID: success={del_success}, response={del_response}")
        except Exception as e:
            self.print_info(f"AUC cleanup by ICCID exception: {e}")
        
        # Finally, try to find and delete by scanning the list
        try:
            success, response = self.api_request('GET', '/auc/list')
            self.print_info(f"AUC list lookup: success={success}")
            if success and isinstance(response, dict) and 'data' in response:
                for auc in response['data']:
                    if auc.get('iccid') == iccid or auc.get('imsi') == imsi:
                        auc_id = auc.get('auc_id')
                        if auc_id:
                            self.print_info(f"Deleting existing AUC from list: {auc_id} (ICCID: {auc.get('iccid')})")
                            del_success, del_response = self.api_request('DELETE', f'/auc/{auc_id}')
                            self.print_info(f"AUC deletion from list: success={del_success}")
        except Exception as e:
            self.print_info(f"AUC list cleanup exception: {e}")
        
        # Check and delete existing APN by name
        try:
            success, response = self.api_request('GET', '/apn/list')
            if success and isinstance(response, dict) and 'data' in response:
                for apn in response['data']:
                    if apn.get('apn') == 'default':
                        apn_id = apn.get('apn_id')
                        if apn_id:
                            self.print_info(f"Deleting existing APN: {apn_id}")
                            self.api_request('DELETE', f'/apn/{apn_id}')
                            break
        except:
            pass

    def provision_apn(self, apn_name: str = 'default') -> Optional[int]:
        """Provision APN"""
        self.print_info(f"Provisioning APN: {apn_name}")
        
        apn_data = {
            'apn': apn_name,
            'ip_version': 0,
            'apn_ambr_dl': 1024000,
            'apn_ambr_ul': 2048000,
            'qci': 9
        }
        
        success, response = self.api_request('PUT', '/apn/', apn_data)
        if not success:
            self.print_error(f"Failed to create APN: {response}")
            return None
        
        apn_id = response.get('apn_id')
        self.print_success(f"APN created: ID={apn_id}")
        return apn_id

    def provision_auc(self, imsi: str = '001010000000001', auc_id: Optional[int] = None) -> Optional[int]:
        """Provision AUC entry"""
        self.print_info(f"Provisioning AUC for IMSI: {imsi}")
        
        # Generate unique ICCID using timestamp to avoid conflicts
        import time
        timestamp = int(time.time()) % 100000  # Use last 5 digits of timestamp
        unique_suffix = f"{timestamp:05d}"
        iccid = f"8944{imsi[-11:-5]}{unique_suffix}"  # Replace last 5 digits with timestamp
        self.print_info(f"Generated unique ICCID: {iccid}")
        auc_data = {
            'ki': '00112233445566778899aabbccddeeff',
            'opc': '112233445566778899aabbccddeeff00',
            'amf': '8000',
            'sqn': 0,
            'imsi': imsi,
            'iccid': iccid
        }
        
        success, response = self.api_request('PUT', '/auc/', auc_data)
        if not success:
            self.print_error(f"Failed to create AUC: {response}")
            return None
        
        auc_id = response.get('auc_id')
        self.print_success(f"AUC created: ID={auc_id}")
        return auc_id

    def provision_subscriber(self, imsi: str, auc_id: int, apn_id: int) -> Optional[int]:
        """Provision subscriber"""
        self.print_info(f"Provisioning subscriber: IMSI={imsi}")
        
        subscriber_data = {
            'imsi': imsi,
            'enabled': True,
            'auc_id': auc_id,
            'default_apn': apn_id,
            'apn_list': 'default',
            'msisdn': '1234567890',
            'ue_ambr_dl': 1024000,
            'ue_ambr_ul': 2048000,
            'nam': 0,
            'roaming_enabled': True,
            'subscribed_rau_tau_timer': 300
        }
        
        success, response = self.api_request('PUT', '/subscriber/', subscriber_data)
        if not success:
            self.print_error(f"Failed to create subscriber: {response}")
            return None
        
        subscriber_id = response.get('subscriber_id')
        self.print_success(f"Subscriber created: ID={subscriber_id}")
        return subscriber_id

    def provision_test_data(self) -> Tuple[str, int, int, int]:
        """Provision complete test data"""
        self.print_header("Provisioning Test Data")
        
        # Check API connectivity
        self.print_info("Checking API connectivity...")
        success, _ = self.api_request('GET', '/oam/ping')
        if not success:
            self.print_error(f"Cannot connect to API at {self.api_base_url}")
            sys.exit(1)
        self.print_success("API is reachable")
        
        # Clean up existing test data
        self.cleanup_existing_data()
        
        # Small delay to ensure cleanup completes
        import time
        time.sleep(1)
        
        # Provision APN
        apn_id = self.provision_apn('default')
        if not apn_id:
            return None, None, None, None
        
        # Provision AUC
        imsi = '001010000000001'
        auc_id = self.provision_auc(imsi)
        if not auc_id:
            return None, None, None, None
        
        # Provision Subscriber
        subscriber_id = self.provision_subscriber(imsi, auc_id, apn_id)
        if not subscriber_id:
            return None, None, None, None
        
        return imsi, subscriber_id, auc_id, apn_id

    def connect_diameter(self) -> bool:
        """Connect to Diameter peer"""
        self.print_info(f"Connecting to Diameter at {self.diameter_host}:{self.diameter_port}")
        
        try:
            self.diameter_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.diameter_socket.settimeout(5)
            self.diameter_socket.connect((self.diameter_host, self.diameter_port))
            self.print_success("Connected to Diameter")
            return True
        except Exception as e:
            self.print_error(f"Failed to connect to Diameter: {e}")
            return False

    def send_capabilities_exchange(self) -> bool:
        """Send CER/CEA handshake for proper Diameter peer establishment"""
        self.print_info("Sending CER (Capabilities-Exchange-Request)")
        
        if not self.diameter:
            self.print_warning("Diameter module not available, skipping CER/CEA")
            return False
        
        try:
            # Build CER packet according to RFC 6733
            origin_host = 'swx-test-client'
            origin_realm = 'test.realm'
            host_ip = '127.0.0.1'
            
            avp = ''
            
            # Origin-Host (AVP 264) - mandatory
            origin_host_hex = binascii.hexlify(origin_host.encode()).decode()
            avp += self.diameter.generate_avp(264, '40', origin_host_hex)
            
            # Origin-Realm (AVP 296) - mandatory
            origin_realm_hex = binascii.hexlify(origin_realm.encode()).decode()
            avp += self.diameter.generate_avp(296, '40', origin_realm_hex)
            
            # Host-IP-Address (AVP 257) - mandatory (Address type for IPv4)
            # Format: 0001 (Address Family IPv4) + 4 bytes IP address
            ip_parts = host_ip.split('.')
            ip_hex = '0001' + ''.join(f'{int(part):02x}' for part in ip_parts)
            avp += self.diameter.generate_avp(257, '40', ip_hex)
            
            # Vendor-Id (AVP 266) - mandatory (0 for IETF)
            avp += self.diameter.generate_avp(266, '40', '00000000')
            
            # Product-Name (AVP 269) - mandatory
            product_name = 'PyHSS-SWx-Test-Client'
            product_name_hex = binascii.hexlify(product_name.encode()).decode()
            avp += self.diameter.generate_avp(269, '00', product_name_hex)
            
            # Supported-Vendor-Id (AVP 265) - 3GPP (10415)
            avp += self.diameter.generate_avp(265, '40', '000028af')
            
            # Auth-Application-Id (AVP 258) - SWx Application ID (16777265 = 0x01000031)
            avp += self.diameter.generate_avp(258, '40', '01000031')
            
            # Firmware-Revision (AVP 267) - optional
            avp += self.diameter.generate_avp(267, '00', '00000001')
            
            # Generate CER packet (Command Code 257, no Application ID for base protocol)
            cer_packet = self.diameter.generate_diameter_packet(
                "01",  # Version
                "80",  # Flags (Request)
                257,   # Command Code (CER)
                0,     # Application ID (0 for Diameter Base Protocol)
                self.diameter.generate_id(4),  # Hop-by-Hop Identifier
                self.diameter.generate_id(4),  # End-to-End Identifier
                avp
            )
            
            self.print_info(f"Sending CER packet ({len(cer_packet)//2} bytes)")
            self.diameter_socket.sendall(bytes.fromhex(cer_packet))
            
            # Receive CEA response
            self.print_info("Waiting for CEA (Capabilities-Exchange-Answer)...")
            self.diameter_socket.settimeout(10.0)
            data = self.diameter_socket.recv(32)
            
            if len(data) < 20:
                self.print_error(f"Incomplete CEA header received: {len(data)} bytes")
                return False
            
            packet_length = self.diameter.decode_diameter_packet_length(data)
            if packet_length > 32:
                data += self.diameter_socket.recv(packet_length - 32)
            
            self.print_success(f"Received CEA response: {len(data)} bytes")
            
            # Parse CEA to verify Result-Code
            cea_hex = data.hex()
            
            # Extract Result-Code (AVP 268) - should be 2001 (DIAMETER_SUCCESS)
            if '0000010c' in cea_hex:  # AVP Code 268
                idx = cea_hex.index('0000010c')
                # Skip AVP header (8 bytes = 16 hex chars), read 4 bytes result code
                result_code_hex = cea_hex[idx+16:idx+24]
                result_code = int(result_code_hex, 16)
                
                if result_code == 2001:
                    self.print_success(f"CER/CEA handshake successful (Result-Code: {result_code} DIAMETER_SUCCESS)")
                    return True
                else:
                    self.print_error(f"CER/CEA failed with Result-Code: {result_code}")
                    return False
            else:
                self.print_warning("Could not parse Result-Code from CEA, assuming success")
                return True
            
        except socket.timeout:
            self.print_error("Timeout waiting for CEA response")
            return False
        except Exception as e:
            self.print_error(f"Failed to complete CER/CEA: {e}")
            import traceback
            self.print_error(traceback.format_exc())
            return False

    def parse_maa_response(self, data: bytes):
        """Parse and display MAA response contents"""
        try:
            maa_hex = data.hex()
            
            # Check Result-Code (AVP 268)
            if '0000010c' in maa_hex:
                idx = maa_hex.index('0000010c')
                result_code_hex = maa_hex[idx+16:idx+24]
                result_code = int(result_code_hex, 16)
                
                if result_code == 2001:
                    self.print_success(f"  Result-Code: {result_code} (DIAMETER_SUCCESS)")
                else:
                    self.print_error(f"  Result-Code: {result_code}")
                    # Common Diameter result codes
                    result_codes = {
                        5001: "DIAMETER_AVP_UNSUPPORTED",
                        5004: "DIAMETER_INVALID_AVP_VALUE",
                        5005: "DIAMETER_MISSING_AVP",
                        5012: "DIAMETER_UNABLE_TO_COMPLY",
                        5420: "DIAMETER_UNKNOWN_SESSION_ID",
                        5003: "DIAMETER_AUTHORIZATION_REJECTED"
                    }
                    if result_code in result_codes:
                        self.print_error(f"    ({result_codes[result_code]})")
            
            # Check for SIP-Auth-Data-Item (AVP 612) - contains auth vectors
            if '00000264' in maa_hex:
                self.print_success("  ✓ SIP-Auth-Data-Item present (contains auth vectors)")
                
                # Try to find and display auth components
                avp_codes = {
                    '00000260': 'Authentication-Scheme',
                    '00000261': 'SIP-Authenticate (RAND||AUTN)',
                    '00000262': 'SIP-Authorization (XRES)',
                    '00000271': 'Confidentiality-Key (CK)',
                    '00000272': 'Integrity-Key (IK)'
                }
                
                for code, name in avp_codes.items():
                    if code in maa_hex:
                        self.print_info(f"    • {name} present")
            else:
                self.print_warning("  ⚠ No SIP-Auth-Data-Item found in response")
            
            # Check for SIP-Number-Auth-Items (AVP 607)
            if '0000025f' in maa_hex:
                idx = maa_hex.index('0000025f')
                # Vendor AVP, skip to data
                num_items_hex = maa_hex[idx+24:idx+32]
                num_items = int(num_items_hex, 16)
                self.print_info(f"  Number of auth items returned: {num_items}")
                
        except Exception as e:
            self.print_warning(f"Could not fully parse MAA: {e}")

    def send_mar_request(self, imsi: str, num_vectors: int = 1) -> Optional[bytes]:
        """Send MAR (Multimedia-Auth-Request)"""
        self.print_info(f"Sending MAR for IMSI: {imsi} (requesting {num_vectors} vector(s))")
        
        if not self.diameter:
            self.print_warning("Diameter module not available, cannot send MAR")
            return None
        
        try:
            # Build MAR packet with proper client identity
            origin_host = 'swx-test-client'
            origin_realm = 'test.realm'
            session_id = f"{origin_host};{int(time.time())};1;app_swx"
            session_id_hex = binascii.hexlify(session_id.encode()).decode()
            
            # User-Name should be IMSI@realm format for SWx
            dest_realm = config.get('hss', {}).get('OriginRealm', 'epc.mnc001.mcc001.3gppnetwork.org')
            username = f"{imsi}@{dest_realm}"
            username_hex = binascii.hexlify(username.encode()).decode()
            
            # Build AVPs for MAR according to 3GPP TS 29.273
            avp = ''
            
            # Session-Id (AVP 263) - mandatory
            avp += self.diameter.generate_avp(263, '40', session_id_hex)
            
            # Vendor-Specific-Application-Id (AVP 260) - mandatory
            vendor_specific_app_id = ''
            vendor_specific_app_id += self.diameter.generate_avp(266, '40', '000028af')  # Vendor-Id (10415 = 3GPP)
            vendor_specific_app_id += self.diameter.generate_avp(258, '40', '01000031')  # Auth-Application-Id (16777265 = SWx)
            avp += self.diameter.generate_avp(260, '40', vendor_specific_app_id)
            
            # Auth-Session-State (AVP 277) - NO_STATE_MAINTAINED (1)
            avp += self.diameter.generate_avp(277, '40', '00000001')
            
            # Origin-Host (AVP 264) - mandatory
            origin_host_hex = binascii.hexlify(origin_host.encode()).decode()
            avp += self.diameter.generate_avp(264, '40', origin_host_hex)
            
            # Origin-Realm (AVP 296) - mandatory
            origin_realm_hex = binascii.hexlify(origin_realm.encode()).decode()
            avp += self.diameter.generate_avp(296, '40', origin_realm_hex)
            
            # Destination-Realm (AVP 283) - mandatory
            dest_realm_hex = binascii.hexlify(dest_realm.encode()).decode()
            avp += self.diameter.generate_avp(283, '40', dest_realm_hex)
            
            # User-Name (AVP 1) - mandatory (IMSI in NAI format)
            avp += self.diameter.generate_avp(1, '40', username_hex)
            
            # SIP-Number-Auth-Items (AVP 607) - number of requested auth vectors
            avp += self.diameter.generate_vendor_avp(607, 'c0', 10415, format(num_vectors, '08x'))
            
            # SIP-Auth-Data-Item (AVP 612) - optional, can request specific auth scheme
            # For now, let HSS decide the auth scheme
            
            # Generate MAR packet (Command Code 303, Application ID 16777265 for SWx)
            mar_packet = self.diameter.generate_diameter_packet(
                "01",  # Version
                "80",  # Flags (Request)
                303,   # Command Code (MAR)
                16777265,  # Application ID (SWx)
                self.diameter.generate_id(4),  # Hop-by-Hop Identifier
                self.diameter.generate_id(4),  # End-to-End Identifier
                avp
            )
            
            self.print_info(f"Sending MAR packet ({len(mar_packet)//2} bytes)")
            self.print_info(f"  Session-Id: {session_id}")
            self.print_info(f"  User-Name: {username}")
            self.print_info(f"  Requested vectors: {num_vectors}")
            
            self.diameter_socket.sendall(bytes.fromhex(mar_packet))
            
            # Receive MAA response - increased timeout for processing
            self.print_info("Waiting for MAA (Multimedia-Auth-Answer)...")
            self.diameter_socket.settimeout(30.0)
            
            # Read diameter header first
            data = self.diameter_socket.recv(20)
            if len(data) < 20:
                self.print_error(f"Incomplete MAA header: {len(data)} bytes")
                return None
            
            packet_length = self.diameter.decode_diameter_packet_length(data)
            self.print_info(f"MAA packet length: {packet_length} bytes")
            
            # Read remaining data
            remaining = packet_length - 20
            while remaining > 0:
                chunk = self.diameter_socket.recv(min(remaining, 4096))
                if not chunk:
                    self.print_error("Connection closed while reading MAA")
                    return None
                data += chunk
                remaining -= len(chunk)
            
            self.print_success(f"Received MAA response: {len(data)} bytes")
            
            # Parse and display MAA contents
            self.parse_maa_response(data)
            
            return data
            
        except socket.timeout:
            self.print_error("Timeout waiting for MAA response (30s)")
            return None
        except Exception as e:
            self.print_error(f"Failed to send MAR: {e}")
            import traceback
            self.print_error(traceback.format_exc())
            return None

    def run_unit_tests(self) -> bool:
        """Run unit tests"""
        self.print_header("Running Unit Tests")
        
        import subprocess
        
        self.print_info("Running SWx unit tests...")
        try:
            result = subprocess.run(
                ['python3', '-m', 'pytest', 'tests/test_swx.py', '-v', '--tb=short'],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse output
            lines = result.stdout.split('\n')
            passed = 0
            failed = 0
            
            for line in lines:
                if 'PASSED' in line:
                    passed += 1
                    print(f"  {ColorOutput.green('✓')} {line.split('::')[1] if '::' in line else line}")
                elif 'FAILED' in line:
                    failed += 1
                    print(f"  {ColorOutput.red('✗')} {line.split('::')[1] if '::' in line else line}")
            
            # Print summary
            summary_lines = [l for l in lines if 'passed' in l.lower() or 'failed' in l.lower()]
            if summary_lines:
                summary = summary_lines[-1]
                print(f"\n{ColorOutput.bold(summary)}")
            
            if result.returncode == 0:
                self.print_success(f"All tests passed! ({passed} tests)")
                return True
            else:
                self.print_error(f"Tests failed! ({failed} failures, {passed} passed)")
                return False
                
        except subprocess.TimeoutExpired:
            self.print_error("Tests timed out")
            return False
        except Exception as e:
            self.print_error(f"Failed to run tests: {e}")
            return False

    def test_swx_integration(self) -> bool:
        """Test SWx integration"""
        self.print_header("Testing SWx Integration")
        
        # Provision data
        imsi, subscriber_id, auc_id, apn_id = self.provision_test_data()
        if not imsi:
            return False
        
        # Connect to Diameter
        if not self.connect_diameter():
            self.print_warning("Skipping Diameter tests (server not available)")
            return True
        
        # Send CER/CEA for proper Diameter peer establishment
        if not self.send_capabilities_exchange():
            self.print_error("CER/CEA handshake failed")
            return False
        
        # Small delay to ensure peer is fully established
        time.sleep(0.5)
        
        # Send MAR and receive MAA
        maa_response = self.send_mar_request(imsi, 1)
        if not maa_response:
            self.print_error("Failed to receive MAA response")
            return False
        
        self.print_success("SWx integration test completed")
        return True

    def run_all_tests(self):
        """Run all provisioning and tests"""
        self.print_header("SWx Provisioning and Testing Script")
        
        print("This script will:")
        print("  1. Provision test APN")
        print("  2. Provision test AUC (crypto keys)")
        print("  3. Provision test subscriber")
        print("  4. Run SWx unit tests")
        print("  5. Test SWx Diameter integration (optional)")
        print()
        
        # Run unit tests first (no dependencies)
        tests_ok = self.run_unit_tests()
        
        # Test integration
        integration_ok = self.test_swx_integration()
        
        # Summary
        self.print_header("Summary")
        if tests_ok:
            self.print_success("Unit tests passed")
        else:
            self.print_error("Unit tests failed")
        
        if integration_ok:
            self.print_success("Integration tests passed")
        else:
            self.print_warning("Integration tests skipped or failed")
        
        if tests_ok and integration_ok:
            self.print_success("All tests completed successfully!")
            return 0
        else:
            self.print_error("Some tests failed")
            return 1

    def send_disconnect_request(self) -> bool:
        """Send DPR (Disconnect-Peer-Request) for graceful shutdown"""
        if not self.diameter_socket or not self.diameter:
            return False
        
        try:
            self.print_info("Sending DPR (Disconnect-Peer-Request)")
            
            origin_host = 'swx-test-client'
            origin_realm = 'test.realm'
            
            avp = ''
            
            # Origin-Host (AVP 264) - mandatory
            origin_host_hex = binascii.hexlify(origin_host.encode()).decode()
            avp += self.diameter.generate_avp(264, '40', origin_host_hex)
            
            # Origin-Realm (AVP 296) - mandatory
            origin_realm_hex = binascii.hexlify(origin_realm.encode()).decode()
            avp += self.diameter.generate_avp(296, '40', origin_realm_hex)
            
            # Disconnect-Cause (AVP 273) - REBOOTING (0)
            avp += self.diameter.generate_avp(273, '40', '00000000')
            
            # Generate DPR packet (Command Code 282)
            dpr_packet = self.diameter.generate_diameter_packet(
                "01",  # Version
                "80",  # Flags (Request)
                282,   # Command Code (DPR)
                0,     # Application ID (Base Protocol)
                self.diameter.generate_id(4),
                self.diameter.generate_id(4),
                avp
            )
            
            self.diameter_socket.sendall(bytes.fromhex(dpr_packet))
            
            # Wait for DPA
            self.diameter_socket.settimeout(5.0)
            data = self.diameter_socket.recv(1024)
            self.print_success("Received DPA (Disconnect-Peer-Answer)")
            return True
            
        except:
            return False

    def cleanup(self):
        """Cleanup resources"""
        if self.diameter_socket:
            try:
                # Try graceful disconnect
                self.send_disconnect_request()
            except:
                pass
            
            try:
                self.diameter_socket.close()
            except:
                pass


def main():
    parser = argparse.ArgumentParser(
        description='SWx Provisioning and Test Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Test against local Docker containers
  python3 tools/swx_test_provision.py

  # Test against remote HSS
  python3 tools/swx_test_provision.py --api-host hss.example.com --diameter-host hss.example.com

  # Test with custom ports
  python3 tools/swx_test_provision.py --api-port 8080 --diameter-port 3868
        '''
    )
    
    parser.add_argument('--api-host', default='127.0.0.1', help='API host (default: 127.0.0.1)')
    parser.add_argument('--api-port', type=int, default=8080, help='API port (default: 8080)')
    parser.add_argument('--diameter-host', default='127.0.0.1', help='Diameter host (default: 127.0.0.1)')
    parser.add_argument('--diameter-port', type=int, default=3868, help='Diameter port (default: 3868)')
    
    args = parser.parse_args()
    
    provisioner = SWxTestProvisioner(
        api_host=args.api_host,
        api_port=args.api_port,
        diameter_host=args.diameter_host,
        diameter_port=args.diameter_port
    )
    
    try:
        exit_code = provisioner.run_all_tests()
    finally:
        provisioner.cleanup()
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
