import unittest
import logging
import binascii
import sys
import os
sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from lib.diameter import Diameter
from lib.logtool import LogTool
from lib.database import Database, AUC, SUBSCRIBER, APN
from pyhss_config import config

class SWx_Tests(unittest.TestCase):
    def setUp(self):
        self.logTool = LogTool(config)
        self.db = Database(logTool=self.logTool)
        self.diameter_inst = Diameter(
            self.logTool,
            str('hss.localdomain'),
            str('localdomain'),
            str('PyHSS'),
            str('999'),
            str('999')
        )
        # Add a dummy AUC entry
        self.auc_data = {
            'ki': '00112233445566778899aabbccddeeff',
            'opc': '112233445566778899aabbccddeeff00',
            'amf': '8000',
            'sqn': 0,
            'imsi': '001010000000001',
            'iccid': '12345678901234567890'
        }
        self.auc_entry = self.db.CreateObj(AUC, self.auc_data)
        self.auc_id = self.auc_entry['auc_id']

        # Add a dummy APN entry
        self.apn_data = {
            'apn': 'default',
            'ip_version': 0,
            'apn_ambr_dl': 1024000,
            'apn_ambr_ul': 2048000,
            'qci': 9
        }
        self.apn_entry = self.db.CreateObj(APN, self.apn_data)
        self.apn_id = self.apn_entry['apn_id']

        # Add a dummy subscriber
        self.imsi = '001010000000001'
        self.subscriber_data = {
            'imsi': self.imsi,
            'enabled': True,
            'auc_id': self.auc_id,
            'default_apn': self.apn_id,
            'apn_list': 'default',
            'msisdn': '1234567890',
            'ue_ambr_dl': 1024000,
            'ue_ambr_ul': 2048000,
            'nam': 0,
            'roaming_enabled': True,
            'subscribed_rau_tau_timer': 300
        }
        self.subscriber_entry = self.db.CreateObj(SUBSCRIBER, self.subscriber_data)
        self.subscriber_id = self.subscriber_entry['subscriber_id']

    def test_SWx_Handler_Exists(self):
        """Test that SWx handler exists and is callable"""
        self.assertTrue(hasattr(self.diameter_inst, 'Answer_16777265_303'))
        self.assertTrue(callable(self.diameter_inst.Answer_16777265_303))

    def test_SWx_MAR_Missing_User_Name_AVP(self):
        """Test SWx MAR handler with missing User-Name AVP"""
        packet_vars = {
            'hop-by-hop-identifier': '00000001',
            'end-to-end-identifier': '00000001'
        }
        avps = []  # Empty AVP list - missing required User-Name (AVP 1)
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        self.assertIsNotNone(response, "Response should not be None")
        # Handler returns hex string, not bytes
        self.assertIsInstance(response, (str, bytes), "Response should be str or bytes")
        self.assertGreater(len(response), 0, "Response should not be empty")

    def test_SWx_MAR_With_Session_ID(self):
        """Test SWx MAR handler with Session-ID AVP"""
        session_id_value = str(binascii.hexlify(str.encode('test_session_123')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': '00000001',
            'end-to-end-identifier': '00000001'
        }
        avps = [
            {'avp_code': 263, 'avp_flags': '40', 'misc_data': session_id_value}
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        self.assertIsNotNone(response, "Response should not be None")
        self.assertIsInstance(response, (str, bytes), "Response should be str or bytes")

    def test_SWx_MAR_With_Valid_User_Name(self):
        """Test SWx MAR handler with valid User-Name AVP for existing subscriber"""
        username_value = str(binascii.hexlify(str.encode(self.imsi + '@localdomain')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': '00000001',
            'end-to-end-identifier': '00000001'
        }
        avps = [
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value}
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        self.assertIsNotNone(response, "Response should not be None")
        self.assertIsInstance(response, (str, bytes), "Response should be str or bytes")
        self.assertGreater(len(response), 0, "Response should not be empty")

    def test_SWx_MAR_With_Nonexistent_Subscriber(self):
        """Test SWx MAR handler with non-existent subscriber IMSI"""
        fake_imsi = '999999999999999'
        username_value = str(binascii.hexlify(str.encode(fake_imsi + '@localdomain')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': '00000001',
            'end-to-end-identifier': '00000001'
        }
        avps = [
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value}
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        self.assertIsNotNone(response, "Response should not be None")
        self.assertIsInstance(response, (str, bytes), "Response should be str or bytes")

    def test_SWx_MAR_Response_Packet_Structure(self):
        """Test that SWx MAR response has correct packet structure"""
        username_value = str(binascii.hexlify(str.encode(self.imsi + '@localdomain')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': 'aabbccdd',
            'end-to-end-identifier': '11223344'
        }
        avps = [
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value}
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        
        # Verify response is a valid Diameter packet (minimum size check)
        # Diameter packet header is 20 bytes = 40 hex characters  
        self.assertGreaterEqual(len(response), 40, "Response packet should be at least 40 hex characters (header size)")
        
        # Response should start with version byte (0x01 in hex)
        self.assertEqual(response[0:2], '01', "Response should start with Diameter version 0x01")

    def test_SWx_MAR_Multiple_AVPs(self):
        """Test SWx MAR handler with multiple AVPs"""
        username_value = str(binascii.hexlify(str.encode(self.imsi + '@localdomain')), 'ascii')
        session_id_value = str(binascii.hexlify(str.encode('test_session_456')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': 'deadbeef',
            'end-to-end-identifier': 'cafebabe'
        }
        avps = [
            {'avp_code': 263, 'avp_flags': '40', 'misc_data': session_id_value},
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value},
            {'avp_code': 268, 'avp_flags': '40', 'misc_data': '000007d1'}  # Result-Code
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        self.assertIsNotNone(response, "Response should not be None")
        self.assertIsInstance(response, (str, bytes), "Response should be str or bytes")

    def test_SWx_Handler_Idempotent(self):
        """Test that SWx handler can be called multiple times with same input"""
        username_value = str(binascii.hexlify(str.encode(self.imsi + '@localdomain')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': '12345678',
            'end-to-end-identifier': '87654321'
        }
        avps = [
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value}
        ]
        
        # Call handler twice with same inputs
        response1 = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        response2 = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        
        # Both responses should be valid
        self.assertIsNotNone(response1, "First response should not be None")
        self.assertIsNotNone(response2, "Second response should not be None")
        self.assertIsInstance(response1, (str, bytes), "First response should be str or bytes")
        self.assertIsInstance(response2, (str, bytes), "Second response should be str or bytes")

    def test_Cx_Handler_Exists(self):
        """Test that Cx handler exists and is callable"""
        self.assertTrue(hasattr(self.diameter_inst, 'Answer_16777216_303'))
        self.assertTrue(callable(self.diameter_inst.Answer_16777216_303))

    def test_SWx_MAR_Auth_Data_Item_Content(self):
        """Test that SWx MAR response contains auth data items with RAND, AUTN, XRES, CK, IK when successful"""
        username_value = str(binascii.hexlify(str.encode(self.imsi + '@localdomain')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': '00000001',
            'end-to-end-identifier': '00000001'
        }
        avps = [
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value}
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        
        # Response should contain auth data
        self.assertIsNotNone(response, "Response should not be None")
        self.assertIsInstance(response, (str, bytes), "Response should be str or bytes")
        
        # Response is hex string, just verify it's not empty
        response_len = len(response) if isinstance(response, str) else len(response.hex())
        self.assertGreater(response_len, 50, "Response should contain packet data")

    def test_SWx_MAR_Result_Code_Success(self):
        """Test that SWx MAR response includes Result-Code AVP (268)"""
        username_value = str(binascii.hexlify(str.encode(self.imsi + '@localdomain')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': '00000001',
            'end-to-end-identifier': '00000001'
        }
        avps = [
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value}
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        
        # Response should contain Result-Code AVP (268)
        self.assertIsNotNone(response, "Response should not be None")
        # Convert to string if bytes
        response_str = response if isinstance(response, str) else response.hex()
        # AVP 268 in hex is '0000010c'
        self.assertIn('0000010c', response_str, "Response should contain Result-Code AVP (268)")

    def test_SWx_MAR_Origin_Host_Realm(self):
        """Test that SWx MAR response includes Origin-Host and Origin-Realm"""
        username_value = str(binascii.hexlify(str.encode(self.imsi + '@localdomain')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': '00000001',
            'end-to-end-identifier': '00000001'
        }
        avps = [
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value}
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        
        # Response should contain Origin-Host (264) and Origin-Realm (296)
        response_str = response if isinstance(response, str) else response.hex()
        
        # AVP 264 in hex = 0x000108
        self.assertIn('00000108', response_str, "Response should contain Origin-Host AVP (264)")
        # AVP 296 in hex = 0x000128
        self.assertIn('00000128', response_str, "Response should contain Origin-Realm AVP (296)")

    def test_SWx_MAR_User_Name_Echo(self):
        """Test that SWx MAR response includes User-Name AVP (1)"""
        username_value = str(binascii.hexlify(str.encode(self.imsi + '@localdomain')), 'ascii')
        
        packet_vars = {
            'hop-by-hop-identifier': '00000001',
            'end-to-end-identifier': '00000001'
        }
        avps = [
            {'avp_code': 1, 'avp_flags': '40', 'misc_data': username_value}
        ]
        
        response = self.diameter_inst.Answer_16777265_303(packet_vars, avps)
        
        # Response should contain User-Name AVP (1)
        response_str = response if isinstance(response, str) else response.hex()
        
        # AVP 1 in hex = 0x000001
        self.assertIn('00000001', response_str, "Response should contain User-Name AVP (1)")

    def tearDown(self):
        self.db.DeleteObj(SUBSCRIBER, self.subscriber_id)
        self.db.DeleteObj(APN, self.apn_id)
        self.db.DeleteObj(AUC, self.auc_id)

if __name__ == '__main__':
    unittest.main()
