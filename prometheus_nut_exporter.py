import time
import os

from nut2 import PyNUTClient
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

METRICS = {
    "device.uptime": {"unit": "'seconds'", "help": "Device uptime"},
    "ups.temperature": {"unit": "celsius", "help": "UPS temperature"},
    "ups.load": {"unit": "percent", "help": "Load on UPS"},
    "ups.load.high": {
        "unit": "percent",
        "help": "Load when UPS switches to overload condition",
    },
    "ups.efficiency": {
        "unit": "percent",
        "help": "Efficiency of the UPS (ratio of the output current on the input current)",
    },
    "ups.power": {"unit": "voltamperes", "help": "Current value of apparent power"},
    "ups.power.nominal": {
        "unit": "voltamperes",
        "help": "Nominal value of apparent power",
    },
    "ups.realpower": {"unit": "watts", "help": "Current value of real power"},
    "ups.realpower.nominal": {"unit": "watts", "help": "Nominal value of real power"},
    "input.voltage": {"unit": "volts", "help": "Input voltage"},
    "input.voltage.maximum": {"unit": "volts", "help": "Maximum incoming voltage seen"},
    "input.voltage.minimum": {"unit": "volts", "help": "Minimum incoming voltage seen"},
    "input.voltage.low.warning": {"unit": "volts", "help": "Low warning threshold"},
    "input.voltage.low.critical": {"unit": "volts", "help": "Low critical threshold"},
    "input.voltage.high.warning": {"unit": "volts", "help": "High warning threshold"},
    "input.voltage.high.critical": {"unit": "volts", "help": "High critical threshold"},
    "input.voltage.nominal": {"unit": "volts", "help": "Nominal input voltage"},
    "input.transfer.delay": {
        "unit": "seconds",
        "help": "Delay before transfer to mains",
    },
    "input.transfer.low": {"unit": "volts", "help": "Low voltage transfer point"},
    "input.transfer.high": {"unit": "volts", "help": "High voltage transfer point"},
    "input.transfer.low.min": {
        "unit": "volts",
        "help": "smallest settable low voltage transfer point",
    },
    "input.transfer.low.max": {
        "unit": "volts",
        "help": "greatest settable low voltage transfer point",
    },
    "input.transfer.high.min": {
        "unit": "volts",
        "help": "smallest settable high voltage transfer point",
    },
    "input.transfer.high.max": {
        "unit": "volts",
        "help": "greatest settable high voltage transfer point",
    },
    "input.current": {"unit": "amperes", "help": "Input current"},
    "input.current.nominal": {"unit": "amperes", "help": "Nominal input current"},
    "input.current.low.warning": {"unit": "amperes", "help": "Low warning threshold"},
    "input.current.low.critical": {"unit": "amperes", "help": "Low critical threshold"},
    "input.current.high.warning": {"unit": "amperes", "help": "High warning threshold"},
    "input.current.high.critical": {
        "unit": "amperes",
        "help": "High critical threshold",
    },
    "input.frequency": {"unit": "hertz", "help": "Input line frequency"},
    "input.frequency.nominal": {
        "unit": "hertz",
        "help": "Nominal input line frequency",
    },
    "input.frequency.low": {"unit": "hertz", "help": "Input line frequency low"},
    "input.frequency.high": {"unit": "hertz", "help": "Input line frequency high"},
    "input.transfer.boost.low": {
        "unit": "hertz",
        "help": "Low voltage boosting transfer point",
    },
    "input.transfer.boost.high": {
        "unit": "hertz",
        "help": "High voltage boosting transfer point",
    },
    "input.transfer.trim.low": {
        "unit": "ertz",
        "help": "Low voltage trimming transfer point",
    },
    "input.transfer.trim.high": {
        "unit": "hertz",
        "help": "High voltage trimming transfer point",
    },
    "input.load": {"unit": "percent", "help": "Load on (ePDU) input"},
    "input.realpower": {
        "unit": "watts",
        "help": "Current sum value of all (ePDU) phases real power",
    },
    "input.power": {
        "unit": "voltamperes",
        "help": "Current sum value of all (ePDU) phases apparent power",
    },
    "output.voltage": {"unit": "volts", "help": "Output voltage"},
    "output.voltage.nominal": {"unit": "volts", "help": "Nominal output voltage"},
    "output.frequency": {"unit": "hertz", "help": "Output frequency"},
    "output.frequency.nominal": {"unit": "hertz", "help": "Nominal output frequency"},
    "output.current": {"unit": "amperes", "help": "Output current"},
    "output.current.nominal": {"unit": "amperes", "help": "Nominal output current"},
    "battery.charge": {"unit": "percent", "help": "Battery charge"},
    "battery.charge.low": {
        "unit": "percent",
        "help": "Remaining battery level when UPS switches to LB",
    },
    "battery.charge.restart": {
        "unit": "percent",
        "help": "Minimum battery level for UPS restart after power-off",
    },
    "battery.charge.warning": {
        "unit": "percent",
        "help": 'Battery level when UPS switches to "Warning" state',
    },
    "battery.voltage": {"unit": "volts", "help": "Battery voltage"},
    "battery.voltage.nominal": {"unit": "volts", "help": "Nominal battery voltage"},
    "battery.voltage.low": {
        "unit": "volts",
        "help": "Minimum battery voltage, that triggers FSD status",
    },
    "battery.voltage.high": {
        "unit": "volts",
        "help": "Maximum battery voltage (i.e. battery.charge = 100)",
    },
    "battery.capacity": {"unit": "amperehours", "help": "Battery capacity"},
    "battery.current": {"unit": "amperes", "help": "Battery current"},
    "battery.current.total": {"unit": "amperes", "help": "Total battery current"},
    "battery.temperature": {"unit": "celsius", "help": "Battery temperature"},
    "battery.runtime": {"unit": "seconds", "help": "Battery runtime"},
    "battery.runtime.low": {
        "unit": "seconds",
        "help": "Remaining battery runtime when UPS switches to LB",
    },
    "battery.runtime.restart": {
        "unit": "seconds",
        "help": "Minimum battery runtime for UPS restart after power-off",
    },
    "battery.packs": {"unit": None, "help": "Number of battery packs"},
    "battery.packs.bad": {"unit": None, "help": "Number of bad battery packs",},
}


