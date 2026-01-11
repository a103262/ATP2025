import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import threading
import traceback
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import random
from collections import Counter
from simulacao import SimulacaoClinica, carregar_pacientes_json, calcular_estatisticas

# --- PALETA DE CORES "PROFESSIONAL DARK" ---
COLOR_SIDEBAR_BG = "#2c3e50"    # Azul Petróleo Escuro
COLOR_SIDEBAR_FG = "#ecf0f1"    # Texto Claro
COLOR_MAIN_BG = "#f4f6f9"       # Fundo Cinza Claro
COLOR_ACCENT = "#e67e22"        # Laranja
COLOR_BTN_ACTION = "#3498db"    # Azul
COLOR_BTN_DANGER = "#e74c3c"    # Vermelho
COLOR_HEADER_TEXT = "#2c3e50"   # Texto Escuro

FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_SUBTITLE = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)

# --- FUNÇÕES GRÁFICAS ---

def embed_plot_on_frame(frame, fig):
    for widget in frame.winfo_children():
        widget.destroy()
    canvas = FigureCanvasTkAgg(fig, frame)
    widget = canvas.get_tk_widget()
    widget.pack(expand=True, fill="both")
    canvas.draw()
    return canvas

def grafico_distritos_bar(frame, distritos_pacientes):
    fig = plt.Figure(figsize=(6, 4), dpi=90)
    ax = fig.add_subplot(111)
    if distritos_pacientes:
        contagens = Counter(distritos_pacientes)
        dists = list(contagens.keys())
        vals = list(contagens.values())
        data_sorted = sorted(zip(dists, vals), key=lambda x: x[1], reverse=True)
        dists = [x[0] for x in data_sorted]
        vals = [x[1] for x in data_sorted]
        top = 10
        ax.bar(dists[:top], vals[:top], color=COLOR_BTN_ACTION, alpha=0.8)
        ax.set_title(f"Top {len(dists[:top])} Distritos", fontsize=10)
        ax.set_xticklabels(dists[:top], rotation=45, ha='right', fontsize=8)
    else:
        ax.text(0.5, 0.5, "Sem dados", ha='center')
    ax.set_ylabel("Pacientes")
    fig.tight_layout()
    return embed_plot_on_frame(frame, fig)

def grafico_tempo_espera_frame(frame, dados):
    fig = plt.Figure(figsize=(6, 4), dpi=90)
    ax = fig.add_subplot(111)
    if dados and np.sum(dados) > 0.01:
        ax.hist(dados, bins=15, color='#8e44ad', alpha=0.7, edgecolor='white')
        ax.set_xlim(left=0)
    else:
        ax.text(0.5, 0.5, "Aguardando dados...", ha='center')
    ax.set_title("Tempos de Espera")
    ax.set_xlabel("Minutos")
    fig.tight_layout()
    return embed_plot_on_frame(frame, fig)

def grafico_tempo_total_frame(frame, dados):
    fig = plt.Figure(figsize=(6, 4), dpi=90)
    ax = fig.add_subplot(111)
    if dados and np.sum(dados) > 0.01:
        ax.hist(dados, bins=15, color='#d35400', alpha=0.7, edgecolor='white')
        ax.set_xlim(left=0)
    else:
        ax.text(0.5, 0.5, "Aguardando dados...", ha='center')
    ax.set_title("Tempo Total na Clínica")
    ax.set_xlabel("Minutos")
    fig.tight_layout()
    return embed_plot_on_frame(frame, fig)

def grafico_ocupacao_frame(frame, dados):
    fig = plt.Figure(figsize=(6, 4), dpi=90)
    ax = fig.add_subplot(111)
    if dados:
        ax.plot(dados, color='#27ae60', linewidth=2)
        ax.set_ylim(0, 105)
        ax.grid(True, linestyle=':', alpha=0.5)
    ax.set_title("Taxa de Ocupação (%)")
    ax.set_xlabel("Tempo (min)")
    fig.tight_layout()
    return embed_plot_on_frame(frame, fig)

def grafico_fila_frame(frame, dados):
    fig = plt.Figure(figsize=(6, 4), dpi=90)
    ax = fig.add_subplot(111)
    if dados:
        ax.plot(dados, color='#c0392b', linewidth=2)
        ax.set_ylim(bottom=0)
        ax.grid(True, linestyle=':', alpha=0.5)
    ax.set_title("Tamanho da Fila")
    ax.set_xlabel("Tempo (min)")
    fig.tight_layout()
    return embed_plot_on_frame(frame, fig)

