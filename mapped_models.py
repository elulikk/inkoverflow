"""Models the backend does not list by name but that a documented source puts in the SAME
record as one it does list.

Nothing here is invented: a mapped model is a copy of its base model's entry, and
backend_cli runs the backend with the base model's name. A model is only mapped while
the backend lacks it; as soon as the backend defines it, its own entry wins.

Source: reinkpy's epson.toml (https://codeberg.org/atufi/reinkpy, the same data the
backend's parse_devices.py reads). One record there lists XP-230, XP-231, XP-235, XP-330 ...
XP-432, XP-433, XP-435 with read key 0x0585, the "Polyxena" write key and the waste cells
0x18/0x19/0x1E, 0x1A/0x1B/0x22 and 0x1C/0x1D/0x2E/0x2F/0x31. That is cell for cell the
backend's own XP-432 entry (its aliases XP-235, XP-433 and XP-435 are in the same record).

Not verified on a real XP-231 or XP-230.

L3250 / L3258 -> ET-2812. reinkpy's epson.toml lists L3250 ... L3259 in the same record as
ET-2810 ... ET-2818 (read key 0x364A, write key "Maribaya"). ez-reset's devices.xml
(https://github.com/CiRIP/ez-reset, src/ez_reset/devices.xml) gives "L3250 Series",
"L3258 Series" and "ET-2812 Series" the same spec (EPSON,L3250), and its <L3250> record
matches the backend's ET-2812 entry cell for cell: waste counters 0x30/0x31/0x2F (max
6346), 0x32/0x33/0x2F (3416) and 0xFC/0xFD/0xFE (1300), the 15 reset bytes, the 0x100 &
0xFE completion step (the backend's waste_reset_commit), serial 0x644-0x64D and the stats
cells. The backend notes that many L3250 firmwares lock the EEPROM (epson_print_conf issue
#35); on those only the temporary reset ("rw", which needs only the serial) works.

Not verified on a real L3250 or L3258.
"""

#: model -> the backend model whose configuration it shares
MAPPED = {"XP-230": "XP-432", "XP-231": "XP-432",
          "L3250": "ET-2812", "L3258": "ET-2812"}


def apply(db, mapped=MAPPED):
    """Add the mapped models to the backend's database, in place. Returns the names added.

    Each new entry carries "backend_model" (the name the backend knows it by) and
    "identifies_as" (every other name that shares that configuration, which is what a
    printer of this kind may call itself).
    """
    original = dict(db)
    added = []
    for name, base in sorted(mapped.items()):
        if name in original or base not in original:
            continue
        same = {m for m, entry in original.items() if entry == original[base]}
        same |= {m for m, b in mapped.items() if b == base and m not in original}
        db[name] = {**original[base], "backend_model": base,
                    "identifies_as": sorted(same - {name})}
        added.append(name)
    return added
