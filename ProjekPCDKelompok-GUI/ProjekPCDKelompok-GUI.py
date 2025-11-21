import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
from PIL import Image, ImageTk, ImageOps, ImageEnhance, ImageFilter, ImageDraw
import threading
import os

class ImageApp:
    def __init__(self, root):
        # Inisialisasi objek aplikasi dan layout utama
        self.root = root
        self.root.title("Aplikasi Pengolahan Citra Digital - GUI")
        self.root.geometry("1280x850")

        # --- STORAGE VARIABLES ---
        # Menyimpan image original, image hasil proses, referensi PhotoImage untuk Tkinter,
        # jalur file saat ini, dan riwayat undo
        self.img_original = None
        self.img_processed = None
        self.tk_img = None
        self.current_filepath = None
        
        self.history = []           # Stack untuk undo (menyimpan salinan image sebelumnya)
        self.zoom_scale = 1.0       # Skala zoom saat ini
        self.is_processing = False  # Flag untuk menandai apakah sedang memproses

        # Default warna untuk operasi boolean (RGB)
        self.bool_color = (255, 0, 0)

        # --- 1. TOP TOOLBAR ---
        # Toolbar atas berisi tombol Open, Save, Undo, Reset, dan Peek/Compare
        self.toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED, bg="#e1e1e1")
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        btn_config = {"padx": 10, "pady": 5, "bg": "#e1e1e1", "bd": 0, "activebackground": "#d9d9d9"}
        
        # File Group
        tk.Button(self.toolbar, text="📂 Open", command=self.open_image, **btn_config).pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="💾 Save", command=self.save_image, **btn_config).pack(side=tk.LEFT)
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # Undo/Reset
        tk.Button(self.toolbar, text="⟲ Undo", command=self.undo_action, **btn_config).pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="🔄 Reset", command=self.reset_image, **btn_config).pack(side=tk.LEFT)
        
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # --- NEW: PEEK / COMPARE BUTTON ---
        # Tombol khusus yang menampilkan gambar original saat ditekan dan mengembalikan gambar hasil saat dilepas
        self.btn_peek = tk.Button(self.toolbar, text="👁️ Tahan untuk Bandingkan (Hold)", 
                                  bg="#ffeba0", activebackground="#ffe082", padx=15, pady=5, bd=1)
        self.btn_peek.pack(side=tk.LEFT, padx=10)
        # Bind event untuk Hold (press) dan Release
        self.btn_peek.bind("<ButtonPress-1>", self.peek_start)
        self.btn_peek.bind("<ButtonRelease-1>", self.peek_end)

        # --- 2. MAIN LAYOUT ---
        # Menggunakan PanedWindow horizontal: sidebar kiri dan canvas utama kanan
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self.sidebar_frame = tk.Frame(self.main_paned, width=340, bg="#f0f0f0", padx=10, pady=10)
        self.main_paned.add(self.sidebar_frame, minsize=340)

        # Canvas Frame
        self.canvas_frame = tk.Frame(self.main_paned, bg="#2c3e50")
        self.main_paned.add(self.canvas_frame, stretch="always")

        # Scrollbars untuk canvas
        self.v_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.h_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Canvas tempat menampilkan gambar
        self.canvas = tk.Canvas(self.canvas_frame, bg="#2c3e50", 
                                xscrollcommand=self.h_scroll.set, 
                                yscrollcommand=self.v_scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)

        # Bind mouse wheel untuk zoom
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)

        # --- 3. BOTTOM STATUS BAR ---
        # Status bar bawah menampilkan info gambar, progress bar, dan kontrol zoom
        self.status_bar = tk.Frame(self.root, bd=1, relief=tk.SUNKEN, bg="#dcdcdc")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.lbl_image_info = tk.Label(self.status_bar, text="No image loaded", 
                                       bg="#dcdcdc", anchor="w", padx=10)
        self.lbl_image_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress = ttk.Progressbar(self.status_bar, mode='indeterminate', length=150)
        self.progress.pack(side=tk.LEFT, padx=10)

        tk.Label(self.status_bar, text="Zoom:", bg="#dcdcdc").pack(side=tk.RIGHT, padx=5)
        self.btn_zoom_in = tk.Button(self.status_bar, text="➕", command=self.zoom_in, width=3)
        self.btn_zoom_in.pack(side=tk.RIGHT, padx=2)
        
        self.lbl_zoom = tk.Label(self.status_bar, text="100%", width=6, bg="#dcdcdc")
        self.lbl_zoom.pack(side=tk.RIGHT, padx=2)
        
        self.btn_zoom_out = tk.Button(self.status_bar, text="➖", command=self.zoom_out, width=3)
        self.btn_zoom_out.pack(side=tk.RIGHT, padx=2)

        # --- BUILD SIDEBAR ---
        self.create_sidebar_widgets()
        
        # --- KEYBOARD SHORTCUTS ---
        self.setup_keyboard_shortcuts()

    # -------------------------------------------------------------
    # NEW FEATURE: PEEK / COMPARE
    # -------------------------------------------------------------
    def peek_start(self, event):
        """Tombol ditekan: tampilkan gambar original sementara (tanpa mengubah state)"""
        if self.img_original:
            self.lbl_image_info.config(text="👁️ Viewing Original Image", fg="blue")
            # Tampilkan temporary image original dengan skala zoom saat ini
            self._display_temp(self.img_original)

    def peek_end(self, event):
        """Tombol dilepas: kembalikan tampilan ke gambar hasil yang sedang aktif"""
        if self.img_processed:
            self.update_image_info()  # Kembalikan teks info
            self.display_image()      # Kembalikan tampilan ke gambar hasil

    def _display_temp(self, img_obj):
        """Helper - menampilkan objek PIL Image tertentu tanpa mengubah atribut image aplikasi.
        - Mengatur ukuran sesuai zoom_scale
        - Menempatkan gambar di tengah canvas jika lebih kecil dari canvas
        - Mengatur scrollregion sesuai ukuran baru"""
        if not img_obj: return
        orig_w, orig_h = img_obj.size
        new_w = int(orig_w * self.zoom_scale)
        new_h = int(orig_h * self.zoom_scale)
        
        img_disp = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(img_disp)  # Simpan reference agar tidak di-GC
        
        self.canvas.delete("all")
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if new_w < cw and new_h < ch:
            # Jika gambar lebih kecil dari canvas, posisikan di tengah
            self.canvas.create_image(cw//2, ch//2, anchor=tk.CENTER, image=self.tk_img)
        else:
            # Jika lebih besar, posisikan di pojok kiri atas dan aktifkan scrollbar
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

    # -------------------------------------------------------------
    # THREADING UTILITIES
    # -------------------------------------------------------------
    def start_processing(self):
        """Set flag proses aktif dan mulai progress bar serta ganti cursor"""
        self.is_processing = True
        self.progress.start(10)
        self.root.config(cursor="wait")

    def stop_processing(self):
        """Matikan flag proses, hentikan progress bar, kembalikan cursor"""
        self.is_processing = False
        self.progress.stop()
        self.root.config(cursor="")

    def process_with_thread(self, operation_func, *args, **kwargs):
        """Jalankan operasi image di thread terpisah agar UI tidak nge-hang.
        - Cek apakah sudah ada proses berjalan
        - Jalankan start_processing sebelum mulai, stop_processing setelah selesai
        - Tangani exception dan tampilkan messagebox di thread utama via root.after"""
        if self.is_processing:
            messagebox.showwarning("Processing", "Please wait for current operation to complete.")
            return
        
        self.start_processing()
        
        def worker():
            try:
                operation_func(*args, **kwargs)
            except Exception as e:
                # Pastikan messagebox dipanggil dari thread utama
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                # Hentikan indicator progress di thread utama
                self.root.after(0, self.stop_processing)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # -------------------------------------------------------------
    # UI BUILDERS
    # -------------------------------------------------------------
    def create_sidebar_widgets(self):
        """Bangun semua widget di sidebar: notebook tabs dan tombol-tombol operasi"""
        lbl_title = tk.Label(self.sidebar_frame, text="Control Panel", 
                             font=("Arial", 14, "bold"), bg="#f0f0f0")
        lbl_title.pack(pady=(0, 10))

        self.notebook = ttk.Notebook(self.sidebar_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tabs: Warna, Boolean, Filter, Math, Geometri
        self.tab_color = tk.Frame(self.notebook, bg="white", padx=10, pady=10)
        self.notebook.add(self.tab_color, text="Warna")
        self.build_color_tab()

        self.tab_bool = tk.Frame(self.notebook, bg="white", padx=10, pady=10)
        self.notebook.add(self.tab_bool, text="Boolean")  # Tab baru untuk operasi boolean
        self.build_bool_tab()

        self.tab_filter = tk.Frame(self.notebook, bg="white", padx=10, pady=10)
        self.notebook.add(self.tab_filter, text="Filter")
        self.build_filter_tab()

        self.tab_math = tk.Frame(self.notebook, bg="white", padx=10, pady=10)
        self.notebook.add(self.tab_math, text="Math")
        self.build_math_tab()

        self.tab_geo = tk.Frame(self.notebook, bg="white", padx=10, pady=10)
        self.notebook.add(self.tab_geo, text="Geometri")
        self.build_geo_tab()

    # -------------------------------------------------------------
    # NEW FEATURE: BOOLEAN TAB (Updated for Colors)
    # -------------------------------------------------------------
    def build_bool_tab(self):
        """Bangun tampilan tab boolean:
        - Penjelasan singkat
        - Color picker untuk memilih warna solid
        - Tombol operasi NOT, AND, OR, XOR yang memanggil op_boolean via thread"""
        tk.Label(self.tab_bool, text="Logika Boolean", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(self.tab_bool, text="Operasi terhadap Warna Solid:", 
                 bg="white", fg="gray", justify=tk.LEFT).pack(anchor="w", pady=(0,5))

        # Color Picker Section
        f_picker = tk.Frame(self.tab_bool, bg="white")
        f_picker.pack(fill="x", pady=5)
        
        tk.Button(f_picker, text="Pilih Warna", command=self.choose_bool_color).pack(side=tk.LEFT, padx=(0,5))
        # Preview warna yang dipilih (label dengan background warna)
        self.lbl_bool_color_preview = tk.Label(f_picker, bg="#ff0000", width=6, relief=tk.SUNKEN)  # Default Red
        self.lbl_bool_color_preview.pack(side=tk.LEFT)

        ttk.Separator(self.tab_bool, orient='horizontal').pack(fill='x', pady=10)

        # Tombol operasi boolean - setiap tombol memanggil op_boolean dalam thread
        tk.Button(self.tab_bool, text="NOT (Invert)", command=lambda: self.process_with_thread(self.op_boolean, "NOT"), width=20).pack(pady=3)
        tk.Button(self.tab_bool, text="AND (Multiply)", command=lambda: self.process_with_thread(self.op_boolean, "AND"), width=20).pack(pady=3)
        tk.Button(self.tab_bool, text="OR (Screen/Add)", command=lambda: self.process_with_thread(self.op_boolean, "OR"), width=20).pack(pady=3)
        tk.Button(self.tab_bool, text="XOR (Difference)", command=lambda: self.process_with_thread(self.op_boolean, "XOR"), width=20).pack(pady=3)

    def choose_bool_color(self):
        """Buka dialog color chooser dan simpan warna yang dipilih ke self.bool_color.
        - colorchooser.askcolor mengembalikan ((r,g,b), '#hex')"""
        color_code = colorchooser.askcolor(title="Choose Boolean Color", initialcolor="#ff0000")
        if color_code[0]:  # Jika pengguna memilih warna
            self.bool_color = tuple(map(int, color_code[0]))
            self.lbl_bool_color_preview.config(bg=color_code[1])

    # -------------------------------------------------------------
    # EXISTING TABS
    # -------------------------------------------------------------
    def build_color_tab(self):
        """Bangun tab warna: grayscale, negative, brightness, saturation, threshold"""
        tk.Button(self.tab_color, text="Grayscale", command=lambda: self.process_with_thread(self.op_grayscale), width=20).pack(pady=2)
        tk.Button(self.tab_color, text="Negative", command=lambda: self.process_with_thread(self.op_negative), width=20).pack(pady=2)
        ttk.Separator(self.tab_color, orient='horizontal').pack(fill='x', pady=8)
        
        tk.Label(self.tab_color, text="Brightness", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        self.scale_bright = tk.Scale(self.tab_color, from_=0.1, to=3.0, resolution=0.1, orient=tk.HORIZONTAL)
        self.scale_bright.set(1.0); self.scale_bright.pack(fill="x")
        tk.Button(self.tab_color, text="Apply Brightness", command=lambda: self.process_with_thread(self.op_brightness)).pack(pady=2)

        tk.Label(self.tab_color, text="Saturation", bg="white").pack(anchor="w")
        self.scale_sat = tk.Scale(self.tab_color, from_=0.0, to=3.0, resolution=0.1, orient=tk.HORIZONTAL)
        self.scale_sat.set(1.0); self.scale_sat.pack(fill="x")
        tk.Button(self.tab_color, text="Apply Saturation", command=lambda: self.process_with_thread(self.op_saturation)).pack(pady=2)

        ttk.Separator(self.tab_color, orient='horizontal').pack(fill='x', pady=8)
        tk.Label(self.tab_color, text="Threshold (Biner)", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        self.scale_binary = tk.Scale(self.tab_color, from_=0, to=255, orient=tk.HORIZONTAL)
        self.scale_binary.set(128); self.scale_binary.pack(fill="x")
        tk.Button(self.tab_color, text="Apply Threshold", command=lambda: self.process_with_thread(self.op_binary)).pack(pady=5, fill="x")

    def build_filter_tab(self):
        """Bangun tab filter: contrast, sharpness, noise, highpass"""
        tk.Label(self.tab_filter, text="Enhancement", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(self.tab_filter, text="Contrast", bg="white").pack(anchor="w")
        self.scale_contrast = tk.Scale(self.tab_filter, from_=0.5, to=3.0, resolution=0.1, orient=tk.HORIZONTAL)
        self.scale_contrast.set(1.0); self.scale_contrast.pack(fill="x")
        tk.Button(self.tab_filter, text="Apply Contrast", command=lambda: self.process_with_thread(self.op_contrast)).pack(pady=2)

        tk.Label(self.tab_filter, text="Sharpness", bg="white").pack(anchor="w")
        self.scale_sharp = tk.Scale(self.tab_filter, from_=0.0, to=5.0, resolution=0.1, orient=tk.HORIZONTAL)
        self.scale_sharp.set(1.0); self.scale_sharp.pack(fill="x")
        tk.Button(self.tab_filter, text="Apply Sharpness", command=lambda: self.process_with_thread(self.op_sharpness)).pack(pady=2)

        ttk.Separator(self.tab_filter, orient='horizontal').pack(fill='x', pady=8)
        tk.Label(self.tab_filter, text="Kernels & Noise", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Button(self.tab_filter, text="Add Gaussian Noise", command=lambda: self.process_with_thread(self.op_noise)).pack(fill="x", pady=2)
        tk.Button(self.tab_filter, text="Highpass Filter", command=lambda: self.process_with_thread(self.op_highpass)).pack(fill="x", pady=2)
        # Catatan: Laplace dan LoG dihapus sesuai permintaan

    def build_math_tab(self):
        """Bangun tab matematika: operasi pointwise add/sub/mul/div"""
        tk.Label(self.tab_math, text="Aritmatika", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(self.tab_math, text="Scalar:", bg="white").pack(anchor="w")
        self.entry_math = tk.Entry(self.tab_math)
        self.entry_math.insert(0, "50"); self.entry_math.pack(fill="x", pady=5)
        tk.Button(self.tab_math, text="(+) Tambah", command=lambda: self.process_with_thread(self.op_math, "add")).pack(fill="x", pady=2)
        tk.Button(self.tab_math, text="(-) Kurang", command=lambda: self.process_with_thread(self.op_math, "sub")).pack(fill="x", pady=2)
        tk.Button(self.tab_math, text="(*) Kali", command=lambda: self.process_with_thread(self.op_math, "mul")).pack(fill="x", pady=2)
        tk.Button(self.tab_math, text="(/) Bagi", command=lambda: self.process_with_thread(self.op_math, "div")).pack(fill="x", pady=2)

    def build_geo_tab(self):
        """Bangun tab geometri: translate, rotate, flip, crop"""
        tk.Label(self.tab_geo, text="Translation", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        f_trans = tk.Frame(self.tab_geo, bg="white"); f_trans.pack(fill="x")
        tk.Label(f_trans, text="X:", bg="white").pack(side="left")
        self.entry_trans_x = tk.Entry(f_trans, width=5); self.entry_trans_x.insert(0, "50"); self.entry_trans_x.pack(side="left", padx=2)
        tk.Label(f_trans, text="Y:", bg="white").pack(side="left")
        self.entry_trans_y = tk.Entry(f_trans, width=5); self.entry_trans_y.insert(0, "50"); self.entry_trans_y.pack(side="left", padx=2)
        tk.Button(f_trans, text="Go", command=lambda: self.process_with_thread(self.geo_translate)).pack(side="left", padx=5)

        ttk.Separator(self.tab_geo, orient='horizontal').pack(fill='x', pady=8)
        tk.Label(self.tab_geo, text="Rotation", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        self.scale_rot = tk.Scale(self.tab_geo, from_=0, to=360, orient=tk.HORIZONTAL)
        self.scale_rot.pack(fill="x")
        tk.Button(self.tab_geo, text="Apply Rotation", command=lambda: self.process_with_thread(self.geo_rotate)).pack(fill="x", pady=2)

        ttk.Separator(self.tab_geo, orient='horizontal').pack(fill='x', pady=8)
        tk.Label(self.tab_geo, text="Flip", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        f_flip = tk.Frame(self.tab_geo, bg="white"); f_flip.pack(fill="x")
        tk.Button(f_flip, text="Horiz", command=lambda: self.process_with_thread(self.geo_flip, "H")).pack(side="left", expand=True, fill="x", padx=2)
        tk.Button(f_flip, text="Vert", command=lambda: self.process_with_thread(self.geo_flip, "V")).pack(side="left", expand=True, fill="x", padx=2)

        ttk.Separator(self.tab_geo, orient='horizontal').pack(fill='x', pady=8)
        tk.Label(self.tab_geo, text="Crop (T, L, B, R)", bg="white", font=("Arial", 10, "bold")).pack(anchor="w")
        f_crop = tk.Frame(self.tab_geo, bg="white"); f_crop.pack(fill="x")
        self.entry_crop_t = tk.Entry(f_crop, width=3); self.entry_crop_t.insert(0, "0"); self.entry_crop_t.pack(side="left", padx=1)
        self.entry_crop_l = tk.Entry(f_crop, width=3); self.entry_crop_l.insert(0, "0"); self.entry_crop_l.pack(side="left", padx=1)
        self.entry_crop_b = tk.Entry(f_crop, width=3); self.entry_crop_b.insert(0, "0"); self.entry_crop_b.pack(side="left", padx=1)
        self.entry_crop_r = tk.Entry(f_crop, width=3); self.entry_crop_r.insert(0, "0"); self.entry_crop_r.pack(side="left", padx=1)
        tk.Button(self.tab_geo, text="Crop", command=lambda: self.process_with_thread(self.geo_crop)).pack(fill="x", pady=5)

    # -------------------------------------------------------------
    # LOGIC: BOOLEAN (UPDATED TO USE COLORS)
    # -------------------------------------------------------------
    def op_boolean(self, mode):
        """
        Lakukan operasi boolean antara gambar yang sedang aktif dan warna solid yang dipilih.
        - mode: "NOT", "AND", "OR", "XOR"
        - Operasi NOT menggunakan ImageOps.invert
        - Operasi AND menggunakan ImageChops.multiply
        - Operasi OR menggunakan ImageChops.screen
        - Operasi XOR menggunakan ImageChops.difference
        Setelah operasi, panggil display_image lewat root.after
        """
        if not self.img_processed: return
        
        self.save_history()  # Simpan ke history sebelum modifikasi
        w, h = self.img_processed.size
        
        # Import lokal ImageChops untuk operasi kanal efisien
        from PIL import ImageChops
        
        if mode == "NOT":
            # Invert seluruh piksel (negatif)
            self.img_processed = ImageOps.invert(self.img_processed)
        else:
            # Buat solid color image sesuai ukuran
            solid_color_img = Image.new("RGB", (w, h), self.bool_color)
            
            if mode == "AND":
                # Multiply -> mirip operasi AND untuk visual warna
                self.img_processed = ImageChops.multiply(self.img_processed, solid_color_img)
            elif mode == "OR":
                # Screen -> mirip operasi OR (menambah keterangan)
                self.img_processed = ImageChops.screen(self.img_processed, solid_color_img)
            elif mode == "XOR":
                # Difference -> perbedaan absolut -> mirip XOR
                self.img_processed = ImageChops.difference(self.img_processed, solid_color_img)

        # Update UI di thread utama
        self.root.after(0, self.display_image)

    # -------------------------------------------------------------
    # LOGIC: STANDARD OPERATIONS
    # -------------------------------------------------------------
    def open_image(self):
        """Buka dialog file, load image ke img_original dan img_processed, reset history dan zoom"""
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp")])
        if path:
            try:
                # Buka dan konversi ke RGB agar konsisten
                self.img_original = Image.open(path).convert("RGB")
                self.img_processed = self.img_original.copy()
                self.current_filepath = path
                self.history.clear()
                self.zoom_scale = 1.0
                self.display_image()
                self.update_image_info()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def save_image(self):
        """Simpan img_processed ke file via Save As dialog. Update current_filepath dan info file"""
        if not self.img_processed: return
        path = filedialog.asksaveasfilename(defaultextension=".jpg", 
                                            filetypes=[("JPG", "*.jpg"), ("PNG", "*.png"), ("BMP", "*.bmp")])
        if path:
            self.img_processed.save(path)
            self.current_filepath = path
            self.update_image_info()
            messagebox.showinfo("Saved", "Image saved successfully!")

    def reset_image(self):
        """Reset gambar hasil ke image original (simpan dulu ke history)"""
        if self.img_original:
            self.save_history()
            self.img_processed = self.img_original.copy()
            self.display_image()
            self.update_image_info()

    def display_image(self):
        """Render img_processed ke canvas sesuai zoom_scale dan atur scrollregion"""
        if not self.img_processed: return
        
        orig_w, orig_h = self.img_processed.size
        new_w = int(orig_w * self.zoom_scale)
        new_h = int(orig_h * self.zoom_scale)

        # Update label zoom
        self.lbl_zoom.config(text=f"{int(self.zoom_scale * 100)}%")
        img_disp = self.img_processed.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(img_disp)
        
        self.canvas.delete("all")
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        
        # Fallback ukuran canvas jika belum tergambar
        if cw < 10: cw, ch = 800, 600

        if new_w < cw and new_h < ch:
            # Jika gambar lebih kecil, posisikan di tengah
            self.canvas.create_image(cw//2, ch//2, anchor=tk.CENTER, image=self.tk_img)
        else:
            # Jika lebih besar, posisikan di pojok kiri atas dan aktifkan scrolling
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

    def zoom_in(self):
        """Perbesar zoom (faktor 1.1) lalu render ulang"""
        self.zoom_scale *= 1.1
        self.display_image()

    def zoom_out(self):
        """Perkecil zoom (faktor 1.1) lalu render ulang"""
        self.zoom_scale /= 1.1
        self.display_image()

    def on_mousewheel(self, event):
        """Handler universal untuk scroll wheel pada berbagai platform:
        - Pada beberapa sistem event.num digunakan (4/5)
        - Pada Windows/macOS menggunakan event.delta"""
        if not self.img_processed: return
        if event.num == 4 or event.delta > 0: self.zoom_in()
        elif event.num == 5 or event.delta < 0: self.zoom_out()

    # Operations (Color/Filter/Math/Geo)
    def op_grayscale(self):
        """Ubah gambar menjadi grayscale (konversi kembali ke RGB setelah itu)"""
        if self.img_processed:
            self.save_history()
            self.img_processed = ImageOps.grayscale(self.img_processed).convert("RGB")
            self.root.after(0, self.display_image)

    def op_negative(self):
        """Invert warna gambar (negative)"""
        if self.img_processed:
            self.save_history()
            self.img_processed = ImageOps.invert(self.img_processed)
            self.root.after(0, self.display_image)

    def op_binary(self):
        """Thresholding biner:
        - Ambil nilai threshold dari scale
        - Konversi ke mode L, terapkan point function, lalu kembalikan ke RGB"""
        if self.img_processed:
            self.save_history()
            thresh = self.scale_binary.get()
            fn = lambda x: 255 if x > thresh else 0
            self.img_processed = self.img_processed.convert("L").point(fn, mode='1').convert("RGB")
            self.root.after(0, self.display_image)

    def op_brightness(self):
        """Atur brightness dengan ImageEnhance"""
        if self.img_processed:
            self.save_history()
            factor = self.scale_bright.get()
            self.img_processed = ImageEnhance.Brightness(self.img_processed).enhance(factor)
            self.root.after(0, self.display_image)

    def op_saturation(self):
        """Atur saturasi (color) dengan ImageEnhance"""
        if self.img_processed:
            self.save_history()
            factor = self.scale_sat.get()
            self.img_processed = ImageEnhance.Color(self.img_processed).enhance(factor)
            self.root.after(0, self.display_image)

    def op_contrast(self):
        """Atur kontras dengan ImageEnhance"""
        if self.img_processed:
            self.save_history()
            factor = self.scale_contrast.get()
            self.img_processed = ImageEnhance.Contrast(self.img_processed).enhance(factor)
            self.root.after(0, self.display_image)

    def op_sharpness(self):
        """Atur ketajaman dengan ImageEnhance"""
        if self.img_processed:
            self.save_history()
            factor = self.scale_sharp.get()
            self.img_processed = ImageEnhance.Sharpness(self.img_processed).enhance(factor)
            self.root.after(0, self.display_image)

    def op_noise(self):
        """Tambahkan noise:
        - Menggunakan Image.effect_noise jika tersedia di versi Pillow
        - Blend noise layer dengan gambar asli
        - Jika tidak tersedia, tampilkan error agar pengguna update Pillow"""
        if not self.img_processed: return
        self.save_history()
        w, h = self.img_processed.size
        try:
            noise_layer = Image.effect_noise((w, h), 50).convert("RGB")
            self.img_processed = Image.blend(self.img_processed, noise_layer, 0.15)
            self.root.after(0, self.display_image)
        except AttributeError:
            # Jika Pillow versi lama tidak punya effect_noise
            self.root.after(0, lambda: messagebox.showerror("Error", "Update Pillow for noise support"))

    def op_highpass(self):
        """Filter highpass sederhana menggunakan kernel 3x3"""
        if self.img_processed:
            self.save_history()
            kernel = (-1, -1, -1, -1, 8, -1, -1, -1, -1)
            self.img_processed = self.img_processed.filter(ImageFilter.Kernel((3, 3), kernel, scale=1, offset=0))
            self.root.after(0, self.display_image)

    def op_math(self, mode):
        """Operasi aritmatika pointwise pada setiap channel:
        - Ambil nilai scalar dari entry, konversi ke float
        - Gunakan Image.point dengan lambda sesuai mode"""
        if not self.img_processed: return
        try: 
            val = float(self.entry_math.get())
            self.save_history()
            
            if mode == "add": self.img_processed = self.img_processed.point(lambda p: min(255, max(0, p + val)))
            elif mode == "sub": self.img_processed = self.img_processed.point(lambda p: min(255, max(0, p - val)))
            elif mode == "mul": self.img_processed = self.img_processed.point(lambda p: min(255, max(0, p * val)))
            elif mode == "div" and val != 0: self.img_processed = self.img_processed.point(lambda p: min(255, max(0, p / val)))
            
            self.root.after(0, self.display_image)
        except:
            # Silent pass jika input tidak valid
            pass

    def geo_translate(self):
        """Translasi gambar menggunakan transform AFFINE:
        - Ambil tx, ty dari entry
        - Gunakan fillcolor untuk mengisi area kosong"""
        if not self.img_processed: return
        try:
            self.save_history()
            tx, ty = int(self.entry_trans_x.get()), int(self.entry_trans_y.get())
            self.img_processed = self.img_processed.transform(
                self.img_processed.size, Image.AFFINE, (1, 0, -tx, 0, 1, -ty), fillcolor="black")
            self.root.after(0, self.display_image)
        except:
            pass

    def geo_rotate(self):
        """Rotasi gambar dengan angle dari scale_rot.
        - expand=True agar ukuran kanvas otomatis menyesuaikan rotasi"""
        if self.img_processed:
            self.save_history()
            angle = self.scale_rot.get()
            self.img_processed = self.img_processed.rotate(angle, expand=True)
            self.root.after(0, self.display_image)

    def geo_flip(self, mode):
        """Flip horizontal atau vertical"""
        if self.img_processed:
            self.save_history()
            m = Image.FLIP_LEFT_RIGHT if mode == "H" else Image.FLIP_TOP_BOTTOM
            self.img_processed = self.img_processed.transpose(m)
            self.root.after(0, self.display_image)

    def geo_crop(self):
        """Crop berdasarkan nilai T, L, B, R:
        - Konversi input ke integer
        - Hitung box (left, top, right, bottom) dan crop jika sah"""
        if self.img_processed:
            try:
                t, b = int(self.entry_crop_t.get()), int(self.entry_crop_b.get())
                l, r = int(self.entry_crop_l.get()), int(self.entry_crop_r.get())
                w, h = self.img_processed.size
                box = (l, t, w - r, h - b)
                # Pastikan box valid (right > left dan bottom > top)
                if box[2] > box[0] and box[3] > box[1]:
                    self.save_history()
                    self.img_processed = self.img_processed.crop(box)
                    self.root.after(0, self.display_image)
            except:
                pass

    # -------------------------------------------------------------
    # MISC
    # -------------------------------------------------------------
    def setup_keyboard_shortcuts(self):
        """Daftarkan shortcut keyboard umum:
        - Ctrl+O: Open
        - Ctrl+S: Save
        - Ctrl+Z: Undo
        - Ctrl+R: Reset
        - Ctrl+Plus / Ctrl+Minus: Zoom"""
        self.root.bind('<Control-o>', lambda e: self.open_image())
        self.root.bind('<Control-s>', lambda e: self.save_image())
        self.root.bind('<Control-z>', lambda e: self.undo_action())
        self.root.bind('<Control-r>', lambda e: self.reset_image())
        self.root.bind('<Control-plus>', lambda e: self.zoom_in())
        self.root.bind('<Control-minus>', lambda e: self.zoom_out())

    def save_history(self):
        """Simpan salinan img_processed ke history untuk undo.
        - Batasi panjang history ke 20 entry untuk menghemat memori"""
        if self.img_processed:
            if len(self.history) > 20:
                self.history.pop(0)
            self.history.append(self.img_processed.copy())

    def undo_action(self):
        """Undo: kembalikan state terakhir dari history jika ada"""
        if self.history:
            self.img_processed = self.history.pop()
            self.display_image()
            self.update_image_info()
        else:
            messagebox.showinfo("Undo", "No more actions to undo.")

    def update_image_info(self):
        """Perbarui label info gambar:
        - Tampilkan resolusi, mode, dan ukuran file jika path tersedia"""
        if not self.img_processed:
            self.lbl_image_info.config(text="No image loaded", fg="black")
            return
        
        width, height = self.img_processed.size
        mode = self.img_processed.mode
        
        size_info = ""
        if self.current_filepath and os.path.exists(self.current_filepath):
            file_size = os.path.getsize(self.current_filepath)
            if file_size < 1024: size_info = f" | {file_size} bytes"
            elif file_size < 1024 * 1024: size_info = f" | {file_size / 1024:.1f} KB"
            else: size_info = f" | {file_size / (1024 * 1024):.2f} MB"
        
        info_text = f"{width} × {height} px | {mode}{size_info}"
        self.lbl_image_info.config(text=info_text, fg="black")

if __name__ == "__main__":
    # Entry point aplikasi: buat Tk root dan jalankan mainloop
    root = tk.Tk()
    app = ImageApp(root)
    root.mainloop()
