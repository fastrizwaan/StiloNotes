# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import tempfile
import unittest
from pathlib import Path
from gi.repository import GLib

from stilonotes.database import NoteDatabase
from stilonotes.config_manager import ConfigManager
from stilonotes import backup_encryption


class TestBackupAndEncryption(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = NoteDatabase(str(self.db_path))
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_database_backup_and_restore_plain(self):
        note1 = self.db.create_note(title="Secret Note", initial_text="Encrypted thoughts", category="Private")
        self.db.create_category("Private")
        att_id = self.db.save_attachment(note1.id, "photo.png", "image/png", b"fake_png_data")

        backup_file = Path(self.temp_dir.name) / "snapshot.db"
        self.db.backup_to_file(str(backup_file))
        self.assertTrue(backup_file.exists())
        self.assertFalse(backup_encryption.is_encrypted_file(str(backup_file)))

        # Restore to fresh db
        db2_path = Path(self.temp_dir.name) / "restored.db"
        db2 = NoteDatabase(str(db2_path))
        try:
            db2.restore_from_file(str(backup_file))
            restored_n1 = db2.get_note(note1.id)
            self.assertIsNotNone(restored_n1)
            self.assertEqual(restored_n1.title, "Secret Note")
            self.assertEqual(restored_n1.category, "Private")

            restored_att = db2.get_attachment(att_id)
            self.assertIsNotNone(restored_att)
            self.assertEqual(restored_att["data"], b"fake_png_data")
        finally:
            db2.close()

    def test_gpg_encryption_and_decryption(self):
        if not backup_encryption.is_gpg_available():
            self.skipTest("GPG not available on this system")

        note1 = self.db.create_note(title="Encrypted Note", initial_text="Classified data")
        raw_backup = Path(self.temp_dir.name) / "raw.db"
        enc_backup = Path(self.temp_dir.name) / "raw.db.gpg"
        dec_backup = Path(self.temp_dir.name) / "dec.db"

        self.db.backup_to_file(str(raw_backup))
        self.assertFalse(backup_encryption.is_encrypted_file(str(raw_backup)))

        # Encrypt with password
        password = "strong_master_password_123!"
        backup_encryption.encrypt_file(str(raw_backup), str(enc_backup), password)
        self.assertTrue(enc_backup.exists())
        self.assertTrue(backup_encryption.is_encrypted_file(str(enc_backup)))

        # Attempt decryption with wrong password
        with self.assertRaises(ValueError):
            backup_encryption.decrypt_file(str(enc_backup), str(dec_backup), "wrong_password")

        # Decrypt with correct password
        backup_encryption.decrypt_file(str(enc_backup), str(dec_backup), password)
        self.assertTrue(dec_backup.exists())
        self.assertFalse(backup_encryption.is_encrypted_file(str(dec_backup)))

        # Verify database restores from decrypted file
        db2_path = Path(self.temp_dir.name) / "restored_enc.db"
        db2 = NoteDatabase(str(db2_path))
        try:
            db2.restore_from_file(str(dec_backup))
            restored_n1 = db2.get_note(note1.id)
            self.assertIsNotNone(restored_n1)
            self.assertEqual(restored_n1.title, "Encrypted Note")
        finally:
            db2.close()

    def test_auto_backup_config(self):
        self.assertEqual(self.config.get_auto_backup_folder(), "")
        self.assertFalse(self.config.get_auto_backup_folder_enabled())
        self.assertFalse(self.config.get_auto_backup_encrypted())
        self.assertEqual(self.config.get_auto_backup_password(), "")

        self.config.set_auto_backup_folder("/home/user/Backups")
        self.config.set_auto_backup_folder_enabled(True)
        self.config.set_auto_backup_encrypted(True)
        self.config.set_auto_backup_password("auto_pass_456")
        self.config.set_last_local_backup("2026-10-03 21:25")

        self.assertEqual(self.config.get_auto_backup_folder(), "/home/user/Backups")
        self.assertTrue(self.config.get_auto_backup_folder_enabled())
        self.assertTrue(self.config.get_auto_backup_encrypted())
        self.assertEqual(self.config.get_auto_backup_password(), "auto_pass_456")
        self.assertEqual(self.config.get_last_local_backup(), "2026-10-03 21:25")

    def test_restore_notifies_listener(self):
        backup_file = Path(self.temp_dir.name) / "restore_test.db"
        self.db.backup_to_file(str(backup_file))

        events = []
        def listener(event_type, data, sender):
            events.append((event_type, data))

        self.db.add_change_listener(listener)
        try:
            self.db.restore_from_file(str(backup_file))
            while GLib.MainContext.default().iteration(False):
                pass
            event_types = [e[0] for e in events]
            self.assertIn("database-restored", event_types)
        finally:
            self.db.remove_change_listener(listener)


if __name__ == "__main__":
    unittest.main()
