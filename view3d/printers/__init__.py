"""One module per printer family; each one's STYLES maps a style name (data["style"],
printer3d.MODELS) to the function that builds it with the parts in view3d/parts.py.
A new family: add its module here."""
from printers import (brother_t420w, canon_g3110, epson_l3150, epson_xp2100, hp_deskjet,
                      hp_ink_tank, hp_smart_tank, laser)

STYLES = {}
for _family in (epson_l3150, epson_xp2100, hp_smart_tank, hp_ink_tank, hp_deskjet,
                canon_g3110, brother_t420w, laser):
    STYLES.update(_family.STYLES)
