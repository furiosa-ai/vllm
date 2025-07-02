import subprocess
import time
from datetime import datetime, timezone
from multiprocessing import Queue
import pandas as pd
import numpy as np


def monitor_npu_power_usage(
    power_log_path: str, stop_queue: Queue = None, interval_ms: int = 500
):
    from furiosa_smi_py import init, list_devices

    init()
    try:
        with open(power_log_path, mode="a") as csvfile:
            csvfile.write(f"timestamp,device_name,utilize,power,temperature\n")
            devices = list_devices()
            while stop_queue.empty():
                device_log = []
                now = datetime.now(timezone.utc)
                s = now.isoformat()
                formatted_timestamp = datetime.fromisoformat(s)
                for device in devices:
                    device_name = f"rngd{device.device_info().index()}"
                    power = device.power_consumption()
                    util = (
                        sum(
                            [
                                pe.pe_usage_percentage()
                                for pe in device.core_utilization().pe_utilization()
                            ]
                        )
                        / 8
                    )
                    temp = device.device_temperature().soc_peak()
                    if util > 0:
                        csvfile.write(
                            f"{formatted_timestamp},{device_name},{float(util):.3f},{float(power)},{float(temp):.3f}\n"
                        )
                time.sleep(interval_ms / 1000.0)
            stop_queue.get()
    except KeyboardInterrupt:
        print("Monitoring stopped.")


def calculate_avg_power_usage(power_log_path: str):
    try:
        df = pd.read_csv(power_log_path)

        if "device_name" not in df.columns or "power" not in df.columns:
            print("Required columns are missing.")
            return

        device_group = df.groupby("device_name")["power"]
        device_names = device_group.groups.keys()

        devices_power = []
        for device_name in device_names:
            power_values = device_group.get_group(device_name).tolist()
            devices_power.append(power_values)

        avg_power = sum(np.mean(p) for p in devices_power)
        return avg_power

    except FileNotFoundError:
        print("Power log file not found.")
    except Exception as e:
        print(f"Error calculating average power usage: {e}")
        