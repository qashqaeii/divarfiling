"""ابزارهای رسانه آکادمی — مدت واقعی MP4."""
from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path


def mp4_duration_seconds(path: Path) -> int | None:
    """مدت ویدیو به ثانیه — ffprobe در صورت وجود، وگرنه خواندن اتم mvhd."""
    path = Path(path)
    if not path.is_file():
        return None
    ffprobe = shutil.which('ffprobe')
    if ffprobe:
        try:
            out = subprocess.check_output(
                [
                    ffprobe,
                    '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    str(path),
                ],
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            return max(1, int(float(out.decode().strip())))
        except (subprocess.SubprocessError, ValueError, OSError):
            pass
    data = path.read_bytes()
    idx = data.find(b'mvhd')
    if idx < 4:
        return None
    i = idx + 4
    version = data[i]
    if version == 0:
        timescale = struct.unpack('>I', data[i + 12 : i + 16])[0]
        dur = struct.unpack('>I', data[i + 16 : i + 20])[0]
    else:
        timescale = struct.unpack('>I', data[i + 20 : i + 24])[0]
        dur = struct.unpack('>Q', data[i + 24 : i + 32])[0]
    if not timescale:
        return None
    return max(1, int(dur / timescale))
