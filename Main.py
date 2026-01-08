import os
import subprocess
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --- CORES E TEMA ---
CORES = {
    "bg": "#36393f",          
    "fg": "#dcddde",           
    "input_bg": "#40444b",    
    "input_fg": "#ffffff",     
    "drop_bg": "#2f3136",      
    "drop_border": "#202225", 
    "btn_bg": "#5865F2",       
    "btn_hover": "#4752c4",
    "btn_fg": "#ffffff",
    "secondary_bg": "#4f545c", 
    "secondary_hover": "#686d73",
    "destaque": "#3ba55c",     
    "erro": "#ed4245"
}

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    USAR_DND = True
except ImportError:
    USAR_DND = False

# --- Funções Visuais ---
def adicionar_hover(widget, cor_normal, cor_hover):
    widget.bind("<Enter>", lambda e: widget.config(bg=cor_hover))
    widget.bind("<Leave>", lambda e: widget.config(bg=cor_normal))

# --- Funções do Sistema ---
def pegar_caminho_ferramenta(nome_arquivo):
    caminho = os.path.join(os.getcwd(), nome_arquivo)
    if os.path.exists(caminho): return caminho
    return None

def obter_duracao(caminho_arquivo, ffprobe_path):
    cmd = [ffprobe_path, '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', caminho_arquivo]
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    try:
        processo = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
        dados = json.loads(processo.stdout)
        return float(dados['format']['duration'])
    except: return 0.0

# --- Lógica de Compressão ---
def logica_compressao(arquivo_entrada, pasta_saida, tamanho_mb, status_cb, progress_cb):
    log_erros = ""
    try:
        ffmpeg_exe = pegar_caminho_ferramenta("ffmpeg.exe")
        ffprobe_exe = pegar_caminho_ferramenta("ffprobe.exe")

        if not ffmpeg_exe or not ffprobe_exe:
            messagebox.showerror("Faltam Arquivos", "ffmpeg.exe ou ffprobe.exe não estão na pasta.")
            status_cb("Erro: Ferramentas ausentes.")
            return

        arquivo_entrada = arquivo_entrada.strip('{}').strip('"').strip("'")
        if not os.path.exists(arquivo_entrada):
            messagebox.showerror("Erro", "Arquivo não encontrado.")
            return

        nome_base = os.path.basename(arquivo_entrada)
        nome_sem_ext = os.path.splitext(nome_base)[0]
        arquivo_saida = os.path.join(pasta_saida, f"{nome_sem_ext}_COMPRIMIDO.mp4")
        
        status_cb("Calculando duração...")
        duracao_total = obter_duracao(arquivo_entrada, ffprobe_exe)
        
        if duracao_total == 0:
            status_cb("Falha ao ler vídeo.")
            messagebox.showerror("Erro", "Arquivo corrompido.")
            return

        tamanho_seguro = tamanho_mb * 0.95
        tamanho_bits = tamanho_seguro * 8192 * 1024
        bitrate_total_kbps = (tamanho_bits / duracao_total) / 1024
        video_bitrate = int(bitrate_total_kbps - 128)
        
        if video_bitrate < 50:
            messagebox.showerror("Erro", "Vídeo muito longo para esse tamanho.")
            status_cb("Cancelado.")
            return

        status_cb(f"Iniciando... (Meta: {video_bitrate}k)")
        
        cmd = [
            ffmpeg_exe, '-y', '-i', arquivo_entrada,
            '-c:v', 'libx264', '-preset', 'medium',
            '-b:v', f'{video_bitrate}k', '-maxrate', f'{video_bitrate}k', '-bufsize', f'{video_bitrate*2}k',
            '-c:a', 'aac', '-b:a', '128k',
            '-progress', 'pipe:1', '-nostats', arquivo_saida
        ]
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        processo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo)

        while True:
            linha = processo.stdout.readline()
            if not linha and processo.poll() is not None: break
            
            if linha:
                log_erros += linha
                if "out_time=" in linha:
                    try:
                        tempo_str = linha.split('out_time=')[1].split('.')[0]
                        parts = list(map(int, tempo_str.split(':')))
                        segundos_atuais = parts[0]*3600 + parts[1]*60 + parts[2]
                        porcentagem = (segundos_atuais / duracao_total) * 100
                        progress_cb(porcentagem)
                        status_cb(f"Comprimindo: {porcentagem:.1f}%")
                    except: pass

        if processo.returncode == 0:
            progress_cb(100)
            status_cb("Concluído!")
            messagebox.showinfo("Sucesso", f"Vídeo salvo em:\n{arquivo_saida}")
        else:
            status_cb("Erro na compressão.")
            linhas_erro = log_erros.splitlines()[-10:]
            messagebox.showerror("FFmpeg Falhou", "\n".join(linhas_erro))

    except Exception as e:
        status_cb("Erro Crítico.")
        messagebox.showerror("Erro", str(e))

# --- Interface Gráfica ---
def iniciar_thread():
    caminho = entry_caminho.get()
    pasta = entry_pasta.get()
    if not caminho or not pasta: return
    try: tamanho = float(entry_tamanho.get())
    except: return

    btn_comprimir.config(state=tk.DISABLED, bg=CORES["input_bg"], text="PROCESSANDO...")
    barra_progresso['value'] = 0
    threading.Thread(target=executar, args=(caminho, pasta, tamanho)).start()

def executar(c, p, t):
    logica_compressao(c, p, t, atualizar_texto, atualizar_barra)
    root.after(0, resetar_ui)

