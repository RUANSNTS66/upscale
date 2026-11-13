import os
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog

from PIL import Image, ImageOps, ImageTk
from tkinterdnd2 import TkinterDnD, DND_FILES

MODEL_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
MODEL_PATH = Path(__file__).parent / "RealESRGAN_x4plus.pth"
EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ---------- aparência ----------
COR_IDLE_BG = "#f0f4ff"
COR_IDLE_BORDA = "#b5c3f0"
COR_HOVER_BG = "#dbe7ff"
COR_HOVER_BORDA = "#3b6cff"
COR_TEXTO = "#333333"
COR_TEXTO_HOVER = "#1f4fd8"
TEXTO_IDLE = "🖼️\n\nArraste uma ou mais imagens aqui\n\nou clique para escolher"
TEXTO_HOVER = "⬇️\n\nSolte a imagem aqui!"
PREVIA_MAX = (520, 190)
MAX_LINHAS_LOG = 1000


class RedirecionaSaida:
    """Joga tudo que seria impresso no console (print, avisos, tqdm...) para a janela de log."""

    def __init__(self, app, original):
        self.app = app
        self.original = original  # console de verdade (pode ser None)

    def write(self, texto):
        if not texto:
            return 0
        try:
            self.app.escrever_raw(texto)
        except Exception:
            pass
        if self.original is not None:
            try:
                self.original.write(texto)
            except Exception:
                pass
        return len(texto)

    def flush(self):
        if self.original is not None:
            try:
                self.original.flush()
            except Exception:
                pass

    def isatty(self):
        return False


