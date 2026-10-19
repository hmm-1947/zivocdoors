import struct

JPEG_SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def image_info(data):
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24 and data[12:16] == b'IHDR':
        width, height = struct.unpack('>II', data[16:24])
        return 'image/png', width, height
    if data[:2] == b'\xff\xd8':
        index = 2
        size = len(data)
        while index + 4 <= size:
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker == 0xFF:
                index += 1
                continue
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            length = struct.unpack('>H', data[index + 2:index + 4])[0]
            if marker in JPEG_SOF:
                if index + 9 > size:
                    return None
                height, width = struct.unpack('>HH', data[index + 5:index + 9])
                return 'image/jpeg', width, height
            index += 2 + length
        return None
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP' and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b'VP8 ':
            width = struct.unpack('<H', data[26:28])[0] & 0x3FFF
            height = struct.unpack('<H', data[28:30])[0] & 0x3FFF
            return 'image/webp', width, height
        if chunk == b'VP8L':
            bits = int.from_bytes(data[21:25], 'little')
            return 'image/webp', (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if chunk == b'VP8X':
            width = int.from_bytes(data[24:27], 'little') + 1
            height = int.from_bytes(data[27:30], 'little') + 1
            return 'image/webp', width, height
    return None


def read_upload(file, limit):
    if file is None or not getattr(file, 'filename', ''):
        return None
    data = file.stream.read(limit + 1)
    return data
