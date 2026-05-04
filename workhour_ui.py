"""출퇴근 계산기 GUI — macOS 네이티브 스타일.

실행:
    python3 workhour_ui.py
"""

from __future__ import annotations

import sys
import unicodedata
from datetime import date, datetime, time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd

import workhour as wh


# ────── 플랫폼/기본값 ──────────────────────────────────────────────

def _find_default_xlsx() -> str:
    dl = Path.home() / "Downloads"
    if not dl.exists():
        return ""
    keyword = unicodedata.normalize("NFC", "출퇴근정보")
    matches = []
    for p in dl.iterdir():
        if not p.is_file() or p.suffix.lower() != ".xlsx":
            continue
        if p.name.startswith("~$"):
            continue
        if keyword in unicodedata.normalize("NFC", p.name):
            matches.append(p)
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else ""


DEFAULT_XLSX = _find_default_xlsx()

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

if IS_MAC:
    FONT_FAMILY = "SF Pro Display"
    FONT_FAMILY_TEXT = "SF Pro Text"
    FONT_FAMILY_MONO = "SF Mono"
elif IS_WIN:
    FONT_FAMILY = "Segoe UI"
    FONT_FAMILY_TEXT = "Segoe UI"
    FONT_FAMILY_MONO = "Consolas"
else:
    FONT_FAMILY = "DejaVu Sans"
    FONT_FAMILY_TEXT = "DejaVu Sans"
    FONT_FAMILY_MONO = "DejaVu Sans Mono"

BG = "#f5f5f7"
CARD = "#ffffff"
TEXT = "#1d1d1f"
SUBTLE = "#6e6e73"
DIVIDER = "#d2d2d7"
ACCENT = "#0071e3"
SUCCESS = "#34c759"
WARNING = "#ff9500"
ERROR = "#ff3b30"


# ────── 유틸 ──────────────────────────────────────────────

def fmt_countdown(seconds: int) -> str:
    if seconds < 0:
        m, s = divmod(-seconds, 60)
        return f"+{m}분 {s:02d}초"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}시간 {m:02d}분 {s:02d}초"
    return f"{m}분 {s:02d}초"


def fmt_hm(hours: float) -> str:
    total_min = round(hours * 60)
    h, m = divmod(total_min, 60)
    if h and m:
        return f"{h}시간 {m}분"
    if h:
        return f"{h}시간"
    return f"{m}분"


def parse_time(s: str) -> time | None:
    s = s.strip()
    if not s:
        return None
    try:
        h, m = map(int, s.split(":"))
        return time(h, m)
    except Exception:
        return None


# ────── 컴포넌트 ──────────────────────────────────────────────

class Card(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, bg=CARD, highlightthickness=0, **kwargs)


