import time
from typing import Optional
from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf

SERVICE_TYPE = "_codea-air-code._tcp.local."


def discover_devices(timeout: float = 5.0) -> list[dict]:
    """Scan the local network for Codea devices via mDNS."""
    devices = []
    zc = Zeroconf()

    class Listener:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if info and info.addresses:
                import socket
                host = socket.inet_ntoa(info.addresses[0])
                devices.append({
                    "name": info.server.rstrip(".") if info.server else name,
                    "host": host,
                    "port": info.port,
                })

        def remove_service(self, zc, type_, name):
            pass

        def update_service(self, zc, type_, name):
            pass

    browser = ServiceBrowser(zc, SERVICE_TYPE, Listener())
    time.sleep(timeout)
    zc.close()
    return devices