class NUTCollector(object):
    def __init__(self, host, ups_name):
        self._host = host
        self._ups_name = ups_name

    def collect(self):
        client = PyNUTClient(self._host)
        client_vars = client.list_vars(self._ups_name)

        info = GaugeMetricFamily(
            "nut_device_info",
            "information about the UPS",
            labels=["manufacturer", "model", "serial"],
        )
        info.add_metric(
            # APC UPSes seem to add whitespace at the end of the serial number
            [
                client_vars["device.mfr"],
                client_vars["device.model"],
                client_vars["device.serial"].strip(),
            ],
            1,
        )

        ups_status = GaugeMetricFamily(
            "nut_ups_status", "UPS status", labels=["status"]
        )
        ups_status.add_metric([client_vars["ups.status"]], 1.0)

        if "ups.beeper.status" in client_vars:
            ups_beeper_status = GaugeMetricFamily(
                "nut_ups_beeper_status", "UPS beeper status", labels=["status"]
            )
            ups_beeper_status.add_metric([client_vars["ups.beeper.status"]], 1.0)
            yield ups_beeper_status

        if "battery.charger.status" in client_vars:
            battery_charger_status = GaugeMetricFamily(
                "nut_battery_charger_status",
                "Status of the battery charger",
                labels=["status"],
            )
            battery_charger_status.add_metric(
                [client_vars["battery.charger.status"]], 1.0
            )
            yield battery_charger_status

        for var in client_vars:
            if var in METRICS:
                formatted_name = var.replace(".", "_")
                if METRICS[var]["unit"]:
                    formatted_name = "_".join(
                        ("nut", formatted_name, METRICS[var]["unit"])
                    )
                else:
                    formatted_name = "_".join(("nut", formatted_name))
                yield GaugeMetricFamily(
                    formatted_name, METRICS[var]["help"], value=client_vars[var]
                )
        yield info
        yield ups_status


if __name__ == "__main__":
    REQUIRED_VARS = ["HOST", "UPS"]

    for var in REQUIRED_VARS:
        if var not in os.environ:
            raise EnvironmentError("Failed because {} is not set.".format(var))

    host = os.environ.get("HOST")
    nut_port = os.environ.get("NUT_PORT") or 3493
    ups = os.environ.get("UPS")
    exporter_port = os.environ.get("EXPORTER_PORT") or 9293

    start_http_server(int(exporter_port))
    REGISTRY.register(NUTCollector(host=host, ups_name=ups))

    while True:
        time.sleep(1)
