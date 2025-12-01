import binascii
from Crypto.Random import random
from milenage import Milenage
from pyhss_config import config
from database import Database
from logtool import LogTool

class SWx:
    def __init__(self, logTool, db=None):
        if db:
            self.db = db
        else:
            self.db = Database(logTool=logTool)
        self.logTool = logTool
        self.milenage = Milenage()
        self.mcc = config.get('hss', {}).get('MCC', '999')
        self.mnc = config.get('hss', {}).get('MNC', '999')

    def generate_swx_auth_vectors(self, imsi, num_vectors):
        self.logTool.log(service='HSS', level='info', message=f"[swx.py] Generating {num_vectors} SWx auth vectors for {imsi}")
        try:
            subscriber = self.db.Get_Subscriber(imsi=imsi)
            if not subscriber:
                self.logTool.log(service='HSS', level='error', message=f"[swx.py] Subscriber {imsi} not found")
                return None

            # Get AUC data which contains the Ki and OPc keys
            auc = self.db.Get_AuC(auc_id=subscriber['auc_id'])
            if not auc:
                self.logTool.log(service='HSS', level='error', message=f"[swx.py] AUC data not found for subscriber {imsi}")
                return None

            key = binascii.unhexlify(auc['ki'])
            opc = binascii.unhexlify(auc['opc'])
            sqn = int(auc['sqn'])
            
            plmn = self._encode_plmn(self.mcc, self.mnc)

            vectors = []
            for _ in range(num_vectors):
                sqn += 1
                rand, xres, autn, ck, ik = self.milenage.generate_maa_vector(key, opc, sqn, plmn)
                vectors.append({
                    'rand': rand,
                    'xres': xres,
                    'autn': autn,
                    'ck': ck,
                    'ik': ik
                })
            
            # Update AUC SQN - increment by 100 as per 3GPP specs
            self.db.Update_AuC(auc['auc_id'], sqn=sqn+100)
            return vectors

        except Exception as e:
            self.logTool.log(service='HSS', level='error', message=f"[swx.py] Error generating SWx auth vectors: {e}")
            return None

    def _encode_plmn(self, mcc, mnc):
        mcc = str(mcc)
        mnc = str(mnc)
        if len(mnc) == 2:
            mnc = '0' + mnc
        
        plmn = ''
        plmn += mcc[1] + mcc[0]
        plmn += mnc[2] + mcc[2]
        plmn += mnc[1] + mnc[0]
        return binascii.unhexlify(plmn)
