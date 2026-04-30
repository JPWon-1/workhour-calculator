"""출퇴근정보 xlsx 분석 및 오늘 퇴근시각 계산.

회사 룰 (CLAUDE.md 참고):
- 출근: 30분 단위 올림 (08:30 이전 도착 → 08:30)
- 퇴근: 18:00 캡 (그 이후 미인정)
- 점심 1시간 차감
- 연차/시간 인정은 시간 단위 절삭 (1분 모자라면 1시간 손해)

사용법:
    python3 workhour.py <xlsx_path>
    python3 workhour.py <xlsx_path> --checkin 09:15
    python3 workhour.py <xlsx_path> --now 17:30
"""

import argparse
import calendar
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

LUNCH = 1.0
DAY_START = time(8, 30)
DAY_END = time(18, 0)
STANDARD_HOURS = 8.0


def parse_time(s: str) -> time:
    h, m = map(int, s.split(":"))
    return time(h, m)


def fmt_hm(hours: float) -> str:
    total_min = round(hours * 60)
    h, m = divmod(total_min, 60)
    return f"{h}시간 {m}분"


def round_checkin(t: time) -> time:
    """출근 라운딩: 08:30 이전 → 08:30, 이후는 다음 30분으로 올림."""
    if t <= DAY_START:
        return DAY_START
    if t.minute == 0 and t.second == 0:
        return t.replace(microsecond=0)
    if t.minute < 30 or (t.minute == 30 and t.second == 0):
        if t.minute == 30 and t.second == 0:
            return time(t.hour, 30)
        return time(t.hour, 30)
    dt = datetime.combine(date.today(), t).replace(minute=0, second=0, microsecond=0)
    return (dt + timedelta(hours=1)).time()


def cap_checkout(t: time) -> time:
    return min(t, DAY_END)


def hours_between(a: time, b: time) -> float:
    today = date.today()
    return (datetime.combine(today, b) - datetime.combine(today, a)).total_seconds() / 3600


def settle(checkin: time, checkout: time) -> float:
    ci = round_checkin(checkin)
    co = cap_checkout(checkout)
    if co <= ci:
        return 0.0
    return max(0.0, hours_between(ci, co) - LUNCH)


def add_hours(t: time, hours: float) -> time:
    dt = datetime.combine(date.today(), t) + timedelta(hours=hours)
    return dt.time()


def weekdays_in_month(year: int, month: int) -> int:
    _, last = calendar.monthrange(year, month)
    return sum(1 for d in range(1, last + 1) if date(year, month, d).weekday() < 5)


def floor_hour(h: float) -> int:
    return int(h)  # 시간 단위 절삭


def load_summary(xlsx: Path):
    df = pd.read_excel(xlsx)
    df["날짜_dt"] = pd.to_datetime(df["날짜"].str.extract(r"(\d{4}-\d{2}-\d{2})")[0]).dt.date
    df["요일"] = pd.to_datetime(df["날짜_dt"]).dt.dayofweek
    df["is_weekday"] = df["요일"] < 5
    df["정산"] = df["근무정산시간"].fillna(0).astype(float)
    return df


