"""Makes the ML service's code importable (the matchers are evaluated directly, without starting any server)."""
import sys
from pathlib import Path

ML_SERVICE = Path(__file__).resolve().parents[2] / "ml-service"
if str(ML_SERVICE) not in sys.path:
    sys.path.insert(0, str(ML_SERVICE))
