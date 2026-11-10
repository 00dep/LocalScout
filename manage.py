#!/usr/bin/env python
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    backend_dir = project_root / "backend"

    if not (backend_dir / "manage.py").exists():
        raise SystemExit("Could not find backend/manage.py")

    os.chdir(backend_dir)
    sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
