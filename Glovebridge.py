import asyncio
import struct
import os
from bleak import BleakScanner, BleakClient

# Define BLE devices and their corresponding named pipes
TARGET_DEVICES = {
    "lucidgloves-right": { "pipe_rx": "\\.\pipe\vrapplication\input\glove\v1\right", "pipe_tx": "\\.\pipe\vrapplication\ffb\curl\right", "address": None },
    "lucidgloves-left": { "pipe_rx": "\\.\pipe\vrapplication\input\glove\v1\left", "pipe_tx": "\\.\pipe\vrapplication\ffb\curl\left", "address": None }
}
CHARACTERISTIC_UUID_RX = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # Replace with actual RX characteristic UUID
CHARACTERISTIC_UUID_TX = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # Replace with actual TX characteristic UUID

async def find_ble_devices():
    """Continuously scan for missing BLE devices."""
    while True:
        print("Scanning for missing BLE devices...")
        devices = await BleakScanner.discover()
        
        for device in devices:
            for name in TARGET_DEVICES:
                if device.name == name and TARGET_DEVICES[name]["address"] is None:
                    TARGET_DEVICES[name]["address"] = device.address
                    print(f"Found {name}: {device.address}")

        await asyncio.sleep(5)  # Scan interval

async def handle_ble_device(device_name):
    """Handles connection, data reading, and writing for a BLE device."""
    paths = TARGET_DEVICES[device_name]
    
    # Ensure named pipes exist
    for path in (paths["pipe_rx"], paths["pipe_tx"]):
        if not os.path.exists(path):
            print("No target pipes found. Exiting.")
            break

    while True:
        if paths["address"] is None:
            print(f"Waiting for {device_name} to be discovered...")
            await asyncio.sleep(5)
            continue
        
        try:
            async with BleakClient(paths["address"]) as client:
                print(f"Connected to {device_name}")

                async def ble_reader():
                    """Reads from BLE and writes to the named pipe."""
                    while True:
                        try:
                            data = await client.read_gatt_char(CHARACTERISTIC_UUID_RX)
                            unpacked_data = struct.unpack("<ffI", data)
                            
                            with open(paths["pipe_rx"], "w") as fifo:
                                fifo.write(f"{unpacked_data}\n")

                            print(f"Received from {device_name}: {unpacked_data}")
                            await asyncio.sleep(1)

                        except BleakError:
                            print(f"{device_name} disconnected during read.")
                            break

                async def pipe_writer():
                    """Reads from named pipe and writes to BLE."""
                    while True:
                        try:
                            with open(paths["pipe_tx"], "r") as fifo:
                                line = fifo.readline().strip()
                                if line:
                                    values = tuple(map(float, line.split(",")))
                                    packed_data = struct.pack("<ffI", *values)
                                    
                                    await client.write_gatt_char(CHARACTERISTIC_UUID_TX, packed_data, response=True)
                                    print(f"Sent to {device_name}: {values}")

                        except BleakError:
                            print(f"{device_name} disconnected during write.")
                            break
                        await asyncio.sleep(1)

                await asyncio.gather(ble_reader(), pipe_writer())

        except Exception as e:
            print(f"Error with {device_name}: {e}. Reconnecting...")
            TARGET_DEVICES[device_name]["address"] = None  # Reset address for rediscovery
            await asyncio.sleep(5)

async def main():
    # Start device handlers
    tasks = [handle_ble_device(name) for name in TARGET_DEVICES]

    # Start background scanning for new/missing devices
    tasks.append(find_ble_devices())

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())