def grafico_fila_vs_taxa_frame(frame, taxas, medias):
    fig = plt.Figure(figsize=(6, 4), dpi=90)
    ax = fig.add_subplot(111)
    ax.plot(taxas, medias, marker='s', color='#2980b9', linewidth=2)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.set_title("Sensibilidade: Impacto da Taxa (λ)")
    ax.set_xlabel("Taxa de Chegada")
    ax.set_ylabel("Fila Média Estimada")
    fig.tight_layout()
    return embed_plot_on_frame(frame, fig)

def grafico_ocupacao_medicos_bar(frame, med_stats):
    fig = plt.Figure(figsize=(6, 4), dpi=90)
    ax = fig.add_subplot(111)
    keys = sorted(med_stats.keys())
    ids = []
    vals = []
    idx = 0
    while idx < len(keys):
        k = keys[idx]
        ids.append(f"M{k+1}\n{med_stats[k]['especialidade'][:3]}")
        vals.append(med_stats[k]['ocupacao_percent'])
        idx += 1
    ax.bar(ids, vals, color='#16a085', edgecolor='white')
    ax.set_ylim(0, 100)
    ax.set_title("Ocupação Individual")
    fig.tight_layout()
    return embed_plot_on_frame(frame, fig)

# --- CLASSE DA APLICAÇÃO ---

