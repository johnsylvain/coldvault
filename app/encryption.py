"""
Encryption utilities
"""
from cryptography.fernet import Fernet
import hashlib
import base64
import logging

logger = logging.getLogger(__name__)

def derive_key(password: str) -> bytes:
    """Derive encryption key from password"""
    # Use SHA256 to derive a 32-byte key
    key = hashlib.sha256(password.encode()).digest()
    # Encode to base64 for Fernet
    return base64.urlsafe_b64encode(key)

def encrypt_file(input_path: str, output_path: str, password: str):
    """Encrypt a file"""
    if not password:
        raise ValueError("Encryption password required")
    
    key = derive_key(password)
    fernet = Fernet(key)
    
    with open(input_path, 'rb') as f:
        data = f.read()
    
    encrypted_data = fernet.encrypt(data)
    
    with open(output_path, 'wb') as f:
        f.write(encrypted_data)
    
    logger.info(f"Encrypted {input_path} to {output_path}")

def decrypt_file(input_path: str, output_path: str, password: str):
    """Decrypt a file"""
    if not password:
        raise ValueError("Decryption password required")
    
    key = derive_key(password)
    fernet = Fernet(key)
    
    with open(input_path, 'rb') as f:
        encrypted_data = f.read()
    
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise
    
    with open(output_path, 'wb') as f:
        f.write(decrypted_data)
    
    logger.info(f"Decrypted {input_path} to {output_path}")
