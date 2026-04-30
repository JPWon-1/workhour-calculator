"""출퇴근 계산 GUI (Tkinter).

실행:
    python3 workhour_ui.py
"""

from __future__ import annotations

import io
import sys
import unicodedata
from contextlib import redirect_stdout
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tkinter import (
    BOTH,
    BOTTOM,
    END,
    LEFT,
    RIGHT,
    TOP,
    W,
    X,
    Button,
    Entry,
    Frame,
    Label,
    StringVar,
    Tk,
    filedialog,
    messagebox,
)
from tkinter.scrolledtext import ScrolledText

import workhour as wh

# 플랫폼별 기본 다운로드 폴더에서 출퇴근정보 xlsx 자동 탐색
# (macOS는 한글 파일명을 NFD로 저장 → glob 매칭 위해 정규화 비교)
def _find_default_xlsx() -> str:
    dl = Path.home() / "Downloads"
    if not dl.exists():
        return ""
    keyword = unicodedata.normalize("NFC", "출퇴근정보")
    matches = []
    for p in dl.iterdir():
        if not p.is_file() or p.suffix.lower() != ".xlsx":
            continue
        if p.name.startswith("~$"):  # 엑셀 임시파일 제외
            continue
        if keyword in unicodedata.normalize("NFC", p.name):
            matches.append(p)
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else ""


DEFAULT_XLSX = _find_default_xlsx()

# 플랫폼별 폰트
if sys.platform == "win32":
    MONO_FONT = ("Consolas", 11)
    UI_FONT = ("Segoe UI", 13, "bold")
elif sys.platform == "darwin":
    MONO_FONT = ("Menlo", 12)
    UI_FONT = ("Helvetica", 14, "bold")
else:
    MONO_FONT = ("DejaVu Sans Mono", 11)
    UI_FONT = ("DejaVu Sans", 13, "bold")


