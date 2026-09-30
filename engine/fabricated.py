from typing import Dict, Any, List, Optional
from .shizuku_bridge import ShizukuBridge

class FabricatedOverlayBuilder:
    """
    Constructs and manages dynamic Fabricated Runtime Resource Overlays (RRO)
    using Android's native `cmd overlay fabricate` engine.
    Supported on Android 12+ (One UI 4.0 - One UI 9.0).
    """

    TYPE_COLOR = "0x1c"
    TYPE_INT = "0x10"
    TYPE_BOOL = "0x12"
    TYPE_STRING = "0x03"

    def __init__(self, target_package: str, overlay_name: str, bridge: Optional[ShizukuBridge] = None):
        self.target = target_package
        self.name = overlay_name
        self.bridge = bridge or ShizukuBridge()
        self.entries: List[str] = []

    def add_color(self, resource_name: str, hex_color: str):
        """
        Adds a color override.
        hex_color: '#RRGGBB' or '#AARRGGBB' or integer hex '0xFFRRGGBB'
        """
        clean = hex_color.replace("#", "")
        if len(clean) == 6:
            clean = "FF" + clean
        val = f"0x{clean.lower()}"
        self.entries.append(f"color/{resource_name} {self.TYPE_COLOR} {val}")
        return self

    def add_bool(self, resource_name: str, val: bool):
        """Adds a boolean resource override."""
        bool_val = "1" if val else "0"
        self.entries.append(f"bool/{resource_name} {self.TYPE_BOOL} {bool_val}")
        return self

    def add_integer(self, resource_name: str, val: int):
        """Adds an integer resource override."""
        self.entries.append(f"integer/{resource_name} {self.TYPE_INT} {val}")
        return self

    def build_and_apply(self) -> bool:
        """Fabricates and enables the overlay."""
        if not self.entries:
            return False

        entries_str = " ".join(self.entries)
        cmd = f"cmd overlay fabricate --target {self.target} --name {self.name} {entries_str}"
        code, out, err = self.bridge.run(cmd)
        if code != 0:
            print(f"Fabrication failed: {err or out}")
            return False

        # Enable overlay
        full_overlay_id = f"com.android.shell:{self.name}"
        code_en, _, err_en = self.bridge.run(f"cmd overlay enable --user current {full_overlay_id}")
        return code_en == 0

    @classmethod
    def remove(cls, overlay_name: str, bridge: Optional[ShizukuBridge] = None) -> bool:
        """Removes a fabricated overlay."""
        b = bridge or ShizukuBridge()
        full_overlay_id = f"com.android.shell:{overlay_name}"
        b.run(f"cmd overlay disable --user current {full_overlay_id}")
        # Note: Android shell auto-cleans fabricated overlays on reboot or via package removal
        return True
