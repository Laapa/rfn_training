"""Пробой вручную на EPICS-фейке:  python fake_server/spike_epics.py RF2
(то же, что команда caput RF2:CAV:Spike 1 из утилит EPICS)"""
import os
import sys

os.environ.setdefault("EPICS_CA_ADDR_LIST", "127.0.0.1")      # фейк слушает только этот компьютер
os.environ.setdefault("EPICS_CA_AUTO_ADDR_LIST", "NO")

import epics                                                   # noqa: E402

prefix = sys.argv[1] if len(sys.argv) > 1 else "RF2"
ok = epics.caput(f"{prefix}:CAV:Spike", 1, wait=True, timeout=2)
print(f"Пробой на {prefix}" if ok else f"Нет ответа от {prefix}:CAV:Spike - фейк запущен?")
