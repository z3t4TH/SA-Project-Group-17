"""Dependency-free QR version 5-L, byte mode, mask 0 (ISO QR matrix)."""
from html import escape


def matrix(text):
    raw = text.encode('utf-8')
    if len(raw) > 106:
        raise ValueError('QR URL must be at most 106 UTF-8 bytes')
    bits = [0, 1, 0, 0] + [(len(raw) >> i) & 1 for i in range(7, -1, -1)]
    for b in raw:
        bits += [(b >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, 864 - len(bits))
    bits += [0] * (-len(bits) % 8)
    data = [sum(bits[i+j] << (7-j) for j in range(8)) for i in range(0, len(bits), 8)]
    while len(data) < 108:
        data.append(0xEC if (len(data) - (len(bits)//8)) % 2 == 0 else 0x11)

    def mul(a, b):
        c = 0
        for i in range(7, -1, -1):
            c = (c << 1) ^ ((c >> 7) * 0x11D)
            c ^= ((b >> i) & 1) * a
        return c

    gen = [1]
    root = 1
    for _ in range(26):
        nxt = [0] * (len(gen)+1)
        for i, v in enumerate(gen):
            nxt[i] ^= v
            nxt[i+1] ^= mul(v, root)
        gen = nxt
        root = mul(root, 2)
    work = data + [0]*26
    for i in range(108):
        factor = work[i]
        for j, g in enumerate(gen):
            work[i+j] ^= mul(factor, g)
    stream = [((b >> i) & 1) for b in data+work[108:] for i in range(7, -1, -1)]
    n = 37
    m = [[None]*n for _ in range(n)]
    for cx, cy in [(3, 3), (n-4, 3), (3, n-4)]:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx+dx, cy+dy
                if 0 <= x < n and 0 <= y < n:
                    d = max(abs(dx), abs(dy))
                    m[y][x] = int(d != 2 and d != 4)
    for i in range(8, n-8):
        m[6][i] = m[i][6] = int(i % 2 == 0)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            m[30+dy][30+dx] = int(max(abs(dx), abs(dy)) != 1)
    # L / mask 0 format string, including BCH and XOR mask.
    fmt = 0x77C4
    for i in range(15):
        v = (fmt >> i) & 1
        if i < 6: m[i][8] = v
        elif i < 8: m[i+1][8] = v
        elif i == 8: m[8][7] = v
        else: m[8][14-i] = v
        if i < 8: m[8][n-1-i] = v
        else: m[n-15+i][8] = v
    m[8][8] = (fmt >> 7) & 1
    m[n-8][8] = 1
    idx = 0
    right = n-1
    up = True
    while right >= 1:
        if right == 6: right -= 1
        for y in (range(n-1, -1, -1) if up else range(n)):
            for x in (right, right-1):
                if m[y][x] is None:
                    m[y][x] = (stream[idx] if idx < len(stream) else 0) ^ int((x+y) % 2 == 0)
                    idx += 1
        up = not up
        right -= 2
    return m


def svg(text):
    m = matrix(text)
    cells = ''.join(f'M{x+4},{y+4}h1v1h-1z' for y,row in enumerate(m) for x,v in enumerate(row) if v)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45" role="img" aria-label="QR"><title>{escape(text)}</title><path fill="white" d="M0 0h45v45H0z"/><path fill="black" d="{cells}"/></svg>'
