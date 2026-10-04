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


    def test_backup_exclude_private_notes_and_password(self):
        # 1. Setup normal note and private note, both with attachments
        normal_note = self.db.create_note(title="Public Work Note", initial_text="General notes", category="Work")
        att_public = self.db.save_attachment(normal_note.id, "report.pdf", "application/pdf", b"PUBLIC_PDF_BLOB")

        private_note = self.db.create_note(title="Secret Finances", initial_text="Financial details", category="Finance", is_locked=True)
        att_private = self.db.save_attachment(private_note.id, "secrets.png", "image/png", b"CONFIDENTIAL_PNG_BLOB")

        self.db.set_private_password("SuperSecretMaster123!")
        self.assertTrue(self.db.has_private_password())

        # 2. Perform backup with exclude_private=True
        backup_file = Path(self.temp_dir.name) / "backup_excluded.db"
        self.db.backup_to_file(str(backup_file), exclude_private=True)
        self.assertTrue(backup_file.exists())

        # 3. Restore to a new clean database
        db_restored_path = Path(self.temp_dir.name) / "restored_excluded.db"
        db_restored = NoteDatabase(str(db_restored_path))
        try:
            db_restored.restore_from_file(str(backup_file))

            # Normal note and its attachment must exist
            n_pub = db_restored.get_note(normal_note.id)
            self.assertIsNotNone(n_pub)
            self.assertEqual(n_pub.title, "Public Work Note")
            self.assertEqual(db_restored.get_attachment(att_public)["data"], b"PUBLIC_PDF_BLOB")

            # Private note must NOT exist in the restored database
            self.assertIsNone(db_restored.get_note(private_note.id))
            self.assertIsNone(db_restored.get_attachment(att_private))

            # Master password must NOT exist in the restored database
            self.assertFalse(db_restored.has_private_password())
            self.assertFalse(db_restored.verify_private_password("SuperSecretMaster123!"))

            # No private notes listed or counted
            self.assertEqual(len(db_restored.get_notes(filter_type="private")), 0)
            self.assertEqual(db_restored.get_counts().get("private", 0), 0)
        finally:
            db_restored.close()

    def test_backup_include_private_notes_default(self):
        private_note = self.db.create_note(title="Secret Note", initial_text="Secret text", is_locked=True)
        att_id = self.db.save_attachment(private_note.id, "key.pem", "text/plain", b"PRIVATE_KEY_DATA")
        self.db.set_private_password("MyPassword456!")

        backup_file = Path(self.temp_dir.name) / "backup_included.db"
        # Default exclude_private=False
        self.db.backup_to_file(str(backup_file))

        db_restored_path = Path(self.temp_dir.name) / "restored_included.db"
        db_restored = NoteDatabase(str(db_restored_path))
        try:
            db_restored.restore_from_file(str(backup_file))

            self.assertIsNotNone(db_restored.get_note(private_note.id))
            self.assertEqual(db_restored.get_attachment(att_id)["data"], b"PRIVATE_KEY_DATA")
            self.assertTrue(db_restored.has_private_password())
            self.assertTrue(db_restored.verify_private_password("MyPassword456!"))
            self.assertEqual(len(db_restored.get_notes(filter_type="private")), 1)
        finally:
            db_restored.close()


if __name__ == "__main__":
    unittest.main()