def report(xlsx: Path, checkin_today: time | None, now: datetime):
    df = load_summary(xlsx)
    name = df["이름"].iloc[0]
    today = now.date()
    year, month = today.year, today.month

    df_month = df[pd.to_datetime(df["날짜_dt"]).dt.month == month]
    has_today = (df_month["날짜_dt"] == today).any()

    df_past = df_month[df_month["날짜_dt"] != today] if has_today else df_month
    total_so_far = df_past["정산"].sum()
    weekdays_used = int(df_past["is_weekday"].sum())

    weekdays_total = weekdays_in_month(year, month)
    target_total = STANDARD_HOURS * weekdays_total
    weekdays_remaining = weekdays_total - weekdays_used

    print(f"=== {name} {year}-{month:02d} 근무현황 ===")
    print(f"누적(오늘 제외): {total_so_far:.2f}h / 평일 {weekdays_used}일")
    if weekdays_used:
        print(f"평균(누적):      {total_so_far/weekdays_used:.2f}h/일")
    print(f"이번달 평일:     {weekdays_total}일 (남은 평일 {weekdays_remaining}일)")
    print(f"목표(8h평균):    총 {target_total:.0f}h")
    print()

    is_weekday_today = today.weekday() < 5
    if not is_weekday_today:
        print(f"오늘({today}, 주말) — 근무일 아님")
        return

    need_today = target_total - total_so_far
    if weekdays_remaining > 1:
        share = need_today / weekdays_remaining
        print(f"=== 오늘 ({today.strftime('%m/%d %a')}) ===")
        print(f"남은 평일에 균등 분배 시: {share:.2f}h/일 필요")
        if share > 8.5:
            print(f"⚠️  하루 최대 8.5h 초과 — 평균 8h 달성 불가 확정")
        return

    ci_actual = checkin_today or DAY_START
    ci_rounded = round_checkin(ci_actual)
    max_today = settle(ci_actual, DAY_END)

    print(f"=== 오늘 ({today.strftime('%m/%d %a')}, 마지막 평일) ===")
    print(f"출근(실제):      {ci_actual.strftime('%H:%M')}")
    print(f"출근(라운딩):    {ci_rounded.strftime('%H:%M')}")
    print(f"오늘 최대 정산: {max_today:.2f}h ({ci_rounded.strftime('%H:%M')}~18:00, 점심 1h)")
    print(f"오늘 필요 정산: {need_today:.2f}h ({fmt_hm(need_today)})")
    print()

    if need_today <= 0:
        print("✅ 오늘 안 일해도 평균 8h 달성")
        print(f"권장 퇴근시각: {add_hours(ci_rounded, LUNCH).strftime('%H:%M')} 이후 아무때나")
    elif need_today > max_today:
        deficit = need_today - max_today
        proj_total = total_so_far + max_today
        proj_avg = proj_total / weekdays_total
        proj_floor = floor_hour(proj_avg)
        print(f"⚠️  풀근무해도 {fmt_hm(deficit)} 부족 — 평균 미달 확정")
        print(f"   풀근무 시 평균: {proj_avg:.4f}h → 시간 단위 절삭 시 {proj_floor}h 인정")
        print(f"   1분이라도 모자라면 시간 통째로 손해 → 일찍 퇴근 추천")
        print()
        early_checkout = time(17, 0)
        early_settle = settle(ci_actual, early_checkout)
        early_total = total_so_far + early_settle
        early_avg = early_total / weekdays_total
        print(f"권장 퇴근시각: {early_checkout.strftime('%H:%M')} (1시간 일찍)")
        print(f"   오늘 정산:  {early_settle:.2f}h ({fmt_hm(early_settle)})")
        print(f"   4월 평균:   {early_avg:.2f}h")
    else:
        checkout = add_hours(ci_rounded, need_today + LUNCH)
        print(f"권장 퇴근시각: {checkout.strftime('%H:%M:%S')}")
        print(f"   여유 두려면: {add_hours(checkout, 5/60).strftime('%H:%M')} 정도")

    if now.time() < DAY_END and is_weekday_today:
        if need_today > max_today:
            tgt = time(17, 0)
        elif need_today <= 0:
            tgt = add_hours(ci_rounded, LUNCH)
        else:
            tgt = add_hours(ci_rounded, need_today + LUNCH)
        if now.time() < tgt:
            remaining = (datetime.combine(today, tgt) - now).total_seconds() / 60
            print()
            print(f"지금 ({now.strftime('%H:%M')}) → 목표({tgt.strftime('%H:%M')})까지 {int(remaining)}분")


def main() -> int:
    p = argparse.ArgumentParser(description="출퇴근 분석 + 오늘 퇴근시각 계산")
    p.add_argument("xlsx", type=Path)
    p.add_argument("--checkin", type=parse_time, default=None, help="오늘 출근시각 HH:MM (기본 08:30)")
    p.add_argument("--now", type=parse_time, default=None, help="현재 시각 HH:MM (기본 시스템 시간)")
    args = p.parse_args()

    if not args.xlsx.exists():
        print(f"파일 없음: {args.xlsx}", file=sys.stderr)
        return 1

    if args.now:
        now = datetime.combine(date.today(), args.now)
    else:
        now = datetime.now()

    report(args.xlsx, args.checkin, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
