import sys
from pathlib import Path

# When run from source, the package lives under src/. (In a PyInstaller
# bundle sys.frozen is set and the package is already importable.)
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from aa_tool.ui.main_window import main

if __name__ == "__main__":
    main()