def atualizar_texto(texto):
    root.after(0, lambda: lbl_status.config(text=texto))

def atualizar_barra(valor):
    root.after(0, lambda: barra_progresso.configure(value=valor))

def resetar_ui():
    btn_comprimir.config(state=tk.NORMAL, bg=CORES["btn_bg"], text="COMPRIMIR VÍDEO")
    adicionar_hover(btn_comprimir, CORES["btn_bg"], CORES["btn_hover"])

def atualizar_input_visual(caminho):
    """Atualiza o campo e o texto da Drop Zone"""
    entry_caminho.delete(0, tk.END)
    entry_caminho.insert(0, caminho)
    
    nome = os.path.basename(caminho)
    # Muda o texto da caixa grande pra mostrar que pegou
    lbl_drop.config(text=f"✅ {nome}\n(Clique para trocar)", fg=CORES["destaque"])

def sel_arquivo_dialog():
    a = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi")])
    if a:
        atualizar_input_visual(a)

def sel_pasta():
    p = filedialog.askdirectory()
    if p:
        entry_pasta.delete(0, tk.END)
        entry_pasta.insert(0, p)

def ao_soltar(event):
    c = event.data.strip('{}')
    atualizar_input_visual(c)

# --- Montagem da Janela ---
if USAR_DND:
    root = TkinterDnD.Tk()
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', ao_soltar)
else:
    root = tk.Tk()

root.title("Compressor de Video By Teteu")
root.geometry("500x550") 
root.resizable(False, False)
root.configure(bg=CORES["bg"])

style = ttk.Style()
style.theme_use('clam')
style.configure("green.Horizontal.TProgressbar", foreground=CORES["destaque"], background=CORES["destaque"], troughcolor=CORES["input_bg"], bordercolor=CORES["bg"], lightcolor=CORES["destaque"], darkcolor=CORES["destaque"])

frame = tk.Frame(root, bg=CORES["bg"], padx=25, pady=25)
frame.pack(fill=tk.BOTH, expand=True)

tk.Label(frame, text="Compressor de Vídeo", bg=CORES["bg"], fg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 20))

# --- DROP ZONE ---
frame_drop = tk.Frame(frame, bg=CORES["drop_border"], bd=2, relief="groove")
frame_drop.pack(fill=tk.X, pady=(0, 20))

lbl_drop = tk.Label(
    frame_drop, 
    text="🎬\nARRASTE SEU VÍDEO AQUI\n(ou clique para buscar)", 
    bg=CORES["drop_bg"], 
    fg="#b9bbbe", 
    font=("Segoe UI", 11, "bold"),
    height=4,
    cursor="hand2"
)
lbl_drop.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
lbl_drop.bind("<Button-1>", lambda e: sel_arquivo_dialog())
adicionar_hover(lbl_drop, CORES["drop_bg"], "#36393f")


# 1. Arquivo (Input escondido/backup)
tk.Label(frame, text="CAMINHO DO ARQUIVO", bg=CORES["bg"], fg="#72767d", font=("Segoe UI", 8, "bold")).pack(anchor="w")
entry_caminho = tk.Entry(frame, bg=CORES["input_bg"], fg=CORES["input_fg"], relief="flat", font=("Segoe UI", 9))
entry_caminho.pack(fill=tk.X, ipady=4, pady=(5, 15))

# 2. Pasta
tk.Label(frame, text="SALVAR EM", bg=CORES["bg"], fg="#b9bbbe", font=("Segoe UI", 8, "bold")).pack(anchor="w")
f2 = tk.Frame(frame, bg=CORES["bg"])
f2.pack(fill=tk.X, pady=(5, 15))
entry_pasta = tk.Entry(f2, bg=CORES["input_bg"], fg=CORES["input_fg"], relief="flat", font=("Segoe UI", 10))
entry_pasta.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0,5))
entry_pasta.insert(0, os.path.join(os.path.expanduser("~"), "Desktop"))
btn_past = tk.Button(f2, text="📂", command=sel_pasta, bg=CORES["secondary_bg"], fg="white", relief="flat", cursor="hand2")
btn_past.pack(side=tk.RIGHT, ipadx=10, ipady=1)
adicionar_hover(btn_past, CORES["secondary_bg"], CORES["secondary_hover"])

# 3. Tamanho
tk.Label(frame, text="TAMANHO (MB)", bg=CORES["bg"], fg="#b9bbbe", font=("Segoe UI", 8, "bold")).pack(anchor="w")
entry_tamanho = tk.Entry(frame, bg=CORES["input_bg"], fg=CORES["input_fg"], relief="flat", width=10, font=("Segoe UI", 10))
entry_tamanho.insert(0, "10")
entry_tamanho.pack(anchor="w", ipady=4, pady=5)

# Botão
btn_comprimir = tk.Button(frame, text="COMPRIMIR VÍDEO", bg=CORES["btn_bg"], fg=CORES["btn_fg"], font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2", command=iniciar_thread)
btn_comprimir.pack(fill=tk.X, ipady=8, pady=(20, 15))
adicionar_hover(btn_comprimir, CORES["btn_bg"], CORES["btn_hover"])

# Barra e Status
barra_progresso = ttk.Progressbar(frame, style="green.Horizontal.TProgressbar", orient="horizontal", length=100, mode='determinate')
barra_progresso.pack(fill=tk.X)

lbl_status = tk.Label(frame, text="Aguardando arquivo...", bg=CORES["bg"], fg="#b9bbbe", font=("Segoe UI", 9))
lbl_status.pack(fill=tk.X, pady=(10, 10))

root.mainloop()