class App(tk.Tk):
    def __init__(self, initial_params):
        super().__init__()
        self.title("Sistema de Gestão Clínica - Simulação")
        self.geometry("1200x750")
        self.configure(bg=COLOR_MAIN_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.initial_params = initial_params
        self.dataset_file = initial_params.get("dataset_file", "pessoas.json")
        self.pacientes = []
        self.sim = None
        self.anim_after = None
        self.minuto_atual = 0
        self.comp_data = None
        self.doc_specs = {}
        self.curr_res_map = {} 
        
        num_docs_init = initial_params.get("num_doctors", 3)
        di = 0
        while di < num_docs_init:
            self.doc_specs[str(di)] = "clinica_geral"
            di += 1
            
        self._build_unique_ui()
        self._apply_config(initial_params)
        self.lbl_data.config(text="Status: Base de Dados Vazia")

    def _apply_config(self, cfg):
        self.ent_l.delete(0, tk.END)
        self.ent_l.insert(0, str(cfg["lambda_rate"]))
        self.ent_m.delete(0, tk.END)
        self.ent_m.insert(0, str(cfg["num_doctors"]))
        self.cmb_d.set(cfg["service_distribution"])
        self.ent_t.delete(0, tk.END)
        self.ent_t.insert(0, str(cfg["mean_service_time"]))
        self.ent_dur.delete(0, tk.END)
        self.ent_dur.insert(0, str(cfg["simulation_time"]))
        self.cmb_arr.set(cfg["arrival_pattern"])
        self._update_specs()

    def _build_unique_ui(self):
        # --- ESQUERDA ---
        left_panel = tk.Frame(self, bg=COLOR_MAIN_BG)
        left_panel.pack(side="left", fill="both", expand=True, padx=20, pady=20)
        
        lbl_dash = tk.Label(left_panel, text="DASHBOARD DE MONITORIZAÇÃO", font=FONT_TITLE, bg=COLOR_MAIN_BG, fg=COLOR_HEADER_TEXT)
        lbl_dash.pack(anchor="w", pady=(0, 10))

        canvas_frame = tk.Frame(left_panel, bg="white", bd=2, relief="groove")
        canvas_frame.pack(expand=True, fill="both")
        
        top_c_bar = tk.Frame(canvas_frame, bg="#ecf0f1", height=30)
        top_c_bar.pack(fill="x")
        tk.Label(top_c_bar, text=" VISUALIZAÇÃO EM TEMPO REAL", font=("Arial", 8, "bold"), bg="#ecf0f1", fg="#7f8c8d").pack(side="left", padx=5)
        
        self.lbl_pac = tk.Label(top_c_bar, text="Minuto: 000 | Fila: 00", font=("Consolas", 10, "bold"), bg="#ecf0f1", fg=COLOR_HEADER_TEXT)
        self.lbl_pac.pack(side="right", padx=10)

        self.canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=0)
        self.canvas.pack(expand=True, fill="both", padx=15, pady=15)
        
        log_frame = tk.Frame(left_panel, bg=COLOR_MAIN_BG, height=150)
        log_frame.pack(fill="x", pady=(15, 0))
        tk.Label(log_frame, text="Resultados da Última Execução:", font=FONT_SUBTITLE, bg=COLOR_MAIN_BG, fg=COLOR_HEADER_TEXT).pack(anchor="w")
        self.txt_res = tk.Text(log_frame, height=6, bg="white", font=FONT_MONO, relief="flat", bd=1, padx=10, pady=10)
        self.txt_res.pack(fill="both", expand=True)

        # --- DIREITA ---
        right_sidebar = tk.Frame(self, bg=COLOR_SIDEBAR_BG, width=350)
        right_sidebar.pack(side="right", fill="y")
        
        tk.Label(right_sidebar, text="PAINEL DE CONTROLE", font=FONT_SUBTITLE, bg=COLOR_SIDEBAR_BG, fg=COLOR_ACCENT).pack(pady=(25, 15))

        p_frame = tk.LabelFrame(right_sidebar, text="Configuração", font=("Segoe UI", 10, "bold"), bg=COLOR_SIDEBAR_BG, fg="white", bd=1, relief="solid", padx=15, pady=10)
        p_frame.pack(fill="x", padx=15, pady=5)

        def create_input(parent, label, row):
            tk.Label(parent, text=label, bg=COLOR_SIDEBAR_BG, fg=COLOR_SIDEBAR_FG).grid(row=row, column=0, sticky="w", pady=4)
            ent = tk.Entry(parent, width=10, bg="#34495e", fg="white", insertbackground="white", relief="flat")
            ent.grid(row=row, column=1, pady=4, padx=5)
            return ent

        self.ent_l = create_input(p_frame, "Taxa Chegada (λ):", 0)
        self.ent_m = create_input(p_frame, "Nº Médicos:", 1)
        self.ent_m.bind("<FocusOut>", self._update_specs)
        
        tk.Label(p_frame, text="Distribuição:", bg=COLOR_SIDEBAR_BG, fg=COLOR_SIDEBAR_FG).grid(row=2, column=0, sticky="w", pady=4)
        self.cmb_d = ttk.Combobox(p_frame, values=["exponential","normal","uniform"], width=8)
        self.cmb_d.grid(row=2, column=1, pady=4, padx=5)
        
        self.ent_t = create_input(p_frame, "Tempo Médio:", 3)
        self.ent_dur = create_input(p_frame, "Duração (min):", 4)
        
        tk.Label(p_frame, text="Chegada:", bg=COLOR_SIDEBAR_BG, fg=COLOR_SIDEBAR_FG).grid(row=5, column=0, sticky="w", pady=4)
        self.cmb_arr = ttk.Combobox(p_frame, values=["homogeneo","naohomogeneo"], width=8)
        self.cmb_arr.grid(row=5, column=1, pady=4, padx=5)

        btn_frame = tk.Frame(right_sidebar, bg=COLOR_SIDEBAR_BG)
        btn_frame.pack(fill="x", padx=15, pady=20)
        
        def mk_btn(txt, cmd, color):
            return tk.Button(btn_frame, text=txt, bg=color, fg="white", font=("Segoe UI", 9, "bold"), activebackground=color, activeforeground="white", relief="flat", command=cmd, pady=6, cursor="hand2")

        mk_btn("▶ INICIAR SIMULAÇÃO", self.start_sim, COLOR_BTN_ACTION).pack(fill="x", pady=5)
        mk_btn("⏹ PARAR", self.stop_anim, COLOR_BTN_DANGER).pack(fill="x", pady=5)
        
        tk.Frame(btn_frame, height=1, bg="white").pack(fill="x", pady=15)
        mk_btn("📊 ANALISAR GRÁFICOS", self.open_graphs, COLOR_ACCENT).pack(fill="x", pady=5)

        ext_frame = tk.Frame(right_sidebar, bg=COLOR_SIDEBAR_BG)
        ext_frame.pack(fill="x", padx=15, pady=10)
        sec_btn_style = {"bg": "#95a5a6", "fg": "white", "relief": "flat", "pady": 4}
        tk.Button(ext_frame, text="Gerir Especialidades", command=self.config_specs, **sec_btn_style).pack(fill="x", pady=3)
        tk.Button(ext_frame, text="Carregar Dataset (JSON)", command=self.load_json, **sec_btn_style).pack(fill="x", pady=3)
        tk.Button(ext_frame, text="Pesquisar Utente", command=self.open_search, **sec_btn_style).pack(fill="x", pady=3)

        self.lbl_data = tk.Label(right_sidebar, text="Dataset: ...", font=("Segoe UI", 8), bg=COLOR_SIDEBAR_BG, fg="#bdc3c7")
        self.lbl_data.pack(side="bottom", pady=10)

    def _update_specs(self, e=None):
        try:
            n = int(self.ent_m.get())
            new = {}
            i = 0
            while i < n:
                sid = str(i)
                new[sid] = self.doc_specs.get(sid, "clinica_geral")
                i += 1
            self.doc_specs = new
        except ValueError:
            print("Valor invalido")

    def config_specs(self):
        self._update_specs()
        win = tk.Toplevel(self)
        win.title("Especialidades Médicas")
        win.geometry("400x500")
        win.configure(bg=COLOR_MAIN_BG)
        specs = ["clinica_geral", "cardiologia", "pneumologia", "ortopedia", "endocrinologia", "geriatria", "otorrino"]
        self.combos = {}
        container = tk.Frame(win, bg=COLOR_MAIN_BG, padx=10, pady=10)
        container.pack(fill="both", expand=True)
        canv = tk.Canvas(container, bg=COLOR_MAIN_BG, highlightthickness=0)
        sb = tk.Scrollbar(container, orient="vertical", command=canv.yview)
        scroll_f = tk.Frame(canv, bg=COLOR_MAIN_BG)
        scroll_f.bind("<Configure>", lambda e: canv.configure(scrollregion=canv.bbox("all")))
        canv.create_window((0,0), window=scroll_f, anchor="nw")
        canv.configure(yscrollcommand=sb.set)
        canv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        try:
            total = int(self.ent_m.get())
            i = 0
            while i < total:
                rf = tk.Frame(scroll_f, bg=COLOR_MAIN_BG)
                rf.pack(fill="x", pady=3)
                tk.Label(rf, text=f"Médico {i+1}", width=10, anchor="w", bg=COLOR_MAIN_BG).pack(side="left")
                c = ttk.Combobox(rf, values=specs, state="readonly")
                c.set(self.doc_specs.get(str(i)))
                c.pack(side="left", padx=5)
                self.combos[str(i)] = c
                i += 1
            def save():
                keys = list(self.combos.keys())
                k = 0
                while k < len(keys):
                    key = keys[k]
                    self.doc_specs[key] = self.combos[key].get()
                    k += 1
                win.destroy()
                messagebox.showinfo("Sucesso", "Configuração salva.")
            tk.Button(win, text="Salvar Alterações", bg=COLOR_BTN_ACTION, fg="white", command=save, relief="flat", pady=5).pack(fill="x", padx=10, pady=10)
        except ValueError:
            messagebox.showerror("Erro", "Numero de medicos invalido")

    def load_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if f:
            p = carregar_pacientes_json(f)
            if p:
                self.pacientes = p
                self.dataset_file = f
                nome = os.path.basename(f)
                self.lbl_data.config(text=f"Dataset: {nome} ({len(p)})")
                messagebox.showinfo("Carregado", "Sucesso.")
            else:
                messagebox.showwarning("Erro", "Ficheiro invalido.")

    # --- FUNÇÃO DE PESQUISA (NOMES + TRIAGEM FIXA + CLEANER AGRESSIVO) ---
    def open_search(self):
        win = tk.Toplevel(self)
        win.title("Pesquisa de Utentes")
        win.geometry("900x600")
        win.configure(bg=COLOR_MAIN_BG)

        # --- FILTROS ---
        top_f = tk.Frame(win, bg="#ecf0f1", pady=15, padx=10, relief="groove", bd=1)
        top_f.pack(fill="x")

        lbl_style = {"bg": "#ecf0f1", "fg": "#2c3e50", "font": ("Segoe UI", 9, "bold")}
        
        tk.Label(top_f, text="Nome:", **lbl_style).pack(side="left", padx=5)
        en_nome = tk.Entry(top_f, width=15)
        en_nome.pack(side="left", padx=5)

        tk.Label(top_f, text="CC/BI:", **lbl_style).pack(side="left", padx=5)
        en_cc = tk.Entry(top_f, width=12)
        en_cc.pack(side="left", padx=5)
        
        tk.Label(top_f, text="Idade:", **lbl_style).pack(side="left", padx=5)
        en_idade = tk.Entry(top_f, width=5)
        en_idade.pack(side="left", padx=5)

        tk.Label(top_f, text="Sexo:", **lbl_style).pack(side="left", padx=5)
        cb_sx = ttk.Combobox(top_f, values=["", "Masculino", "Feminino", "Outro"], width=10, state="readonly")
        cb_sx.pack(side="left", padx=5)

        # --- TREEVIEW ---
        tree_frame = tk.Frame(win, bg=COLOR_MAIN_BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

        cols = ("cc", "nome", "idade", "sexo", "profissao")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        
        tree.heading("cc", text="CC/BI")
        tree.heading("nome", text="Nome Completo")
        tree.heading("idade", text="Idade")
        tree.heading("sexo", text="Sexo")
        tree.heading("profissao", text="Profissão")

        tree.column("cc", width=100, anchor="center")
        tree.column("nome", width=280, anchor="w")
        tree.column("idade", width=60, anchor="center")
        tree.column("sexo", width=80, anchor="center")
        tree.column("profissao", width=150, anchor="w")

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.curr_res_map = {} 

        # --- DETALHE DA FICHA (CLEANER AGRESSIVO) ---
        def ver_detalhe(evt):
            sel_id = tree.focus()
            if not sel_id: return
            
            p = self.curr_res_map.get(sel_id)
            if not p: return

            d_win = tk.Toplevel(win)
            d_win.title(f"Ficha: {p.nome}")
            d_win.geometry("500x550")
            d_win.configure(bg="white")

            header = tk.Frame(d_win, bg=COLOR_SIDEBAR_BG, height=60)
            header.pack(fill="x")
            tk.Label(header, text=p.nome.upper(), font=("Segoe UI", 14, "bold"), bg=COLOR_SIDEBAR_BG, fg="white").pack(pady=15)

            body = tk.Frame(d_win, bg="white", padx=20, pady=20)
            body.pack(fill="both", expand=True)

            def add_row(label, value, row_idx, val_color="#2c3e50"):
                tk.Label(body, text=label, font=("Segoe UI", 9, "bold"), bg="white", fg="#7f8c8d").grid(row=row_idx, column=0, sticky="w", pady=5)
                tk.Label(body, text=value, font=("Segoe UI", 10, "bold"), bg="white", fg=val_color).grid(row=row_idx, column=1, sticky="w", pady=5, padx=10)

            # --- DADOS PESSOAIS ---
            tk.Label(body, text="DADOS PESSOAIS", font=("Segoe UI", 8, "bold"), fg=COLOR_ACCENT, bg="white").grid(row=0, column=0, sticky="w", pady=(0, 10))
            
            add_row("CC/BI:", p.cc_bi, 1)
            add_row("Idade:", f"{p.idade} anos", 2)
            add_row("Sexo:", str(p.sexo).capitalize(), 3)
            add_row("Profissão:", p.profissao, 4)
            
            # --- RELIGIÃO ---
            rel = p.religiao if p.religiao else "Não especificado"
            cor_rel = "#2c3e50"
            if "Jeová" in rel or "jeová" in rel:
                cor_rel = COLOR_BTN_DANGER 
                rel += " (ALERTA: SANGUE)"
            add_row("Religião:", rel, 5, cor_rel)

            tk.Frame(body, height=1, bg="#ecf0f1").grid(row=6, column=0, columnspan=2, sticky="ew", pady=15)

            # --- TRIAGEM ---
            tk.Label(body, text="TRIAGEM E DIAGNÓSTICO", font=("Segoe UI", 8, "bold"), fg=COLOR_ACCENT, bg="white").grid(row=7, column=0, sticky="w", pady=(0, 10))
            
            rng = random.Random(str(p.cc_bi))
            
            doenca_show = "Virose"
            prio_show = "Normal"
            
            opcoes_sim = [
                "Gripe", "Virose", "Febre", "Checkup",    
                "Perna Partida", "Entorse", "Queda",      
                "Dor no Peito", "Arritmia", "Enfarte",    
                "Falta de Ar", "Asma",                    
                "Dor de Ouvidos", "Otite"                 
            ]

            raw_desc = str(p.descrição).lower() if p.descrição else ""
            
            lorem_words = [
                "nostrud", "ipsum", "magna", "aliquip", "amet", "dolore", "excepteur",
                "voluptate", "irure", "eiusmod", "laborum", "sint", "duis", "mollit", 
                "culpa", "velit", "anim", "id", "est", "consectetur", "adipiscing", "elit"
            ]
            
            is_lorem = any(w in raw_desc.split() for w in lorem_words)

            if is_lorem or not p.descrição:
                doenca_show = rng.choice(opcoes_sim)
            else:
                doenca_show = "Sob Observação"

            emergencias = ["Angina", "Enfarte", "Fratura", "Perna", "Arritmia", "Peito"]
            urgentes = ["Febre", "Dor", "Infeccao", "Asma", "Otite"]
            
            if any(e in doenca_show for e in emergencias): prio_show = "Urgente"
            elif any(u in doenca_show for u in urgentes): prio_show = "Moderada"
            
            pcor = "#27ae60"
            if prio_show == "Urgente": pcor = COLOR_BTN_DANGER
            elif prio_show == "Moderada": pcor = "#f39c12"

            add_row("Doença:", doenca_show, 8)
            add_row("Prioridade:", prio_show, 9, pcor)

            tk.Frame(body, height=1, bg="#ecf0f1").grid(row=10, column=0, columnspan=2, sticky="ew", pady=15)

            # --- NOTAS (COM GERADOR) ---
            tk.Label(body, text="OBSERVAÇÕES CLÍNICAS", font=("Segoe UI", 8, "bold"), fg=COLOR_ACCENT, bg="white").grid(row=11, column=0, sticky="w", pady=(0, 10))
            
            final_desc = p.descrição
            
            if is_lorem or not final_desc:
                mapa_sintomas = {
                    "Gripe": "Paciente apresenta febre alta (38.5ºC), dores musculares e tosse seca.",
                    "Virose": "Queixas de náuseas, vómitos e mal-estar geral há 2 dias.",
                    "Febre": "Temperatura corporal elevada sem outros sintomas aparentes.",
                    "Checkup": "Consulta de rotina para avaliação geral e renovação de receitas.",
                    "Perna Partida": "Traumatismo no membro inferior após queda. Dor intensa e edema visível.",
                    "Entorse": "Torção do tornozelo durante atividade física. Dificuldade em caminhar.",
                    "Queda": "Escoriações múltiplas após queda da própria altura.",
                    "Dor no Peito": "Sensação de aperto torácico irradiando para o braço esquerdo. Histórico de hipertensão.",
                    "Arritmia": "Palpitações e sensação de desmaio. Pulso irregular.",
                    "Enfarte": "Dor precordial intensa, sudorese fria e náuseas. EMERGÊNCIA.",
                    "Falta de Ar": "Dispneia aos pequenos esforços e sibilos audíveis.",
                    "Asma": "Crise asmática com dificuldade expiratória.",
                    "Dor de Ouvidos": "Otalgia direita intensa, agravada à noite.",
                    "Otite": "Inflamação do canal auditivo com secreção purulenta."
                }
                final_desc = mapa_sintomas.get(doenca_show, f"Paciente encaminhado para triagem devido a queixas de {doenca_show}.")
                final_desc += "\n(Obs: Descrição gerada automaticamente por falta de dados originais)."

            lbl_desc = tk.Label(body, text=final_desc, font=("Segoe UI", 9), bg="#f9f9f9", fg="#2c3e50", wraplength=400, justify="left", relief="flat", padx=10, pady=10)
            lbl_desc.grid(row=12, column=0, columnspan=2, sticky="w")
            
            tk.Button(d_win, text="FECHAR FICHA", bg=COLOR_BTN_DANGER, fg="white", relief="flat", command=d_win.destroy, pady=5).pack(fill="x", side="bottom", padx=20, pady=20)

        tree.bind("<Double-1>", ver_detalhe)

        # --- BUSCA ---
        def buscar():
            for item in tree.get_children():
                tree.delete(item)
            self.curr_res_map.clear()

            qn = en_nome.get().lower().strip()
            qc = en_cc.get().lower().strip()
            qs = cb_sx.get().lower()
            qi = en_idade.get().strip()

            count = 0
            for p in self.pacientes:
                match = True
                if qn:
                    name_parts = str(p.nome).lower().split()
                    if not any(part.startswith(qn) for part in name_parts):
                        match = False
                
                if match and qc and qc not in str(p.cc_bi).lower(): match = False
                if match and qi:
                    if str(p.idade) != qi: match = False
                if match and qs:
                    p_sex = str(p.sexo).lower()
                    if qs == "outro":
                        if p_sex in ["masculino", "feminino"]: match = False
                    else:
                        if p_sex != qs: match = False
                
                if match:
                    sexo_fmt = str(p.sexo).capitalize() if p.sexo else "N/A"
                    row_id = tree.insert("", "end", values=(p.cc_bi, p.nome, p.idade, sexo_fmt, p.profissao))
                    self.curr_res_map[row_id] = p
                    count += 1
            
            if count == 0:
                messagebox.showinfo("Pesquisa", "Nenhum utente encontrado.")

        btn = tk.Button(top_f, text="🔍 PESQUISAR", bg=COLOR_BTN_ACTION, fg="white", font=("Segoe UI", 9, "bold"), command=buscar, relief="flat", padx=15, pady=2)
        btn.pack(side="left", padx=20)

    def start_sim(self):
        try:
            if not self.pacientes:
                messagebox.showwarning("Aviso", "Carregue o dataset primeiro.")
                return
            
            self.comp_data = None 
            
            self._update_specs()
            self.sim = SimulacaoClinica(
                lambda_rate=float(self.ent_l.get()),
                num_doctors=int(self.ent_m.get()),
                service_distribution=self.cmb_d.get(),
                mean_service_time=float(self.ent_t.get()),
                simulation_time=int(self.ent_dur.get()),
                arrival_pattern=self.cmb_arr.get(),
                pacientes=self.pacientes,
                doctor_specialties=self.doc_specs
            )
            threading.Thread(target=self._run_bg, daemon=True).start()
            self.minuto_atual = 0
            self.canvas.delete("all")
            self.after(200, self.anim)
        except ValueError:
            messagebox.showerror("Erro", "Valores numéricos inválidos.")
    
    
    def _run_bg(self):
        self.sim.run()
        st = calcular_estatisticas(self.sim)
        
        # --- ALTERAÇÃO AQUI: Adicionar as estatísticas em falta ---
        t = "RELATÓRIO DE SIMULAÇÃO\n" + "="*30 + "\n"
        t += f"Utentes Atendidos:     {st['doentes_atendidos']}\n"
        t += f"Ocupação Média Médicos: {st['ocupacao_media_medicos']:.1f}%\n"
        t += "-"*30 + "\n"
        t += f"Tempo Médio Espera:    {st['tempo_medio_espera']:.1f} min\n"
        t += f"Tempo Médio Consulta:  {st['tempo_medio_consulta']:.1f} min\n"
        t += f"Tempo Médio na Clínica:{st['tempo_medio_na_clinica']:.1f} min\n"
        t += "-"*30 + "\n"
        t += f"Fila de Espera (Média): {st['fila_media']:.1f}\n"
        t += f"Fila de Espera (Máx):   {st['fila_max']}\n"
        
        t += "="*30 + "\nDETALHE POR MÉDICO:\n"
        ks = sorted(st['stats_por_medico'].keys())
        kidx = 0
        while kidx < len(ks):
            k = ks[kidx]
            d = st['stats_por_medico'][k]
            # Mostra ID, Especialidade abreviada e % de ocupação
            t += f"M{k+1} [{d['especialidade'][:4].upper()}]: {d['ocupacao_percent']:.1f}% (Atend: {d['num_atendidos']})\n"
            kidx += 1
            
        # Atualiza a caixa de texto na Interface
        self.txt_res.delete("1.0", tk.END)
        self.txt_res.insert("1.0", t)

    def anim(self):
        if not self.sim: return
        try: fs = self.sim.fila_sizes
        except: fs = []
        if not fs: return
        if self.minuto_atual >= len(fs):
            self.lbl_pac.config(text="FIM DA SIMULAÇÃO")
            self.stop_anim()
            return
        self.canvas.delete("all")
        fila = fs[self.minuto_atual]
        
        h_total = 300
        h_fill = min(h_total, fila * 5)
        self.canvas.create_rectangle(30, 50, 60, 50+h_total, fill="#ecf0f1", outline="#bdc3c7")
        self.canvas.create_rectangle(30, 50+(h_total-h_fill), 60, 50+h_total, fill="#e74c3c", outline="")
        self.canvas.create_text(45, 40, text="FILA", font=("Arial", 8, "bold"))
        self.canvas.create_text(45, 50+h_total+15, text=str(fila), font=("Arial", 10, "bold"), fill="#e74c3c")
        
        on_docs = {}
        evs = self.sim.eventos
        ei = 0
        while ei < len(evs):
            ev = evs[ei]
            ini = ev['minuto_inicio']
            dur = ev['duracao']
            if (ini <= self.minuto_atual) and (self.minuto_atual < ini + dur):
                on_docs[ev['medico']] = ev
            ei += 1
            
        start_x = 100
        start_y = 50
        d_idx = 0
        while d_idx < self.sim.num_doctors:
            col = d_idx % 2
            row = d_idx // 2
            x = start_x + col * 260
            y = start_y + row * 90
            info = on_docs.get(d_idx)
            spec = self.doc_specs.get(str(d_idx), "Geral")
            if info:
                bg_room = "#d5f5e3"
                border = "#27ae60"
                cor_status = "#27ae60"
                
                # --- CORREÇÃO FINAL: NOME EM CIMA, DOENÇA EM BAIXO, SEM PARÊNTESES ---
                pac_txt = "--"
                if 'motivo' in info:
                    primeiro_nome = info['paciente'].split()[0]
                    doenca_txt = str(info['motivo']).upper()
                    pac_txt = f"{primeiro_nome}\n{doenca_txt}"
                
                txt_status = "OCUPADO"
            else:
                bg_room = "white"
                border = "#bdc3c7"
                txt_status = "LIVRE"
                cor_status = "#95a5a6"
                pac_txt = "--"
            
            self.canvas.create_rectangle(x, y, x+240, y+80, fill=bg_room, outline=border, width=2)
            self.canvas.create_line(x+240, y+20, x+240, y+60, fill="white", width=4) 
            self.canvas.create_text(x+10, y+15, text=f"GABINETE {d_idx+1}", font=("Arial", 8, "bold"), anchor="w", fill="#2c3e50")
            self.canvas.create_text(x+230, y+15, text=spec.upper(), font=("Arial", 7), anchor="e", fill="#7f8c8d")
            
            # Ajuste de posição para caber as 2 linhas
            self.canvas.create_text(x+10, y+45, text=pac_txt, font=("Segoe UI", 9, "bold"), anchor="w", fill="#2c3e50")
            
            self.canvas.create_text(x+10, y+68, text=txt_status, font=("Arial", 7, "bold"), anchor="w", fill=cor_status)
            d_idx += 1
        self.lbl_pac.config(text=f"Minuto: {self.minuto_atual} | Fila: {fila}")
        self.minuto_atual += 1
        self.anim_after = self.after(50, self.anim)

    def stop_anim(self):
        if self.anim_after:
            self.after_cancel(self.anim_after)
            self.anim_after = None

    def open_graphs(self):
        if not self.sim or not self.sim.pacientes:
            messagebox.showinfo("Info", "Execute a simulação primeiro.")
            return
            
        win = tk.Toplevel(self)
        win.title("Análise Estatística")
        win.geometry("900x650")
        
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        
        tab_bg = "white"
        
        t1 = tk.Frame(nb, bg=tab_bg); nb.add(t1, text="Filas")
        grafico_fila_frame(t1, self.sim.fila_sizes)
        
        t2 = tk.Frame(nb, bg=tab_bg); nb.add(t2, text="Ocupação")
        grafico_ocupacao_frame(t2, self.sim.ocupacao_medicos)
        
        t3 = tk.Frame(nb, bg=tab_bg); nb.add(t3, text="Demografia")
        grafico_distritos_bar(t3, self.sim.distritos_pacientes)
        
        t4 = tk.Frame(nb, bg=tab_bg); nb.add(t4, text="Produtividade")
        grafico_ocupacao_medicos_bar(t4, self.sim.stats_por_medico)
        
        t5 = tk.Frame(nb, bg=tab_bg); nb.add(t5, text="Sensibilidade")
        
        container_plot = tk.Frame(t5, bg=tab_bg)
        container_plot.pack(fill="both", expand=True)
        
        btn_recalc = tk.Button(t5, text="Calcular Impacto (Atualizar Gráfico)", 
                               command=lambda: self.run_comp(win),
                               bg=COLOR_BTN_ACTION, fg="white", font=FONT_SUBTITLE, relief="flat")
        btn_recalc.pack(pady=10, side="bottom")

        if self.comp_data:
            grafico_fila_vs_taxa_frame(container_plot, *self.comp_data)
        else:
            tk.Label(container_plot, text="Clique abaixo para gerar a análise.\nIsto simula múltiplos cenários com os parâmetros atuais.", 
                     bg=tab_bg, font=FONT_SUBTITLE).pack(expand=True)

    def run_comp(self, win):
        win.destroy()
        rates = range(10, 31, 5)
        avgs = []
        r_list = list(rates)
        idx = 0
        
        self._update_specs()
        
        try:
            sim_docs = int(self.ent_m.get())
            if sim_docs <= 0: sim_docs = 3
        except:
            sim_docs = 3
            
        sim_time = 800
        
        while idx < len(r_list):
            r = r_list[idx]
            s = SimulacaoClinica(
                lambda_rate=r, num_doctors=sim_docs, service_distribution="exponential",
                mean_service_time=float(self.ent_t.get()), simulation_time=sim_time, 
                pacientes=self.pacientes, arrival_pattern="homogeneo", 
                doctor_specialties=self.doc_specs
            )
            s.run()
            v = 0
            if s.fila_sizes: v = np.mean(s.fila_sizes)
            avgs.append(v)
            idx += 1
            
        self.comp_data = (r_list, avgs)
        self.open_graphs()

    def _on_close(self):
        self.stop_anim()
        self.destroy()