def mp_decode(buf, pos=0):
    b = buf[pos]
    if b <= 0x7f: return b, pos+1
    if b >= 0xe0: return b-256, pos+1
    if b == 0xc0: return None, pos+1
    if b == 0xc2: return False, pos+1
    if b == 0xc3: return True, pos+1
    if b == 0xcc: return buf[pos+1], pos+2
    if b == 0xcd: return struct.unpack('>H', buf[pos+1:pos+3])[0], pos+3
    if b == 0xce: return struct.unpack('>I', buf[pos+1:pos+5])[0], pos+5
    if b == 0xcf: return struct.unpack('>Q', buf[pos+1:pos+9])[0], pos+9
    if b == 0xd0: return struct.unpack('>b', buf[pos+1:pos+2])[0], pos+2
    if b == 0xd1: return struct.unpack('>h', buf[pos+1:pos+3])[0], pos+3
    if b == 0xd2: return struct.unpack('>i', buf[pos+1:pos+5])[0], pos+5
    if b == 0xd3: return struct.unpack('>q', buf[pos+1:pos+9])[0], pos+9
    if b == 0xca: return struct.unpack('>f', buf[pos+1:pos+5])[0], pos+5
    if b == 0xcb: return struct.unpack('>d', buf[pos+1:pos+9])[0], pos+9
    if 0xa0 <= b <= 0xbf:
        n = b & 0x1f
        return buf[pos+1:pos+1+n].decode('utf-8'), pos+1+n
    if b == 0xd9:
        n = buf[pos+1]
        return buf[pos+2:pos+2+n].decode('utf-8'), pos+2+n
    if b == 0xda:
        n = struct.unpack('>H', buf[pos+1:pos+3])[0]
        return buf[pos+3:pos+3+n].decode('utf-8'), pos+3+n
    if b == 0xdb:
        n = struct.unpack('>I', buf[pos+1:pos+5])[0]
        return buf[pos+5:pos+5+n].decode('utf-8'), pos+5+n
    if b == 0xc4:
        n = buf[pos+1]
        return buf[pos+2:pos+2+n], pos+2+n
    if b == 0xc5:
        n = struct.unpack('>H', buf[pos+1:pos+3])[0]
        return buf[pos+3:pos+3+n], pos+3+n
    if b == 0xc6:
        n = struct.unpack('>I', buf[pos+1:pos+5])[0]
        return buf[pos+5:pos+5+n], pos+5+n
    if 0x90 <= b <= 0x9f:
        n = b & 0x0f
        arr = []
        pos += 1
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if b == 0xdc:
        n = struct.unpack('>H', buf[pos+1:pos+3])[0]
        pos += 3
        arr = []
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if b == 0xdd:
        n = struct.unpack('>I', buf[pos+1:pos+5])[0]
        pos += 5
        arr = []
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if 0x80 <= b <= 0x8f:
        n = b & 0x0f
        d = {}
        pos += 1
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    if b == 0xde:
        n = struct.unpack('>H', buf[pos+1:pos+3])[0]
        pos += 3
        d = {}
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    if b == 0xdf:
        n = struct.unpack('>I', buf[pos+1:pos+5])[0]
        pos += 5
        d = {}
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    raise ValueError(f"Unsupported msgpack byte 0x{b:02x} at {pos}")
