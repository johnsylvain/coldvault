"""
Tests for encryption utilities
"""
import pytest
import os
import tempfile
from app.encryption import encrypt_file, decrypt_file, derive_key


class TestEncryption:
    """Test encryption functions"""
    
    def test_derive_key(self):
        """Test key derivation"""
        password = "test-password"
        key = derive_key(password)
        
        assert key is not None
        assert len(key) == 44  # Base64 encoded 32-byte key
        assert isinstance(key, bytes)
        
        # Same password should produce same key
        key2 = derive_key(password)
        assert key == key2
        
        # Different password should produce different key
        key3 = derive_key("different-password")
        assert key != key3
    
    def test_encrypt_decrypt_file(self, temp_dir):
        """Test file encryption and decryption"""
        # Create a test file
        original_content = b"This is test content for encryption"
        original_path = os.path.join(temp_dir, "original.txt")
        encrypted_path = os.path.join(temp_dir, "encrypted.bin")
        decrypted_path = os.path.join(temp_dir, "decrypted.txt")
        
        with open(original_path, "wb") as f:
            f.write(original_content)
        
        password = "test-encryption-password"
        
        # Encrypt
        encrypt_file(original_path, encrypted_path, password)
        assert os.path.exists(encrypted_path)
        
        # Verify encrypted file is different
        with open(encrypted_path, "rb") as f:
            encrypted_content = f.read()
        assert encrypted_content != original_content
        
        # Decrypt
        decrypt_file(encrypted_path, decrypted_path, password)
        assert os.path.exists(decrypted_path)
        
        # Verify decrypted content matches original
        with open(decrypted_path, "rb") as f:
            decrypted_content = f.read()
        assert decrypted_content == original_content
    
    def test_encrypt_file_no_password(self, temp_dir):
        """Test encryption fails without password"""
        original_path = os.path.join(temp_dir, "original.txt")
        encrypted_path = os.path.join(temp_dir, "encrypted.bin")
        
        with open(original_path, "wb") as f:
            f.write(b"test content")
        
        with pytest.raises(ValueError, match="Encryption password required"):
            encrypt_file(original_path, encrypted_path, "")
    
    def test_decrypt_file_no_password(self, temp_dir):
        """Test decryption fails without password"""
        encrypted_path = os.path.join(temp_dir, "encrypted.bin")
        
        with open(encrypted_path, "wb") as f:
            f.write(b"fake encrypted data")
        
        decrypted_path = os.path.join(temp_dir, "decrypted.txt")
        
        with pytest.raises(ValueError, match="Decryption password required"):
            decrypt_file(encrypted_path, decrypted_path, "")
    
    def test_decrypt_file_wrong_password(self, temp_dir):
        """Test decryption fails with wrong password"""
        original_path = os.path.join(temp_dir, "original.txt")
        encrypted_path = os.path.join(temp_dir, "encrypted.bin")
        decrypted_path = os.path.join(temp_dir, "decrypted.txt")
        
        with open(original_path, "wb") as f:
            f.write(b"test content")
        
        password = "correct-password"
        encrypt_file(original_path, encrypted_path, password)
        
        # Try to decrypt with wrong password
        with pytest.raises(Exception):  # Should raise cryptography exception
            decrypt_file(encrypted_path, decrypted_path, "wrong-password")
    
    def test_encrypt_file_not_found(self, temp_dir):
        """Test encryption fails when input file doesn't exist"""
        non_existent_path = os.path.join(temp_dir, "nonexistent.txt")
        encrypted_path = os.path.join(temp_dir, "encrypted.bin")
        
        with pytest.raises(FileNotFoundError):
            encrypt_file(non_existent_path, encrypted_path, "password")
