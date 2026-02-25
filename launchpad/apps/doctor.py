from __future__ import annotations

import shutil


def doctor_report() -> dict[str, bool]:
    tools = ["python", "git", "gh", "node", "npm", "pnpm"]
    return {t: shutil.which(t) is not None for t in tools}
