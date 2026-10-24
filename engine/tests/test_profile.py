import pytest
from pathlib import Path
from engine.brain.profile import (
    load_profile,
    save_profile,
    import_avatar,
    remove_avatar,
    get_avatar_file,
    UserProfile
)
from engine.brain.lifecycle import initialize_brain


def test_profile_lifecycle(tmp_path: Path):
    brain_dir = tmp_path / "test_brain"
    initialize_brain(brain_dir, name="Profile Test Brain", seed_documents=False)

    # 1. Default profile
    p1 = load_profile(brain_dir)
    assert p1.display_name == "Local User"
    assert p1.about == ""
    assert p1.avatar is None
    assert p1.schema_version == 1

    # 2. Update profile
    p2 = save_profile("Yasir", "PESE Explorer & Builder", brain_dir)
    assert p2.display_name == "Yasir"
    assert p2.about == "PESE Explorer & Builder"
    assert p2.avatar is None

    # Reload from disk
    p2_loaded = load_profile(brain_dir)
    assert p2_loaded.display_name == "Yasir"
    assert p2_loaded.about == "PESE Explorer & Builder"

    # 3. Import avatar
    dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    p3 = import_avatar(dummy_png, "my_avatar.png", brain_dir)
    assert p3.avatar is not None
    assert p3.avatar.relative_path == "profile/avatar.png"
    assert p3.display_name == "Yasir"

    # Verify avatar file resolution
    avatar_file = get_avatar_file(brain_dir)
    assert avatar_file is not None
    assert avatar_file.exists()
    assert avatar_file.read_bytes() == dummy_png

    # 4. Replace avatar with webp
    dummy_webp = b"RIFF....WEBPVP8 ...."
    p4 = import_avatar(dummy_webp, "new.webp", brain_dir)
    assert p4.avatar.relative_path == "profile/avatar.webp"
    # Old png was deleted
    assert not (brain_dir / "profile" / "avatar.png").exists()
    assert (brain_dir / "profile" / "avatar.webp").exists()

    # 5. Remove avatar
    p5 = remove_avatar(brain_dir)
    assert p5.avatar is None
    assert not (brain_dir / "profile" / "avatar.webp").exists()
    assert get_avatar_file(brain_dir) is None
