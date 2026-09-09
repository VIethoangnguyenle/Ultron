#!/usr/bin/env python3
"""Machine resource snapshot: system summary + top-N CPU/RAM + heuristic flags.

Measures per-process CPU% correctly by sampling twice, so the numbers are real
rather than instantaneous kernel values. Copy and tune the thresholds in the
HEURISTIC FLAGS section.
"""
import os
import time
import psutil

SAMPLE_INTERVAL = 1.5  # seconds between CPU samples
SELF_PID = os.getpid()

load1, load5, load15 = psutil.getloadavg()
cpu_cores = psutil.cpu_count(logical=True)
mem = psutil.virtual_memory()
swap = psutil.swap_memory()

# First sample: capture per-process cpu_times and metadata.
snap1 = {}
for p in psutil.process_iter(["pid", "name", "cmdline", "status",
                              "memory_info", "create_time", "num_threads"]):
    try:
        info = p.info
        info["cpu_times"] = p.cpu_times()
        snap1[p.pid] = info
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        continue


def _busy(ct):
    return ct.user + ct.system + ct.idle + ct.iowait + ct.irq + ct.softirq + ct.steal


tot1 = psutil.cpu_times()
time.sleep(SAMPLE_INTERVAL)
tot2 = psutil.cpu_times()
total_delta = _busy(tot2) - _busy(tot1)

rows = []
for pid, info1 in snap1.items():
    if pid == SELF_PID:
        continue
    try:
        p = psutil.Process(pid)
        ct = p.cpu_times()
        rss_mb = info1["memory_info"].rss / (1024 * 1024)
        mem_pct = (info1["memory_info"].rss / mem.total) * 100
        delta = (ct.user + ct.system) - (info1["cpu_times"].user + info1["cpu_times"].system)
        cpu_pct = (delta / total_delta) * 100 * cpu_cores if total_delta > 0 else 0.0
        rows.append({
            "pid": pid, "name": info1["name"], "status": info1["status"],
            "cpu_pct": cpu_pct, "mem_pct": mem_pct, "rss_mb": rss_mb,
            "age_h": (time.time() - info1["create_time"]) / 3600,
            "threads": info1["num_threads"],
            "cmdline": (" ".join(info1["cmdline"]) if info1["cmdline"] else info1["name"])[:200],
        })
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        continue

GB = 1024 ** 3
print("=== SYSTEM ===")
print(f"time: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"uptime_h: {(time.time() - psutil.boot_time())/3600:.1f}")
print(f"load: {load1:.2f} {load5:.2f} {load15:.2f}")
print(f"cpu_cores: {cpu_cores}")
print(f"mem: total={mem.total/GB:.1f}Gi used={mem.used/GB:.1f}Gi avail={mem.available/GB:.1f}Gi pct={mem.percent}%")
print(f"swap: total={swap.total/GB:.1f}Gi used={swap.used/GB:.1f}Gi pct={swap.percent}%")
print(f"process_count: {len(rows)}")
print(f"zombie_count: {sum(1 for r in rows if r['status'] == psutil.STATUS_ZOMBIE)}")

for label, key, top_n in (("TOP 12 BY CPU", "cpu_pct", 12), ("TOP 12 BY RAM", "rss_mb", 12)):
    print(f"\n=== {label} ===")
    print(f"{'PID':>7} {'CPU%':>6} {'MEM%':>6} {'RSS_MB':>9} {'AGE_H':>7} {'THR':>4} NAME")
    for r in sorted(rows, key=lambda r: -r[key])[:top_n]:
        print(f"{r['pid']:>7} {r['cpu_pct']:>6.1f} {r['mem_pct']:>6.1f} {r['rss_mb']:>9.0f} {r['age_h']:>7.1f} {r['threads']:>4} {r['name']}")
        print(f"        cmd: {r['cmdline']}")

# Heuristic flags — the agent, not the script, decides what is 'unnecessary'.
print("\n=== HEURISTIC FLAGS ===")
flags = []
for r in rows:
    if r["cpu_pct"] > 50:
        flags.append(f"HIGH_CPU pid={r['pid']} cpu={r['cpu_pct']:.0f}% name={r['name']} cmd={r['cmdline']}")
for r in sorted(rows, key=lambda r: -r["mem_pct"]):
    if r["mem_pct"] > 5:
        flags.append(f"HIGH_MEM pid={r['pid']} mem={r['mem_pct']:.0f}% rss={r['rss_mb']:.0f}MB name={r['name']}")
for r in rows:
    if r["age_h"] > 24 and (r["cpu_pct"] > 30 or r["mem_pct"] > 10):
        flags.append(f"LONG_RUN_HEAVY pid={r['pid']} age={r['age_h']:.0f}h cpu={r['cpu_pct']:.0f}% mem={r['mem_pct']:.0f}% name={r['name']}")
if flags:
    for f in flags[:30]:
        print(f"  {f}")
else:
    print("  (none — no process exceeds thresholds)")
