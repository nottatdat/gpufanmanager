#!/home/dat/frameworks/miniconda3/bin/python
import os
import time
import json
import subprocess

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


class GPU:
    def __init__(self, gpuid, temp_min, temp_max, fan_min, fan_max, fanids):
        self.gpuid = gpuid
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.fan_min = fan_min
        self.fan_max = fan_max
        self.fanids = fanids

        self.fan_current = None

    def __str__(self):
        return str(self.gpuid)

    @staticmethod
    def parse_gpu_config(json_object):
        gpuid = json_object["gpuid"]
        temp_max = int(json_object["tempmax"])
        temp_min = int(json_object["tempmin"])
        fan_min = int(json_object["fanmin"])
        fan_max = int(json_object["fanmax"])
        fanids = json_object["fanids"]

        return gpuid, temp_min, temp_max, fan_min, fan_max, fanids

    @staticmethod
    def calculate_fan_speed(t, t_min, t_max, f_min, f_max):
        if t <= t_min:
            return f_min

        if t >= t_max:
            return f_max

        return int(f_min + (f_max - f_min) * ((t - t_min) / (t_max - t_min)) ** 2)

    @property
    def temperature(self):
        output = subprocess.run(
            "DISPLAY=:1 nvidia-settings -q GPUCoreTemp | grep %s" % self.gpuid,
            shell = True,
            capture_output=True
        )

        if not output.stdout:
            return None

        temperature = int(output.stdout
                                .decode()
                                .replace("\n", "")
                                .replace(".", "")
                                .split()[-1])

        return temperature

    def set_fan(self, f):
        if f == self.fan_current:
            return

        set_fan_command = """
        DISPLAY=:1 nvidia-settings -a "[{}]/GPUFanControlState=1" -a "[fan:{}]/GPUTargetFanSpeed={}"
        """

        for fanid in self.fanids:
            subprocess.call(
                set_fan_command.format(self.gpuid, fanid, f),
                shell=True,
                stdout=open(os.devnull, 'w')
            )

        self.fan_current = f

    def adjust_fan(self):
        t = self.temperature

        if not t:
            return

        f = GPU.calculate_fan_speed(t, self.temp_min, self.temp_max, self.fan_min, self.fan_max)

        self.set_fan(f)


class GPUFanManager:
    def __init__(self, config):
        config = json.load(config)
        self.interval = config["interval"]

        self.devices = []
        for device_config in config["devices"]:
            args = GPU.parse_gpu_config(device_config)
            device = GPU(*args)
            self.devices.append(device)

    def run(self):
        start = time.time()

        with open(os.getenv("GPU_MANAGER_LOG"), "a") as log:
            log.write("{}:".format(start))

        while True:
            for device in self.devices:
                with open(os.getenv("GPU_MANAGER_LOG"), "a") as log:
                    log.write("{}|".format(device.temperature))
                device.adjust_fan()

            time.sleep(self.interval - ((time.time() - start) % self.interval))


def get_lock_fname():
    return os.path.abspath("{}.lock".format(__file__))


def main():
    if os.path.isfile(get_lock_fname()):
        print("GPUFanManager already running!")
        return

    open(get_lock_fname(), "w").close()

    manager = GPUFanManager(open(os.getenv("GPU_MANAGER_CONFIG"), "r"))
    manager.run()


def cleanup():
    os.remove(get_lock_fname())


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