class App:
    def __init__(self, root):
        self.root = root
        self.upsampler = None
        self.ocupado = False
        self.ultima_pasta = None

        # estado visual
        self.hover = False
        self.foto = None       # referência da prévia (evita o Tk "esquecer" a imagem)
        self.legenda = ""

        root.title("Upscale com IA")
        root.geometry("580x700")
        root.minsize(500, 620)

        self.escala = tk.IntVar(value=4)

        # Área de arrastar (moldura fixa + label dentro)
        self.moldura = tk.Frame(
            root, height=270, bg=COR_IDLE_BG,
            highlightthickness=4, highlightbackground=COR_IDLE_BORDA,
            highlightcolor=COR_IDLE_BORDA,
        )
        self.moldura.pack(fill="x", padx=16, pady=(16, 8))
        self.moldura.pack_propagate(False)

        self.drop = tk.Label(
            self.moldura, text=TEXTO_IDLE, bg=COR_IDLE_BG, fg=COR_TEXTO,
            font=("Segoe UI", 13), cursor="hand2", compound="top",
        )
        self.drop.pack(fill="both", expand=True)
        self.drop.drop_target_register(DND_FILES)
        self.drop.dnd_bind("<<DropEnter>>", self.ao_entrar)
        self.drop.dnd_bind("<<DropLeave>>", self.ao_sair)
        self.drop.dnd_bind("<<Drop>>", self.ao_soltar)
        self.drop.bind("<Button-1>", lambda e: self.escolher())

        # Escala
        frame = ttk.Frame(root)
        frame.pack(fill="x", padx=16, pady=4)
        ttk.Label(frame, text="Ampliar:", font=("Segoe UI", 11)).pack(side="left")
        ttk.Radiobutton(frame, text="2x", variable=self.escala, value=2).pack(side="left", padx=10)
        ttk.Radiobutton(frame, text="4x", variable=self.escala, value=4).pack(side="left")

        # Botão para adicionar nova imagem
        self.btn_nova = ttk.Button(root, text="➕  Adicionar nova imagem", command=self.escolher)
        self.btn_nova.pack(fill="x", padx=16, pady=(8, 4), ipady=4)

        self.status = ttk.Label(root, text="Pronto. Arraste uma imagem.", font=("Segoe UI", 10))
        self.status.pack(fill="x", padx=16, pady=(8, 2))
        self.barra = ttk.Progressbar(root, mode="determinate")
        self.barra.pack(fill="x", padx=16)

        # Janela de log (com barra de rolagem)
        quadro_log = ttk.Frame(root)
        quadro_log.pack(fill="both", expand=True, padx=16, pady=8)
        self.log = tk.Text(
            quadro_log, height=8, state="disabled", wrap="word",
            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", insertbackground="#d4d4d4",
        )
        rolagem = ttk.Scrollbar(quadro_log, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        self.btn_pasta = ttk.Button(root, text="Abrir pasta do resultado", command=self.abrir_pasta, state="disabled")
        self.btn_pasta.pack(pady=(0, 12))

        # Tudo que iria pro console agora vai também pra janela de log
        sys.stdout = RedirecionaSaida(self, sys.__stdout__)
        sys.stderr = RedirecionaSaida(self, sys.__stderr__)

        self.escrever("Programa iniciado. Aguardando imagem...")

    # ---------- parte visual da área de arrastar ----------
    def _render(self):
        if self.hover:
            bg, borda, fg = COR_HOVER_BG, COR_HOVER_BORDA, COR_TEXTO_HOVER
            self.drop.configure(image="", text=TEXTO_HOVER, bg=bg, fg=fg,
                                font=("Segoe UI", 15, "bold"))
        else:
            bg, borda, fg = COR_IDLE_BG, COR_IDLE_BORDA, COR_TEXTO
            if self.foto is not None:
                self.drop.configure(image=self.foto, text=self.legenda, bg=bg, fg=fg,
                                    font=("Segoe UI", 10), compound="top")
            else:
                self.drop.configure(image="", text=TEXTO_IDLE, bg=bg, fg=fg,
                                    font=("Segoe UI", 13))
        self.moldura.configure(bg=bg, highlightbackground=borda, highlightcolor=borda)

    def mostrar_previa(self, caminho, legenda):
        """Carrega a miniatura da imagem e mostra na área de arrastar."""
        try:
            img = Image.open(caminho)
            img = ImageOps.exif_transpose(img)
            img.thumbnail(PREVIA_MAX)
            self.foto = ImageTk.PhotoImage(img)
        except Exception:
            self.foto = None
        self.legenda = legenda
        self._render()

    def set_previa(self, caminho, legenda):
        self.root.after(0, lambda: self.mostrar_previa(caminho, legenda))

    def set_legenda(self, legenda):
        def f():
            self.legenda = legenda
            self._render()
        self.root.after(0, f)

    def ao_entrar(self, event):
        self.hover = True
        self._render()
        return event.action

    def ao_sair(self, event):
        self.hover = False
        self._render()
        return event.action

    # ---------- utilidades de UI (podem ser chamadas de qualquer thread) ----------
    def _inserir_log(self, texto):
        """Roda na thread principal. Trata '\\r' (barras de progresso) reescrevendo a linha."""
        self.log.configure(state="normal")
        partes = texto.split("\r")
        for i, parte in enumerate(partes):
            if i > 0:
                self.log.delete("end-1c linestart", "end-1c")
            self.log.insert("end", parte)
        # evita o log crescer sem limite
        total_linhas = int(self.log.index("end-1c").split(".")[0])
        if total_linhas > MAX_LINHAS_LOG:
            self.log.delete("1.0", f"{total_linhas - MAX_LINHAS_LOG}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def escrever_raw(self, texto):
        self.root.after(0, lambda: self._inserir_log(texto))

    def escrever(self, msg):
        hora = time.strftime("%H:%M:%S")
        self.escrever_raw(f"[{hora}] {msg}\n")

    def set_status(self, msg):
        self.root.after(0, lambda: self.status.configure(text=msg))

    def set_barra(self, valor, maximo=None):
        def f():
            if maximo is not None:
                self.barra.configure(maximum=maximo)
            self.barra.configure(value=valor)
        self.root.after(0, f)

    def abrir_pasta(self):
        if self.ultima_pasta:
            os.startfile(self.ultima_pasta)

    # ---------- entrada de arquivos ----------
    def escolher(self):
        arquivos = filedialog.askopenfilenames(
            title="Escolha as imagens",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp")],
        )
        if arquivos:
            self.iniciar([Path(a) for a in arquivos])

    def ao_soltar(self, event):
        self.hover = False
        self._render()
        caminhos = [Path(p) for p in self.root.tk.splitlist(event.data)]
        arquivos = []
        for c in caminhos:
            if c.is_dir():
                arquivos += sorted(f for f in c.iterdir() if f.suffix.lower() in EXTENSOES)
            elif c.suffix.lower() in EXTENSOES:
                arquivos.append(c)
        if not arquivos:
            self.escrever("Nenhuma imagem válida (use jpg, png, webp ou bmp).")
            return event.action
        self.iniciar(arquivos)
        return event.action

    def iniciar(self, arquivos):
        if self.ocupado:
            self.escrever("Aguarde, ainda processando...")
            return
        self.ocupado = True
        escala = self.escala.get()
        self.escrever(f"{len(arquivos)} imagem(ns) recebida(s). Ampliação: {escala}x")
        # prévia imediata da primeira imagem
        extra = f"  (+{len(arquivos) - 1})" if len(arquivos) > 1 else ""
        self.mostrar_previa(arquivos[0], f"{arquivos[0].name}{extra}\nPreparando...")
        threading.Thread(target=self.trabalhar, args=(arquivos, escala), daemon=True).start()

    # ---------- processamento (thread separada) ----------
    def baixar_modelo(self):
        ultimo = [-1]

        def progresso(blocos, tam_bloco, total):
            if total > 0:
                pct = min(100, blocos * tam_bloco * 100 // total)
                if pct != ultimo[0]:
                    ultimo[0] = pct
                    self.escrever_raw(f"\rBaixando modelo: {pct}%")
                    self.set_status(f"Baixando modelo: {pct}%")

        self.escrever("Modelo não encontrado. Baixando (~64 MB, só na primeira vez)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, progresso)
        self.escrever_raw("\n")
        self.escrever("Download do modelo concluído.")

    def carregar_modelo(self):
        if self.upsampler is not None:
            return

        self.set_status("Carregando bibliotecas de IA...")
        self.escrever("Carregando bibliotecas de IA (pode demorar na primeira vez)...")
        import torch
        import torchvision.transforms.functional as F

        # Conserto de compatibilidade com torchvision novo (antes de importar basicsr)
        try:
            import torchvision.transforms.functional_tensor  # noqa: F401
        except ModuleNotFoundError:
            sys.modules["torchvision.transforms.functional_tensor"] = F

        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        if not MODEL_PATH.exists():
            self.set_status("Baixando modelo (~64 MB, só na primeira vez)...")
            self.baixar_modelo()

        usa_gpu = torch.cuda.is_available()
        self.escrever("Usando: " + ("GPU (CUDA)" if usa_gpu else "CPU (mais lento)"))
        self.escrever("Carregando modelo de IA na memória...")

        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                        num_block=23, num_grow_ch=32, scale=4)
        self.upsampler = RealESRGANer(
            scale=4,
            model_path=str(MODEL_PATH),
            model=model,
            tile=256,
            tile_pad=10,
            pre_pad=0,
            half=usa_gpu,
            device="cuda" if usa_gpu else "cpu",
        )
        self.escrever("Modelo carregado e pronto.")

    def trabalhar(self, arquivos, escala):
        try:
            import cv2
            self.carregar_modelo()

            total = len(arquivos)
            self.set_barra(0, total)
            for i, arq in enumerate(arquivos, 1):
                self.set_status(f"Processando {i}/{total}: {arq.name}")
                self.set_previa(arq, f"{arq.name}  ({i}/{total})\n⏳ Processando...")
                self.escrever(f"Processando {i}/{total}: {arq.name}")
                img = cv2.imread(str(arq), cv2.IMREAD_UNCHANGED)
                if img is None:
                    self.escrever(f"[pulado] não consegui abrir {arq.name}")
                    continue
                inicio = time.time()
                resultado, _ = self.upsampler.enhance(img, outscale=escala)
                saida = arq.with_name(f"{arq.stem}_x{escala}.png")
                cv2.imwrite(str(saida), resultado)
                self.ultima_pasta = str(saida.parent)
                self.escrever(
                    f"{arq.name}: {img.shape[1]}x{img.shape[0]} -> "
                    f"{resultado.shape[1]}x{resultado.shape[0]} "
                    f"(levou {time.time() - inicio:.1f}s)"
                )
                self.escrever(f"Salvo em: {saida}")
                self.set_legenda(f"{arq.name}  ({i}/{total})\n✅ Pronto! Salvo como {saida.name}")
                self.set_barra(i)

            self.set_status("Concluído! O arquivo foi salvo ao lado do original (_x2 / _x4).")
            self.escrever("Tudo concluído.")
            self.root.after(0, lambda: self.btn_pasta.configure(state="normal"))
        except Exception:
            self.escrever("ERRO:\n" + traceback.format_exc())
            self.set_status("Ocorreu um erro (veja o log abaixo).")
            self.set_legenda("❌ Ocorreu um erro (veja o log)")
        finally:
            self.ocupado = False


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    App(root)
    root.mainloop()