# ────── 메인 앱 ──────────────────────────────────────────────

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.target_time: time | None = None
        self.subtitle = tk.StringVar(value="엑셀 파일을 선택하세요")

        self._setup_window()
        self._setup_style()
        self._build()
        self._tick()

        if DEFAULT_XLSX:
            self.root.after(150, self._run)

    def _setup_window(self):
        self.root.title("출퇴근 계산기")
        self.root.geometry("640x880")
        self.root.minsize(560, 800)
        self.root.configure(bg=BG)

    def _setup_style(self):
        style = ttk.Style()
        if IS_MAC:
            try:
                style.theme_use("aqua")
            except tk.TclError:
                style.theme_use("clam")
        else:
            style.theme_use("clam")
        style.configure("Big.Horizontal.TProgressbar", thickness=6)

    def _build(self):
        # ────── 헤더 ──────
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(20, 12))
        tk.Label(header, text="출퇴근 계산기",
                 font=(FONT_FAMILY, 26, "bold"),
                 fg=TEXT, bg=BG).pack(anchor="w")
        tk.Label(header, textvariable=self.subtitle,
                 font=(FONT_FAMILY_TEXT, 13),
                 fg=SUBTLE, bg=BG).pack(anchor="w", pady=(2, 0))

        # ────── 1. 오늘 카드 (목표 퇴근시각 + 카운트다운) ──────
        today_card = Card(self.root)
        today_card.pack(fill="x", padx=24, pady=8)
        ti = tk.Frame(today_card, bg=CARD)
        ti.pack(fill="x", padx=24, pady=22)

        # 상단 라벨
        tk.Label(ti, text="오늘의 목표 퇴근시각",
                 font=(FONT_FAMILY_TEXT, 12), fg=SUBTLE, bg=CARD
                 ).pack(anchor="w")

        self.target_label = tk.Label(
            ti, text="—",
            font=(FONT_FAMILY, 56, "bold"), fg=ACCENT, bg=CARD,
        )
        self.target_label.pack(anchor="w", pady=(4, 6))

        # 상태 배지
        self.status_label = tk.Label(
            ti, text="",
            font=(FONT_FAMILY_TEXT, 13, "bold"), fg=SUBTLE, bg=CARD,
        )
        self.status_label.pack(anchor="w", pady=(0, 14))

        # 진행바
        self.progress = ttk.Progressbar(
            ti, mode="determinate", length=100,
            style="Big.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(0, 14))

        # 카운트다운/현재 두 칸
        cd_row = tk.Frame(ti, bg=CARD)
        cd_row.pack(fill="x")
        cd_row.grid_columnconfigure(0, weight=1)
        cd_row.grid_columnconfigure(1, weight=1)

        cl = tk.Frame(cd_row, bg=CARD)
        cl.grid(row=0, column=0, sticky="w")
        tk.Label(cl, text="남은 시간", font=(FONT_FAMILY_TEXT, 11),
                 fg=SUBTLE, bg=CARD).pack(anchor="w")
        self.countdown_label = tk.Label(
            cl, text="—",
            font=(FONT_FAMILY, 22, "bold"), fg=TEXT, bg=CARD,
        )
        self.countdown_label.pack(anchor="w", pady=(2, 0))

        cr = tk.Frame(cd_row, bg=CARD)
        cr.grid(row=0, column=1, sticky="e")
        tk.Label(cr, text="현재 시각", font=(FONT_FAMILY_TEXT, 11),
                 fg=SUBTLE, bg=CARD).pack(anchor="e")
        self.now_label = tk.Label(
            cr, text=datetime.now().strftime("%H:%M:%S"),
            font=(FONT_FAMILY_MONO, 22), fg=SUBTLE, bg=CARD,
        )
        self.now_label.pack(anchor="e", pady=(2, 0))

        # ────── 2. 추천 카드 (왜 그 시각인지 설명) ──────
        reco_card = Card(self.root)
        reco_card.pack(fill="x", padx=24, pady=8)
        ri = tk.Frame(reco_card, bg=CARD)
        ri.pack(fill="x", padx=24, pady=18)
        tk.Label(ri, text="오늘 권장사항",
                 font=(FONT_FAMILY_TEXT, 12), fg=SUBTLE, bg=CARD
                 ).pack(anchor="w")
        self.reco_label = tk.Label(
            ri, text="—",
            font=(FONT_FAMILY_TEXT, 14), fg=TEXT, bg=CARD,
            wraplength=540, justify="left",
        )
        self.reco_label.pack(anchor="w", pady=(6, 0), fill="x")

        # ────── 3. 이번달 요약 카드 ──────
        sum_card = Card(self.root)
        sum_card.pack(fill="x", padx=24, pady=8)
        si = tk.Frame(sum_card, bg=CARD)
        si.pack(fill="x", padx=24, pady=18)
        tk.Label(si, text="이번 달 현황",
                 font=(FONT_FAMILY_TEXT, 12), fg=SUBTLE, bg=CARD
                 ).pack(anchor="w", pady=(0, 10))

        # 4칸 통계 그리드
        grid = tk.Frame(si, bg=CARD)
        grid.pack(fill="x")
        for i in range(4):
            grid.grid_columnconfigure(i, weight=1)

        self.stat_days = self._stat(grid, "출근일", 0)
        self.stat_total = self._stat(grid, "누적시간", 1)
        self.stat_avg = self._stat(grid, "일 평균", 2)
        self.stat_diff = self._stat(grid, "기준 대비", 3)

        # ────── 4. 설정 카드 ──────
        set_card = Card(self.root)
        set_card.pack(fill="x", padx=24, pady=8)
        seti = tk.Frame(set_card, bg=CARD)
        seti.pack(fill="x", padx=24, pady=16)

        # 파일
        self.path_var = tk.StringVar(value=DEFAULT_XLSX)
        self._row_label(seti, "엑셀 파일", 0)
        path_row = tk.Frame(seti, bg=CARD)
        path_row.grid(row=0, column=1, sticky="ew", pady=4)
        seti.grid_columnconfigure(1, weight=1)
        ttk.Entry(path_row, textvariable=self.path_var
                  ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(path_row, text="찾기",
                   command=self._browse).pack(side="left")

        # 출근
        self.checkin_var = tk.StringVar(value="08:30")
        self._row_label(seti, "출근 시각", 1)
        ci_row = tk.Frame(seti, bg=CARD)
        ci_row.grid(row=1, column=1, sticky="w", pady=4)
        e1 = ttk.Entry(ci_row, textvariable=self.checkin_var, width=10)
        e1.pack(side="left")
        e1.bind("<Return>", lambda _: self._run())
        tk.Label(ci_row, text="HH:MM · 30분 단위 자동 라운딩",
                 font=(FONT_FAMILY_TEXT, 11), fg=SUBTLE, bg=CARD
                 ).pack(side="left", padx=8)

        # 현재
        self.now_var = tk.StringVar(value="")
        self._row_label(seti, "현재 시각", 2)
        nw_row = tk.Frame(seti, bg=CARD)
        nw_row.grid(row=2, column=1, sticky="w", pady=4)
        e2 = ttk.Entry(nw_row, textvariable=self.now_var, width=10)
        e2.pack(side="left")
        e2.bind("<Return>", lambda _: self._run())
        tk.Label(nw_row, text="비우면 시스템 시간 사용",
                 font=(FONT_FAMILY_TEXT, 11), fg=SUBTLE, bg=CARD
                 ).pack(side="left", padx=8)

        # 분석 버튼
        ttk.Button(seti, text="분석 실행", command=self._run
                   ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _row_label(self, parent, text: str, row: int):
        tk.Label(parent, text=text,
                 font=(FONT_FAMILY_TEXT, 12), fg=TEXT, bg=CARD,
                 anchor="w", width=10
                 ).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))

    def _stat(self, parent, label: str, col: int):
        f = tk.Frame(parent, bg=CARD)
        f.grid(row=0, column=col, sticky="w", padx=(0, 12) if col < 3 else 0)
        tk.Label(f, text=label, font=(FONT_FAMILY_TEXT, 11),
                 fg=SUBTLE, bg=CARD).pack(anchor="w")
        val = tk.Label(f, text="—", font=(FONT_FAMILY, 20, "bold"),
                       fg=TEXT, bg=CARD)
        val.pack(anchor="w", pady=(2, 0))
        return val

    def _browse(self):
        p = filedialog.askopenfilename(
            filetypes=[("Excel", "*.xlsx"), ("All", "*.*")])
        if p:
            self.path_var.set(p)
            self._run()

    def _run(self):
        xlsx = Path(self.path_var.get())
        if not xlsx.exists():
            messagebox.showerror("오류", f"파일을 찾을 수 없습니다:\n{xlsx}")
            return

        ci = parse_time(self.checkin_var.get())
        now_t = parse_time(self.now_var.get())
        now = datetime.combine(date.today(), now_t) if now_t else datetime.now()

        try:
            df = wh.load_summary(xlsx)
        except Exception as e:
            messagebox.showerror("분석 실패", str(e))
            return

        self._update(df, ci, now)

    def _update(self, df: pd.DataFrame, ci_input: time | None, now: datetime):
        today = now.date()
        name = df["이름"].iloc[0]

        df_month = df[pd.to_datetime(df["날짜_dt"]).dt.month == today.month]
        df_past = df_month[df_month["날짜_dt"] != today]

        total_so_far = float(df_past["정산"].sum())
        weekdays_used = int(df_past["is_weekday"].sum())
        days_worked = int((df_past["정산"] > 0).sum())
        weekdays_total = wh.weekdays_in_month(today.year, today.month)

        target_total = wh.STANDARD_HOURS * weekdays_total
        avg = total_so_far / weekdays_used if weekdays_used else 0
        diff_so_far = total_so_far - wh.STANDARD_HOURS * weekdays_used

        # 헤더
        self.subtitle.set(f"{name} · {today.year}년 {today.month}월")

        # 통계
        self.stat_days.configure(text=f"{days_worked}일")
        self.stat_total.configure(text=f"{total_so_far:.2f}h")
        self.stat_avg.configure(
            text=f"{avg:.2f}h",
            fg=SUCCESS if avg >= 8 else WARNING,
        )
        sign = "+" if diff_so_far >= 0 else ""
        self.stat_diff.configure(
            text=f"{sign}{fmt_hm(abs(diff_so_far))}" if diff_so_far else "0",
            fg=SUCCESS if diff_so_far >= 0 else ERROR,
        )

        # 오늘 계산 + 추천
        if today.weekday() >= 5:
            self.target_time = None
            self.target_label.configure(text="주말", fg=SUBTLE)
            self.status_label.configure(text="휴무", fg=SUBTLE)
            self.reco_label.configure(
                text="오늘은 주말이라 근무일이 아닙니다. 푹 쉬세요.",
                fg=SUBTLE,
            )
            self.progress["value"] = 0
            return

        need = target_total - total_so_far
        ci_actual = ci_input or wh.DAY_START
        ci_rounded = wh.round_checkin(ci_actual)
        max_today = wh.settle(ci_actual, wh.DAY_END)

        if need <= 0:
            self.target_time = wh.add_hours(ci_rounded, wh.LUNCH)
            self.target_label.configure(text="✓ 달성", fg=SUCCESS)
            self.status_label.configure(
                text="이미 평균 8시간 달성", fg=SUCCESS)
            self.reco_label.configure(
                text=(f"이번 달 누적이 이미 평균 8시간을 넘었습니다. "
                      f"오늘은 출근만 찍어도 평균 유지됩니다."),
                fg=TEXT,
            )

        elif need > max_today:
            deficit = need - max_today
            proj_avg = (total_so_far + max_today) / weekdays_total
            early_co = time(17, 0)
            early_settle = wh.settle(ci_actual, early_co)
            early_avg = (total_so_far + early_settle) / weekdays_total

            self.target_time = early_co
            self.target_label.configure(text="17:00", fg=WARNING)
            self.status_label.configure(
                text="⚠ 평균 8시간 미달 확정", fg=WARNING)
            self.reco_label.configure(
                text=(
                    f"평균 8시간을 맞추려면 오늘 {fmt_hm(need)} 정산이 필요한데, "
                    f"회사 룰상 오늘 최대 {fmt_hm(max_today)}밖에 못 채웁니다 "
                    f"({fmt_hm(deficit)} 부족).\n\n"
                    f"풀근무해도 평균 {proj_avg:.4f}h → 시간 단위 절삭 시 "
                    f"{int(proj_avg)}시간만 인정됩니다. 어차피 1시간을 손해 보므로 "
                    f"17:00에 일찍 퇴근하는 것이 더 합리적입니다.\n\n"
                    f"→ 17:00 퇴근 시 오늘 정산 {fmt_hm(early_settle)}, "
                    f"4월 평균 {early_avg:.2f}h"
                ),
                fg=TEXT,
            )

        else:
            self.target_time = wh.add_hours(ci_rounded, need + wh.LUNCH)
            t_str = self.target_time.strftime("%H:%M:%S")
            self.target_label.configure(text=t_str[:5], fg=ACCENT)
            self.status_label.configure(
                text="✓ 평균 8시간 달성 가능", fg=SUCCESS)
            self.reco_label.configure(
                text=(
                    f"평균 8시간을 맞추려면 오늘 {fmt_hm(need)} 정산해야 합니다 "
                    f"(출근 {ci_rounded.strftime('%H:%M')} · 점심 1시간 차감 기준).\n\n"
                    f"→ {t_str} 이후 퇴근 찍으면 4월 평균 정확히 8시간이 됩니다. "
                    f"여유 두려면 1~2분 늦게 찍으세요."
                ),
                fg=TEXT,
            )

    def _tick(self):
        now = datetime.now()
        self.now_label.configure(text=now.strftime("%H:%M:%S"))

        if self.target_time is not None:
            tgt_dt = datetime.combine(now.date(), self.target_time)
            delta_s = int((tgt_dt - now).total_seconds())

            if delta_s <= 0:
                self.countdown_label.configure(
                    text="퇴근 가능", fg=SUCCESS)
            else:
                self.countdown_label.configure(
                    text=fmt_countdown(delta_s), fg=TEXT)

            ci = parse_time(self.checkin_var.get()) or wh.DAY_START
            ci_rounded = wh.round_checkin(ci)
            start_dt = datetime.combine(now.date(), ci_rounded)
            span = (tgt_dt - start_dt).total_seconds()
            elapsed = (now - start_dt).total_seconds()
            if span > 0:
                self.progress["value"] = max(0, min(100, elapsed / span * 100))
            else:
                self.progress["value"] = 100 if delta_s <= 0 else 0
        else:
            self.countdown_label.configure(text="—", fg=SUBTLE)
            self.progress["value"] = 0

        self.root.after(1000, self._tick)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