class App:
    def __init__(self, root: Tk):
        self.root = root
        root.title("출퇴근 계산기")
        root.geometry("760x620")

        self.path_var = StringVar(value=DEFAULT_XLSX)
        self.checkin_var = StringVar(value="08:30")
        self.now_var = StringVar(value=datetime.now().strftime("%H:%M"))
        self.target_time: time | None = None
        self.target_label_var = StringVar(value="—")
        self.countdown_var = StringVar(value="—")
        self.now_display_var = StringVar(value="—")

        self._build()
        self._tick()

    def _build(self):
        # 파일 선택
        f1 = Frame(self.root, padx=10, pady=8)
        f1.pack(fill=X)
        Label(f1, text="엑셀 파일:", width=10, anchor=W).pack(side=LEFT)
        Entry(f1, textvariable=self.path_var).pack(side=LEFT, fill=X, expand=True, padx=4)
        Button(f1, text="찾기", command=self._browse).pack(side=LEFT)

        # 입력
        f2 = Frame(self.root, padx=10, pady=4)
        f2.pack(fill=X)
        Label(f2, text="출근시각:", width=10, anchor=W).pack(side=LEFT)
        Entry(f2, textvariable=self.checkin_var, width=10).pack(side=LEFT, padx=4)
        Label(f2, text="(HH:MM, 라운딩 자동 적용)").pack(side=LEFT)

        f3 = Frame(self.root, padx=10, pady=4)
        f3.pack(fill=X)
        Label(f3, text="현재시각:", width=10, anchor=W).pack(side=LEFT)
        Entry(f3, textvariable=self.now_var, width=10).pack(side=LEFT, padx=4)
        Label(f3, text="(빈칸 가능 — 시스템 시간 사용)").pack(side=LEFT)

        # 버튼
        f4 = Frame(self.root, padx=10, pady=8)
        f4.pack(fill=X)
        Button(f4, text="분석 실행", command=self._run, width=15, height=1).pack(side=LEFT)
        Button(f4, text="현재시각으로", command=self._set_now).pack(side=LEFT, padx=8)

        # 카운트다운 패널
        panel = Frame(self.root, padx=10, pady=6, bg="#1e293b")
        panel.pack(fill=X, padx=10, pady=4)
        Label(panel, text="현재 ", fg="#94a3b8", bg="#1e293b").grid(row=0, column=0, sticky=W)
        Label(panel, textvariable=self.now_display_var, fg="#fbbf24", bg="#1e293b",
              font=UI_FONT).grid(row=0, column=1, sticky=W)
        Label(panel, text="   목표퇴근 ", fg="#94a3b8", bg="#1e293b").grid(row=0, column=2, sticky=W)
        Label(panel, textvariable=self.target_label_var, fg="#34d399", bg="#1e293b",
              font=UI_FONT).grid(row=0, column=3, sticky=W)
        Label(panel, text="   남은시간 ", fg="#94a3b8", bg="#1e293b").grid(row=0, column=4, sticky=W)
        Label(panel, textvariable=self.countdown_var, fg="#f87171", bg="#1e293b",
              font=UI_FONT).grid(row=0, column=5, sticky=W)

        # 결과 출력
        self.output = ScrolledText(self.root, font=MONO_FONT, bg="#0f172a", fg="#e2e8f0")
        self.output.pack(fill=BOTH, expand=True, padx=10, pady=(4, 10))

    def _browse(self):
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx"), ("All", "*.*")])
        if p:
            self.path_var.set(p)

    def _set_now(self):
        self.now_var.set(datetime.now().strftime("%H:%M"))

    def _parse_time(self, s: str) -> time | None:
        s = s.strip()
        if not s:
            return None
        try:
            h, m = map(int, s.split(":"))
            return time(h, m)
        except Exception:
            return None

    def _run(self):
        xlsx = Path(self.path_var.get())
        if not xlsx.exists():
            messagebox.showerror("오류", f"파일 없음: {xlsx}")
            return

        ci = self._parse_time(self.checkin_var.get())
        now_t = self._parse_time(self.now_var.get())
        now = datetime.combine(date.today(), now_t) if now_t else datetime.now()

        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                wh.report(xlsx, ci, now)
        except Exception as e:
            messagebox.showerror("오류", str(e))
            return

        self.output.delete("1.0", END)
        self.output.insert(END, buf.getvalue())

        self._compute_target(xlsx, ci, now)

    def _compute_target(self, xlsx: Path, ci_input: time | None, now: datetime):
        try:
            df = wh.load_summary(xlsx)
            today = now.date()
            df_month = df[
                (__import__("pandas").to_datetime(df["날짜_dt"]).dt.month == today.month)
                & (df["날짜_dt"] != today)
            ]
            total_so_far = df_month["정산"].sum()
            weekdays_used = int(df_month["is_weekday"].sum())
            weekdays_total = wh.weekdays_in_month(today.year, today.month)
            target_total = wh.STANDARD_HOURS * weekdays_total
            need = target_total - total_so_far

            if today.weekday() >= 5 or weekdays_total - weekdays_used != 1:
                self.target_time = None
                self.target_label_var.set("—")
                return

            ci_actual = ci_input or wh.DAY_START
            ci_rounded = wh.round_checkin(ci_actual)
            max_today = wh.settle(ci_actual, wh.DAY_END)

            if need > max_today:
                self.target_time = time(17, 0)
            elif need <= 0:
                self.target_time = wh.add_hours(ci_rounded, wh.LUNCH)
            else:
                self.target_time = wh.add_hours(ci_rounded, need + wh.LUNCH)
            self.target_label_var.set(self.target_time.strftime("%H:%M:%S"))
        except Exception:
            self.target_time = None
            self.target_label_var.set("—")

    def _tick(self):
        now = datetime.now()
        self.now_display_var.set(now.strftime("%H:%M:%S"))
        if self.target_time is not None:
            tgt_dt = datetime.combine(now.date(), self.target_time)
            delta = tgt_dt - now
            if delta.total_seconds() > 0:
                total = int(delta.total_seconds())
                h, rem = divmod(total, 3600)
                m, s = divmod(rem, 60)
                if h:
                    self.countdown_var.set(f"{h}시간 {m}분 {s}초")
                else:
                    self.countdown_var.set(f"{m}분 {s}초")
            else:
                over = int(-delta.total_seconds())
                m, s = divmod(over, 60)
                self.countdown_var.set(f"퇴근 가능 (+{m}분 {s}초)")
        else:
            self.countdown_var.set("—")
        self.root.after(1000, self._tick)


def main():
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
