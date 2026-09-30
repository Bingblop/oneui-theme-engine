import subprocess
import shutil
import os
from typing import Tuple, Optional

class ShizukuBridge:
    """Handles execution of privileged shell commands via Shizuku (rish), su, or direct shell."""

    def __init__(self):
        self.mode = self._detect_mode()

    def _detect_mode(self) -> str:
        # Check if rish is available in PATH or common locations
        if shutil.which("rish"):
            return "rish"
        rish_home = os.path.expanduser("~/rish")
        if os.path.exists(rish_home) and os.access(rish_home, os.X_OK):
            return rish_home
        if shutil.which("su"):
            return "su"
        return "direct"

    def run(self, cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
        """Runs a command under privileged shell."""
        if self.mode == "rish" or self.mode.endswith("/rish"):
            full_cmd = [self.mode, "-c", cmd]
        elif self.mode == "su":
            full_cmd = ["su", "-c", cmd]
        else:
            full_cmd = ["sh", "-c", cmd]

        try:
            res = subprocess.run(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            # Filter out rish notice message if present
            stdout = res.stdout
            if "Waiting for Shizuku authorization..." in stdout:
                stdout = stdout.replace("Waiting for Shizuku authorization... check your notifications.\n", "")
            return res.returncode, stdout, res.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
