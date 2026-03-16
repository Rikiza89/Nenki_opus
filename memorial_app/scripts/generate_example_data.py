"""Generate example Excel dataset with 100 Japanese person records across 3 sheets.

Each sheet uses a different column naming convention to exercise the auto-detect logic.
Death dates span from Meiji through Reiwa.
"""

import random
import datetime
from pathlib import Path

import pandas as pd

SURNAMES = [
    "佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
    "吉田", "山田", "佐々木", "松本", "井上", "木村", "林", "斎藤", "清水", "山口",
    "森", "池田", "橋本", "阿部", "石川", "山崎", "中島", "前田", "小川", "藤田",
    "岡田", "後藤", "長谷川", "石井", "村上", "近藤", "坂本", "遠藤", "青木", "藤井",
]

GIVEN_NAMES_M = [
    "太郎", "一郎", "二郎", "三郎", "正", "清", "茂", "勝", "進", "実",
    "健一", "和夫", "秀樹", "浩", "誠", "豊", "隆", "博", "修", "哲也",
]

GIVEN_NAMES_F = [
    "花子", "幸子", "和子", "節子", "敏子", "洋子", "久子", "文子", "美智子", "恵子",
    "由美", "直子", "京子", "真理子", "裕子", "智子", "明美", "弘子", "典子", "順子",
]

HOUMYOU_PREFIX = ["釈", "釋"]
HOUMYOU_CHARS = [
    "浄", "光", "真", "信", "慧", "法", "蓮", "徳", "善", "妙",
    "清", "覚", "智", "円", "照", "寂", "空", "明", "道", "念",
]

PREFECTURES = [
    "東京都", "神奈川県", "大阪府", "京都府", "愛知県", "北海道",
    "福岡県", "広島県", "宮城県", "新潟県", "石川県", "長野県",
]

CITIES = [
    "中央区", "港区", "新宿区", "横浜市", "大阪市", "京都市",
    "名古屋市", "札幌市", "福岡市", "広島市", "仙台市", "金沢市",
]


def random_death_date(era: str) -> datetime.date:
    ranges = {
        "meiji": (datetime.date(1868, 10, 1), datetime.date(1912, 7, 29)),
        "taisho": (datetime.date(1912, 7, 30), datetime.date(1926, 12, 24)),
        "showa_early": (datetime.date(1927, 1, 1), datetime.date(1960, 12, 31)),
        "showa_late": (datetime.date(1961, 1, 1), datetime.date(1989, 1, 7)),
        "heisei": (datetime.date(1989, 1, 8), datetime.date(2019, 4, 30)),
        "reiwa": (datetime.date(2019, 5, 1), datetime.date(2025, 12, 31)),
    }
    start, end = ranges[era]
    delta = (end - start).days
    return start + datetime.timedelta(days=random.randint(0, delta))


def random_buddhist_name(is_female: bool) -> str:
    prefix = random.choice(HOUMYOU_PREFIX)
    chars = random.sample(HOUMYOU_CHARS, 2)
    if is_female:
        return f"{prefix}{''.join(chars)}尼"
    return f"{prefix}{''.join(chars)}"


def format_era_date(d: datetime.date) -> str:
    from memorial_app.core.era_converter import gregorian_to_era
    era, year = gregorian_to_era(d)
    year_str = "元" if year == 1 else str(year)
    return f"{era.name}{year_str}年{d.month}月{d.day}日"


def generate_records(n: int) -> list[dict]:
    era_weights = {
        "meiji": 5, "taisho": 8, "showa_early": 20,
        "showa_late": 25, "heisei": 30, "reiwa": 12,
    }
    eras = list(era_weights.keys())
    weights = list(era_weights.values())

    records = []
    for _ in range(n):
        is_female = random.random() < 0.5
        surname = random.choice(SURNAMES)
        given = random.choice(GIVEN_NAMES_F if is_female else GIVEN_NAMES_M)
        name = f"{surname}\u3000{given}"

        era = random.choices(eras, weights=weights, k=1)[0]
        death_date = random_death_date(era)
        buddhist_name = random_buddhist_name(is_female)
        prefecture = random.choice(PREFECTURES)
        city = random.choice(CITIES)
        address = f"{prefecture}{city}{random.randint(1, 9)}-{random.randint(1, 30)}-{random.randint(1, 15)}"
        phone = f"0{random.randint(3, 9)}0-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
        family = f"{surname}\u3000{random.choice(GIVEN_NAMES_M)}"

        records.append({
            "name": name, "death_date": death_date, "buddhist_name": buddhist_name,
            "address": address, "phone": phone, "family": family, "is_female": is_female,
        })
    return records


def build_sheet1(records):
    rows = []
    for r in records:
        rows.append({
            "氏名": r["name"],
            "没年月日": format_era_date(r["death_date"]),
            "戒名": r["buddhist_name"],
            "施主名": r["family"],
            "住所": r["address"],
            "電話番号": r["phone"],
        })
    return pd.DataFrame(rows)


def build_sheet2(records):
    rows = []
    for r in records:
        rows.append({
            "お名前": r["name"],
            "ご命日": r["death_date"].strftime("%Y/%m/%d"),
            "法名": r["buddhist_name"],
            "ご遺族": r["family"],
            "連絡先": r["phone"],
        })
    return pd.DataFrame(rows)


def build_sheet3(records):
    rows = []
    for i, r in enumerate(records):
        if i % 2 == 0:
            date_str = format_era_date(r["death_date"])
        else:
            date_str = r["death_date"].isoformat()
        rows.append({
            "名前": r["name"],
            "命日": date_str,
            "法名": r["buddhist_name"],
            "備考": f"{'女性' if r['is_female'] else '男性'}",
        })
    return pd.DataFrame(rows)


def generate_example(output_path: Path):
    """Generate example dataset Excel file."""
    random.seed(42)
    records = generate_records(100)

    sheet1_recs = records[:40]
    sheet2_recs = records[40:75]
    sheet3_recs = records[75:]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        build_sheet1(sheet1_recs).to_excel(writer, sheet_name="寺院記録", index=False)
        build_sheet2(sheet2_recs).to_excel(writer, sheet_name="管理台帳", index=False)
        build_sheet3(sheet3_recs).to_excel(writer, sheet_name="DATA", index=False)


def main():
    output_path = Path(__file__).resolve().parent.parent.parent / "example_dataset.xlsx"
    generate_example(output_path)
    print(f"Example dataset generated: {output_path}")


if __name__ == "__main__":
    main()
