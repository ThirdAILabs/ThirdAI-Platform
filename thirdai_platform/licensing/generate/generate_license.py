# license_generation.py

import argparse
import base64
import json
import os
from datetime import datetime, timezone

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

parser = argparse.ArgumentParser()
parser.add_argument(
    "--thirdai_key",
    type=str,
    required=True,
    help="The thirdai license key to use for the Platform license.",
)

args = parser.parse_args()

cpu_mhz_limit = 100000000
expiry_date = datetime(year=2030, month=4, day=3, tzinfo=timezone.utc)

licensing_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Load the private key
with open(os.path.join(licensing_dir, "generate", "private_key.pem"), "rb") as f:
    private_key = serialization.load_pem_private_key(
        f.read(), password=None, backend=default_backend()
    )

# License information
license_info = {
    "cpuMhzLimit": str(cpu_mhz_limit),
    "expiryDate": expiry_date.isoformat(),
    "boltLicenseKey": args.thirdai_key,
}

# Serialize license information
license_str = json.dumps(license_info, separators=(",", ":"))

# Sign the license
signature = private_key.sign(
    license_str.encode(),
    padding.PKCS1v15(),
    hashes.SHA256(),
)

# Encode the signature in Base64 to embed in JSON
encoded_signature = base64.b64encode(signature).decode()

# Combine the license information and signature
ndb_enterprise_license = {"license": license_info, "signature": encoded_signature}

# Write the combined license to a file
with open("ndb_enterprise_license.json", "w") as f:
    json.dump(ndb_enterprise_license, f, indent=4)

print("Rag-on-Rails license generated and signed.")
