# file: app/utils.py
import subprocess
import platform

def get_mac_from_ip(ip_address):
    """Lấy địa chỉ MAC từ IP bằng cách đọc bảng ARP của hệ thống."""
    try:
        output = subprocess.check_output(["arp", "-a", ip_address], text=True, encoding='utf-8')
        for line in output.splitlines():
            if ip_address in line and (line.count('-') == 5 or line.count(':') == 5):
                mac = line.split()[1].upper().replace('-', ':')
                return mac
    except Exception as e:
        print(f"Không thể tìm thấy MAC cho IP {ip_address}: {e}")
        return None
    return None

def scan_network():
    """Quét mạng LAN và trả về một TẬP HỢP các địa chỉ MAC đang hoạt động."""
    current_os = platform.system()
    try:
        if current_os == "Windows":
            command = ["arp", "-a"]
            output = subprocess.check_output(command, text=True, encoding='utf-8')
            active_macs = set()
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 2 and len(parts[1]) == 17 and parts[1].count('-') == 5:
                    active_macs.add(parts[1].upper().replace('-', ':'))
            return active_macs
        else: # Dành cho Linux/macOS
            command = ["sudo", "arp-scan", "--localnet", "-q", "-g", "-F", "${mac}"]
            output = subprocess.check_output(command, text=True)
            active_macs = set(output.strip().upper().split('\n'))
            active_macs.discard('')
            return active_macs
    except Exception as e:
        print(f"Lỗi khi quét mạng: {e}")
        return set()