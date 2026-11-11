# -*- coding: utf-8 -*-
"""
Giao diện điều khiển scrcpy
- Hiển thị danh sách thiết bị dạng:  serial (tên thiết bị)
- Lấy tên thiết bị tự động qua adb
- Chạy scrcpy trực tiếp (không mở cửa sổ CMD)
- Có hoạt ảnh loading sau nút chạy, tự dừng khi scrcpy tắt
"""
import os
import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scrcpy_gui_config.json")

DEFAULT_ARGS = "-m1280 --max-fps=60 --turn-screen-off --stay-awake"


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # Chuyển cấu trúc cũ (list) sang mới (dict serial -> tên)
            if isinstance(cfg.get("devices"), list):
                cfg["devices"] = {s: "" for s in cfg["devices"]}
            return cfg
        except Exception:
            pass
    return {"devices": {"14bdeec3": ""}, "scrcpy_path": "scrcpy.exe",
            "last_device": "14bdeec3"}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_device_name(serial):
    """Lấy tên model của thiết bị qua adb. Trả về '' nếu lỗi."""
    try:
        out = subprocess.check_output(
            ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
            stderr=subprocess.DEVNULL, timeout=8)
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


class ScrcpyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scrcpy Launcher")
        self.geometry("560x330")
        self.resizable(False, False)

        self.config = load_config()
        self.devices = self.config.get("devices", {})   # {serial: tên}
        self.display_map = {}                            # "serial (tên)" -> serial
        self._expand_tooltip = None

        # --- Dòng 1: chọn thiết bị ---
        frm1 = ttk.LabelFrame(self, text=" Thiết bị (serial - tên) ")
        frm1.pack(fill="x", padx=10, pady=8)

        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(frm1, textvariable=self.device_var,
                                         state="readonly", width=38)
        self.device_combo.pack(side="left", padx=8, pady=8)
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_change)

        ttk.Button(frm1, text="Thêm", command=self.add_device).pack(side="left", padx=3)
        ttk.Button(frm1, text="Xóa", command=self.remove_device).pack(side="left", padx=3)
        ttk.Button(frm1, text="adb devices", command=self.list_devices).pack(side="left", padx=3)

        # --- Dòng 2: đường dẫn scrcpy ---
        frm2 = ttk.LabelFrame(self, text=" Đường dẫn scrcpy.exe ")
        frm2.pack(fill="x", padx=10, pady=4)

        self.path_var = tk.StringVar(value=self.config.get("scrcpy_path", "scrcpy.exe"))
        ttk.Entry(frm2, textvariable=self.path_var, width=45).pack(side="left", padx=8, pady=8)
        ttk.Button(frm2, text="Duyệt...", command=self.browse_scrcpy).pack(side="left", padx=4)

        # --- Dòng 3: tham số bổ sung ---
        frm3 = ttk.LabelFrame(self, text=" Tham số bổ sung (tuỳ chọn) ")
        frm3.pack(fill="x", padx=10, pady=4)

        self.args_var = tk.StringVar(value=DEFAULT_ARGS)
        self.args_entry = ttk.Entry(frm3, textvariable=self.args_var, width=38)
        self.args_entry.pack(side="left", padx=(8, 4), pady=8)

        self.expand_button = ttk.Button(
            frm3, text="⤢", width=3, command=self._show_expanded_args
        )
        self.expand_button.pack(side="left", padx=2)
        self.expand_button.bind("<Enter>", self._show_expand_tooltip)
        self.expand_button.bind("<Leave>", self._hide_expand_tooltip)

        self.arg_menu = tk.Menu(self, tearoff=0)
        for option in ("Placeholder 1", "Placeholder 2", "Placeholder 3"):
            self.arg_menu.add_command(
                label=option,
                command=lambda value=option: self.add_argument(value)
            )

        self.args_button = ttk.Button(
            frm3, text="Thêm tham số", command=self._show_arg_menu
        )
        self.args_button.pack(side="left", padx=4)

        # --- Dòng 4: nút chạy + spinner ---
        frm4 = ttk.Frame(self)
        frm4.pack(fill="x", padx=10, pady=12)

        ttk.Button(frm4, text="▶ CHẠY SCRCPY", command=self.run_scrcpy).pack(side="left", padx=8)

        # Label hoạt ảnh loading
        self.spinner_frames = ["◐", "◓", "◑", "◒"]
        self.spinner_lbl = tk.Label(frm4, text="", font=("Segoe UI", 24),
                                    foreground="#0078D7")
        self.spinner_lbl.pack(side="left", padx=6)
        self._spin_id = None
        self._proc = None

        self.preview_var = tk.StringVar()
        ttk.Label(self, textvariable=self.preview_var, foreground="gray",
                  wraplength=540, justify="left").pack(fill="x", padx=12, pady=4)

        # Cập nhật preview ngay khi tham số thay đổi, kể cả khi xóa hết nội dung.
        self.args_var.trace_add("write", lambda *_: self._update_preview())

        self.refresh_combo(select_serial=self.config.get("last_device", ""))

    def _show_expand_tooltip(self, _event=None):
        if self._expand_tooltip:
            return
        self._expand_tooltip = tk.Toplevel(self)
        self._expand_tooltip.wm_overrideredirect(True)
        self._expand_tooltip.wm_geometry(
            f"+{self.expand_button.winfo_rootx()}+"
            f"{self.expand_button.winfo_rooty() + self.expand_button.winfo_height()}"
        )
        ttk.Label(self._expand_tooltip, text="expand", padding=(4, 2)).pack()

    def _hide_expand_tooltip(self, _event=None):
        if self._expand_tooltip:
            self._expand_tooltip.destroy()
            self._expand_tooltip = None

    def _show_expanded_args(self):
        win = tk.Toplevel(self)
        win.title("Tham số bổ sung")
        win.resizable(True, False)

        # Đặt cửa sổ bên dưới nút expand 50px; chiều cao đủ hiển thị ba dòng.
        self.update_idletasks()
        x = self.expand_button.winfo_rootx()
        y = self.expand_button.winfo_rooty() + self.expand_button.winfo_height() + 50
        win.geometry(f"760x100+{x}+{y}")
        win.transient(self)

        entry = ttk.Entry(win, textvariable=self.args_var)
        entry.pack(fill="x", padx=12, pady=16)
        entry.focus_set()
        entry.icursor(tk.END)

    def _show_arg_menu(self):
        self.arg_menu.tk_popup(
            self.args_button.winfo_rootx(),
            self.args_button.winfo_rooty() + self.args_button.winfo_height()
        )

    def add_argument(self, value):
        current = self.args_var.get().strip()
        self.args_var.set(f"{current} {value}".strip())
        self._update_preview()

    # ---------- hoạt ảnh loading ----------
    def start_spinner(self):
        self._animate(0)

    def stop_spinner(self):
        if self._spin_id:
            self.after_cancel(self._spin_id)
            self._spin_id = None
        self.spinner_lbl.config(text="")

    def _animate(self, i):
        self.spinner_lbl.config(text=self.spinner_frames[i % len(self.spinner_frames)])
        self._spin_id = self.after(80, self._animate, i + 1)

    # ---------- hiển thị thiết bị ----------
    def refresh_combo(self, select_serial=""):
        """Cập nhật danh sách hiển thị dạng 'serial (tên)'."""
        self.display_map = {}
        values = []
        for serial, name in self.devices.items():
            label = f"{serial} ({name})" if name else serial
            self.display_map[label] = serial
            values.append(label)
        self.device_combo["values"] = values
        for label, serial in self.display_map.items():
            if serial == select_serial:
                self.device_var.set(label)
                break
        else:
            if values:
                self.device_var.set(values[0])
        self._update_preview()

    def current_serial(self):
        return self.display_map.get(self.device_var.get(), "")

    def _on_device_change(self, _evt=None):
        self.config["last_device"] = self.current_serial()
        save_config(self.config)
        self._update_preview()

    def _update_preview(self):
        cmd = self.build_command()
        self.preview_var.set("Lệnh: " + " ".join(cmd))

    # ---------- logic ----------
    def build_command(self):
        exe = self.path_var.get().strip() or "scrcpy.exe"
        serial = self.current_serial()
        args = self.args_var.get().strip()
        cmd = [exe]
        if serial:
            cmd += ["-s", serial]
        if args:
            cmd += args.split()
        return cmd

    def add_device(self):
        win = tk.Toplevel(self)
        win.title("Thêm thiết bị")
        win.geometry("360x150")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="Serial:").grid(row=0, column=0, padx=8, pady=8, sticky="e")
        serial_var = tk.StringVar()
        ttk.Entry(win, textvariable=serial_var, width=30).grid(row=0, column=1, padx=8, pady=4)

        ttk.Label(win, text="Tên (tuỳ chọn):").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var, width=30).grid(row=1, column=1, padx=8, pady=4)

        def do_add():
            serial = serial_var.get().strip()
            if not serial:
                messagebox.showwarning("Thiếu serial", "Nhập ID thiết bị.", parent=win)
                return
            name = name_var.get().strip()
            if not name:
                # Tự lấy tên qua adb nếu thiết bị đang kết nối
                name = get_device_name(serial)
            self.devices[serial] = name
            self.config["devices"] = self.devices
            save_config(self.config)
            self.refresh_combo(select_serial=serial)
            win.destroy()

        ttk.Button(win, text="Lưu", command=do_add).grid(row=2, column=0, columnspan=2, pady=10)
        win.wait_window()

    def remove_device(self):
        serial = self.current_serial()
        if serial and serial in self.devices:
            del self.devices[serial]
            self.config["devices"] = self.devices
            save_config(self.config)
            self.refresh_combo()

    def browse_scrcpy(self):
        path = filedialog.askopenfilename(
            title="Chọn scrcpy.exe",
            filetypes=[("Executable", "*.exe"), ("Tất cả", "*.*")])
        if path:
            self.path_var.set(path)
            self.config["scrcpy_path"] = path
            save_config(self.config)
            self._update_preview()

    def run_scrcpy(self):
        # Chặn bấm 2 lần khi đang chạy
        if self._proc and self._proc.poll() is None:
            messagebox.showinfo("Đang chạy", "scrcpy đang chạy rồi.")
            return
        cmd = self.build_command()
        exe = cmd[0]
        if not os.path.isabs(exe) and not self._which(exe):
            local = os.path.join(os.path.dirname(os.path.abspath(__file__)), exe)
            if os.path.exists(local):
                cmd[0] = local
            else:
                messagebox.showerror("Không tìm thấy scrcpy.exe",
                                     "Không tìm thấy scrcpy.exe. Hãy bấm 'Duyệt...' để chỉ đúng đường dẫn.")
                return
        self.config["last_device"] = self.current_serial()
        save_config(self.config)
        # Chạy scrcpy trực tiếp, không mở cửa sổ CMD
        self._proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        self.start_spinner()
        self._watch_proc()

    def _watch_proc(self):
        """Theo dõi process scrcpy, dừng spinner khi nó tắt."""
        if self._proc and self._proc.poll() is None:
            self.after(300, self._watch_proc)
        else:
            self.stop_spinner()

    def list_devices(self):
        subprocess.Popen('start "adb devices" cmd /k "adb devices"', shell=True)

    @staticmethod
    def _which(name):
        from shutil import which
        return which(name)


if __name__ == "__main__":
    app = ScrcpyGUI()
    app.mainloop()
