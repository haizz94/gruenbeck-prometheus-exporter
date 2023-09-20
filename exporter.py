import time
from datetime import datetime
import os
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client import start_http_server, PROCESS_COLLECTOR, PLATFORM_COLLECTOR, GC_COLLECTOR
from api import GruenbeckApi



class GruenbeckCollector(object):
    def __init__(self, user: str, password: str):
        self.__gbApi: GruenbeckApi = GruenbeckApi(user, password)
        self.__gbApi.init()
    def collect(self):          
        self.__gbApi.refreshValues()

        next_regeneration = GaugeMetricFamily("next_regeneration", "Timestamp for next regeneration")
        try:
            datetime_object = datetime.strptime(self.__gbApi.nextRegeneration, '%Y-%m-%dT%H:%M:%S')
            next_regeneration.add_metric([], datetime_object.timestamp() * 1000)
        except:
            print("Could not parse time for next regeneration")

        yield next_regeneration

        raw_water = GaugeMetricFamily("raw_water", "Raw water hardness")
        value = float(self.__gbApi.rawWaterHardness)
        raw_water.add_metric([], value)
        yield raw_water

        # Output water hardness
        # softWater
        soft_water = GaugeMetricFamily("soft_water", "Soft water hardness")
        value = float(self.__gbApi.softWaterHardness)
        soft_water.add_metric([], value)
        yield soft_water

        # mode
        # 1=Eco, 2=Comfort, 3=Power
        mode = GaugeMetricFamily("mode", "Current mode (1=Eco, 2=Comfort, 3=Power)")
        value = int(self.__gbApi.mode)
        mode.add_metric([], value)
        yield mode

        # Has error
        # hasError
        hasError = GaugeMetricFamily("has_error", "Water softener has error")
        value = 1 if self.__gbApi.hasError else 0
        hasError.add_metric([], value)
        yield hasError

        ### Stream
        # mcountwater1
        water_usage = GaugeMetricFamily("water_usage", "Soft water usage of all time in liters", labels=['tank'])
        for idx, x in enumerate(self.__gbApi.waterUsages):
            water_usage.add_metric([str(idx+1)], x)
        yield water_usage

        # mcountreg
        reg_counter = GaugeMetricFamily("reg_counter", "Regeneration counter")
        reg_counter.add_metric([], self.__gbApi.regenerationCounter)
        yield reg_counter

        # mflow1
        water_flow = GaugeMetricFamily("water_flow", "Actual water flow in m3/h", labels=['tank'])
        for idx, x in enumerate(self.__gbApi.waterFlows):
            water_flow.add_metric([str(idx+1)], x)
        yield water_flow

        # mrescapa1
        remaining_cap_m3 = GaugeMetricFamily("remaining_cap_m3", "Remaining capacity in m3", labels=['tank'])
        for idx, x in enumerate(self.__gbApi.remainingCapacitiesM3):
            remaining_cap_m3.add_metric([str(idx+1)], x)
        yield remaining_cap_m3

        # residcap1
        remaining_cap_percent = GaugeMetricFamily("remaining_cap_percent", "Remaining capacity in %", labels=['tank'])
        for idx, x in enumerate(self.__gbApi.remainingCapacitiesPercent):
            remaining_cap_percent.add_metric([str(idx+1)], x)
        yield remaining_cap_percent

        # msaltrange
        salt_range = GaugeMetricFamily("salt_range", "Salt range in days")
        salt_range.add_metric([], self.__gbApi.saltRange)
        yield salt_range

        # msaltusage
        salt_usage = GaugeMetricFamily("salt_usage", "Salt usage in kg")
        salt_usage.add_metric([], self.__gbApi.saltUsage)
        yield salt_usage

        # Maintenance left days
        # mmaint
        maint_left = GaugeMetricFamily("maint_left", "Left days until next maintenance")
        maint_left.add_metric([], self.__gbApi.maintenanceLeftDays)
        yield maint_left
    
if __name__ == "__main__":
    port = os.getenv("EXPORTER_PORT")
    if port is None:
        port = 9042

    user = os.getenv("GB_USER_NAME")
    if user is None:
        print("No username found, please set environment variable like this:")
        print("GB_USER_NAME=admin")
        exit(255)

    password = os.getenv("GB_PASSWORD")
    if password is None:
        print("No password found, please set environment variable like this:")
        print("GB_PASSWORD=1234")
        exit(255)

    print("EXPORTER_PORT:", port)
    print("GB_USER_NAME:", user)
    print("GB_PASSWORD:", password)  
    
    start_http_server(port)
    REGISTRY.unregister(PROCESS_COLLECTOR)
    REGISTRY.unregister(PLATFORM_COLLECTOR)
    REGISTRY.unregister(GC_COLLECTOR)
    REGISTRY.register(GruenbeckCollector(user, password))
    while (True):
        time.sleep(1)