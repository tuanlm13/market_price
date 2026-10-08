from enum import Enum
from typing import Dict, Any, List

class ConditionCode(str, Enum):
    N0 = "N0"  # New Sealed
    N1 = "N1"  # New Open Box
    U0 = "U0"  # Like New
    U1 = "U1"  # Used Good
    U2 = "U2"  # Used Normal
    U3 = "U3"  # Used Fair
    R0 = "R0"  # Repaired
    D0 = "D0"  # Defective
    P0 = "P0"  # Parts Only

CONDITION_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "code": "N0",
        "name": "New Sealed",
        "grade": "NEW",
        "multiplier_weight": 1.00,
        "description": "Nguyen seal nha san xuat, chua kich hoat hoac moi 100% fullbox."
    },
    {
        "code": "N1",
        "name": "New Open Box",
        "grade": "NEW",
        "multiplier_weight": 0.93,
        "description": "Moi khui hop kiem tra, chua qua su dung, day du phu kien zin."
    },
    {
        "code": "U0",
        "name": "Like New",
        "grade": "USED",
        "multiplier_weight": 0.88,
        "description": "Dep 99%, khong trầy xuoc, pin cao, nguyen ban chua qua sua chua."
    },
    {
        "code": "U1",
        "name": "Used Good",
        "grade": "USED",
        "multiplier_weight": 0.80,
        "description": "Hinh thuc 95-98%, xuoc dam nhe khong can mop, hoat dong hoan hao."
    },
    {
        "code": "U2",
        "name": "Used Normal",
        "grade": "USED",
        "multiplier_weight": 0.70,
        "description": "Hinh thuc 90-95%, can nhe hoac trầy nhieu cho, chuc nang binh thuong."
    },
    {
        "code": "U3",
        "name": "Used Fair",
        "grade": "USED",
        "multiplier_weight": 0.60,
        "description": "Hinh thuc xau, co the am man hinh, ho hao pin, chuc nang van dung duoc."
    },
    {
        "code": "R0",
        "name": "Repaired",
        "grade": "REPAIRED",
        "multiplier_weight": 0.55,
        "description": "Da qua sua chua / thay the linh kien (thay pin, thay man, sua nguon)."
    },
    {
        "code": "D0",
        "name": "Defective",
        "grade": "DEFECTIVE",
        "multiplier_weight": 0.35,
        "description": "Loi 1 hoac nhieu chuc nang (mat FaceID, loi cong HDMI, sap nguon)."
    },
    {
        "code": "P0",
        "name": "Parts Only",
        "grade": "PARTS",
        "multiplier_weight": 0.15,
        "description": "Xac may, vo man nat, chet nguon, chi ban lay linh kien."
    }
]

def get_condition_by_code(code: str) -> Dict[str, Any]:
    for item in CONDITION_DEFINITIONS:
        if item["code"] == code.upper():
            return item
    raise ValueError(f"Invalid condition code: {code}")
