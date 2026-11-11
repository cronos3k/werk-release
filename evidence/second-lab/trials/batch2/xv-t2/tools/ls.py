import sys, zipfile, struct
p = sys.argv[1]
data = open(p, "rb").read()
z = zipfile.ZipFile(p)
print("comment:", z.comment[:200])
for i in z.infolist():
    # local header check
    lh = data[i.header_offset:i.header_offset+30]
    sig, ver, flag, meth, t, d, crc, cs, us, nl, el = struct.unpack("<IHHHHHIIIHH", lh)
    lname = data[i.header_offset+30:i.header_offset+30+nl].decode("utf-8", "replace")
    dstart = i.header_offset + 30 + nl + el
    note = ""
    if lname != i.filename: note += f" LOCALNAME={lname!r}"
    if meth != i.compress_type: note += f" LOCALMETH={meth}"
    print(f"{i.header_offset:>9} {dstart:>9} m{i.compress_type} crc={i.CRC:08x} {i.compress_size:>9} {i.file_size:>9} el={el} {i.filename}{note}")
end = max(i.header_offset for i in z.infolist())
print("total entries", len(z.infolist()))
eocd = data.rfind(b"PK\x05\x06")
print("EOCD at", eocd, "file len", len(data), "trailing after EOCD+22:", len(data) - eocd - 22)
# scan for local headers not in central dir
offs = {i.header_offset for i in z.infolist()}
pos = 0; extra = []
while True:
    pos = data.find(b"PK\x03\x04", pos)
    if pos < 0: break
    if pos not in offs: extra.append(pos)
    pos += 1
print("unlisted PK0304 signatures at:", extra[:50])
