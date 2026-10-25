"""Opt-in real Google test: isolated profile, synthetic Brain, no credential output.

Run using the candidate's embedded Python. The user completes system-browser
authorization. No existing Brain or machine-local pointer is opened or changed.
"""
import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("desktop_client_json", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("progress", type=Path)
    args = parser.parse_args()
    results = {"passed":False,"real_google":True,"synthetic_data_only":True}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    def progress(phase):
        args.progress.write_text(json.dumps({"phase":phase}), encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="pese-google-acceptance-") as temporary:
        temporary = Path(temporary)
        os.environ["LOCALAPPDATA"] = str(temporary / "profile")
        from engine.brain.lifecycle import initialize_brain
        from engine.brain.atomic import atomic_write_json
        from engine.sync.oauth import load_oauth_client_config
        from engine.sync.service import GoogleDriveSyncService
        from engine.sync.snapshot import canonical_state_digest
        from engine.desktop.offline import install_offline_boundary
        from engine.brain.resolver import get_default_local_appdata_dir
        # Validate the user-supplied client type before making a private temporary copy.
        load_oauth_client_config(args.desktop_client_json)
        profile = get_default_local_appdata_dir()
        profile.mkdir(parents=True)
        shutil.copyfile(args.desktop_client_json, profile / "google-oauth-config.json")
        root = temporary / "synthetic-brain"
        initialize_brain(root)
        atomic_write_json(root / "firestore_documents.json", {"g1-acceptance": {
            "id":"g1-acceptance","slug":"g1-acceptance","title":"Disposable Google Drive acceptance",
            "content":"This synthetic fixture contains no personal content.", "status":"published"}})
        install_offline_boundary()
        service = GoogleDriveSyncService(brain_path=root)
        before = canonical_state_digest(root)
        uploaded = None
        try:
            progress("opening_system_browser")
            service.start_oauth_flow(authorization_timeout=600)
            progress("awaiting_user_authorization")
            deadline = time.monotonic() + 630
            while time.monotonic() < deadline:
                status = service.get_status()
                if status.connected:
                    break
                if status.status.value == "error":
                    raise RuntimeError("OAuth authorization did not complete")
                time.sleep(.5)
            else:
                raise TimeoutError("User authorization was not completed in time")
            results["oauth_connected"] = True
            results["account_identity_present"] = bool(status.account_email)
            results["connect_preserves_brain"] = canonical_state_digest(root) == before
            progress("uploading_synthetic_snapshot")
            uploaded = service.sync_now()
            results["upload_preserves_brain"] = canonical_state_digest(root) == before
            records = service.list_remote_snapshots()
            selected = next(item for item in records if item["id"] == uploaded["drive_file_id"])
            assert not selected["local_changes"] and selected["compatible"]
            results["uploaded_snapshot_listed"] = True
            progress("verifying_download_and_new_directory_recovery")
            recovered = service.recover_to_new_brain(file_id=selected["id"], snapshot_id=selected["snapshot_id"],
                          brain_id=selected["brain_id"], archive_sha256=selected["archive_sha256"],
                          confirmed_local_digest=before, target=temporary / "recovered-brain")
            assert recovered.success
            results["download_verified"] = True
            results["new_brain_matches_original"] = canonical_state_digest(temporary / "recovered-brain") == before
            results["recovery_preserves_original"] = canonical_state_digest(root) == before
            results["passed"] = all(value for key,value in results.items() if key not in ("passed",))
        except Exception as error:
            results["error_type"] = type(error).__name__
            results["authorization_error"] = service.get_status().message
        finally:
            if uploaded:
                try:
                    results["synthetic_cloud_artifact_deleted"] = service._drive_client.delete_snapshot(uploaded["drive_file_id"])
                except Exception:
                    results["synthetic_cloud_artifact_deleted"] = False
            try:
                disconnected = service.disconnect()
                results["remote_revocation_confirmed"] = ("could not be confirmed" not in disconnected["message"]) if results.get("oauth_connected") else None
                results["disconnect_preserves_brain"] = canonical_state_digest(root) == before
                results["local_credentials_cleared"] = not service.is_connected()
            except Exception:
                results["local_credentials_cleared"] = False
            results["passed"] = results["passed"] and results.get("disconnect_preserves_brain",False) and results.get("local_credentials_cleared",False)
            if uploaded and not results.get("synthetic_cloud_artifact_deleted"):
                results["passed"] = False
            args.report.write_text(json.dumps(results,indent=2),encoding="utf-8")
            progress("complete" if results["passed"] else "incomplete")
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
