import os
import json
import random
import numpy as np
import heapq
import itertools
import math
from typing import List, Dict, Any, Optional, Tuple

# --- CONSTANTES GLOBAIS ---
FALLBACK_ESP = "clinica_geral"
CHEGADA = "CHEGADA"
SAIDA = "SAIDA"

DOENCA_TO_ESP = {
    "asma": "pneumologia", "bronquite": "pneumologia", "covid": "pneumologia", "falta de ar": "pneumologia",
    "diabetes": "endocrinologia", "obesidade": "endocrinologia", 
    "angina": "cardiologia", "arritmia": "cardiologia", "hipertensão": "cardiologia", "dor no peito": "cardiologia", "enfarte": "cardiologia",
    "fractura": "ortopedia", "fratura": "ortopedia", "queda": "ortopedia", "luxacao": "ortopedia", "entorse": "ortopedia", "perna partida": "ortopedia",
    "otite": "otorrino", "rinite": "otorrino", "sinusite": "otorrino", "dor de ouvidos": "otorrino",
    "geriatria_cronica": "geriatria", "demencia": "geriatria",
    "febre": "clinica_geral", "virose": "clinica_geral", "gripe": "clinica_geral", "dor de cabeça": "clinica_geral", "checkup": "clinica_geral"
}

class Paciente:
    def __init__(self, id: str, cc_bi: str, nome: str, idade: Optional[int] = None,
                 profissao: Optional[str] = None, prioridade: str = "normal", **kwargs):
        self.id = id           
        self.cc_bi = cc_bi     
        self.nome = nome
        self.idade = idade
        self.profissao = profissao
        self.prioridade = "normal" 
        self.sexo = kwargs.get('sexo')
        self.morada = kwargs.get('morada', {}) 
        self.descrição = kwargs.get('descrição')
        self.atributos = kwargs.get('atributos')
        self.religiao = kwargs.get('religiao')
        self.desportos = kwargs.get('desportos')
        
    def __repr__(self):
        return f"{self.nome} ({self.prioridade})"

def carregar_pacientes_json(ficheiro: str, limite: Optional[int] = None) -> List[Paciente]:
    if not os.path.exists(ficheiro):
        return []

    data = None
    try:
        with open(ficheiro, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Erro ao ler {ficheiro}: {e}")
        return []
    
    if data is None: return []

    pacientes = []
    i = 0
    while i < len(data):
        p = data[i]
        profissao = str(p.get("profissao", "")).lower()
        is_doctor = "médico" in profissao or "medicina" in profissao
        
        internal_id = p.get("id", f"p{i}")
        real_doc_id = p.get("CC") or p.get("BI") or p.get("cc") or "N/A"
        
        # Carrega a descrição crua (mesmo com latim) para a ficha, 
        # mas a simulação vai ignorá-la se for lixo.
        raw_desc = p.get('descrição')
        
        if not is_doctor:
            pacientes.append(Paciente(
                id=str(internal_id),
                cc_bi=str(real_doc_id),
                nome=p.get("nome", f"Pessoa {i+1}"),
                idade=p.get("idade"),
                profissao=p.get("profissao"),
                prioridade="normal", 
                sexo=p.get('sexo'),
                morada=p.get('morada'),
                descrição=raw_desc,
                atributos=p.get('atributos', {}),
                religiao=p.get('religiao'),
                desportos=p.get('desportos')
            ))
        i += 1

    random.shuffle(pacientes)
    if limite is not None:
        pacientes = pacientes[:limite]
    return pacientes

def gera_intervalo_tempo_chegada(taxa, rng: Optional[np.random.Generator] = None):
    val = float('inf')
    if taxa > 0:
        taxa_por_minuto = taxa / 60.0
        val = float(rng.exponential(1.0 / taxa_por_minuto)) if rng else float(np.random.exponential(1.0 / taxa_por_minuto))
    return val

def gera_tempo_consulta(media, distribuicao="exponential", rng: Optional[np.random.Generator] = None):
    val = 0.0
    if distribuicao in ("exponential", "exponencial"):
        val = float(rng.exponential(scale=media)) if rng else float(np.random.exponential(scale=media))
    elif distribuicao == "normal":
        val = float(rng.normal(loc=media, scale=0.2 * media)) if rng else float(np.random.normal(loc=media, scale=0.2 * media))
        val = max(0.1, val)
    elif distribuicao in ("uniform", "uniforme"):
        val = float(rng.uniform(low=0.5 * media, high=1.5 * media)) if rng else float(np.random.uniform(low=0.5 * media, high=1.5 * media))
    else: 
        val = float(rng.exponential(scale=media)) if rng else float(np.random.exponential(scale=media))
    return val

def calcular_estatisticas(sim) -> dict:
    ii = 0
    while ii < len(sim._medicos):
        m = sim._medicos[ii]
        tempos = m.get("tempos_consulta", []) or []
        num_att = m.get("num_atendidos", 0)
        total_ocup_individual = sum(tempos)
        
        media_cons = float(np.mean(tempos)) if len(tempos) > 0 else 0.0
        div = max(1.0, float(sim.simulation_time))
        ocup_percent = 100.0 * total_ocup_individual / div
        if ocup_percent > 100.0: ocup_percent = 100.0
        
        sim.stats_por_medico[ii] = {
            "id": m.get("id"), "especialidade": m.get("especialidade"),
            "num_atendidos": num_att,
            "ocupacao_percent": ocup_percent, "media_consulta": media_cons
        }
        ii += 1

    tempos_esp_arr = np.array(sim.tempos_espera) if len(sim.tempos_espera) > 0 else np.array([0.0])
    tempos_cons_arr = np.array(sim.tempos_consulta) if len(sim.tempos_consulta) > 0 else np.array([0.0])
    fila_arr = np.array(sim.fila_sizes) if len(sim.fila_sizes) > 0 else np.array([0])
    
    t_line = sim.slots_ocupados[:sim.simulation_time]
    t_line = np.minimum(t_line, sim.num_doctors) 
    media_medicos_ocupados = np.mean(t_line)
    ocupacao_media_global_pct = (media_medicos_ocupados / max(1, sim.num_doctors)) * 100.0
    if ocupacao_media_global_pct > 100.0: ocupacao_media_global_pct = 100.0

    sim.stats_geral = {
        "tempo_medio_espera": float(np.mean(tempos_esp_arr)),
        "tempo_medio_consulta": float(np.mean(tempos_cons_arr)),
        "fila_media": float(np.mean(fila_arr)),
        "fila_max": int(np.max(fila_arr)) if fila_arr.size > 0 else 0,
        "ocupacao_media_medicos": ocupacao_media_global_pct,
        "doentes_atendidos": int(sim.doentes_atendidos)
    }
    
    t_medio_clinica = float(np.mean(sim.tempos_clinica)) if sim.tempos_clinica else 0.0

    return {
        "tempo_medio_espera": sim.stats_geral["tempo_medio_espera"],
        "variancia_tempo_espera": float(np.var(tempos_esp_arr)) if len(tempos_esp_arr)>1 else 0.0,
        "tempo_medio_consulta": sim.stats_geral["tempo_medio_consulta"],
        "variancia_tempo_consulta": float(np.var(tempos_cons_arr)) if len(tempos_cons_arr)>1 else 0.0,
        "tempo_medio_na_clinica": t_medio_clinica,
        "fila_media": sim.stats_geral["fila_media"],
        "fila_max": sim.stats_geral["fila_max"],
        "ocupacao_media_medicos": sim.stats_geral["ocupacao_media_medicos"],
        "doentes_atendidos": sim.stats_geral["doentes_atendidos"],
        "stats_por_medico": sim.stats_por_medico 
    }

class SimulacaoClinica:
    def __init__(self, **kwargs):
        self.lambda_rate = float(kwargs.get('lambda_rate', 10))
        self.num_doctors = int(kwargs.get('num_doctors', 3))
        self.service_distribution = kwargs.get('service_distribution', "exponential")
        self.mean_service_time = float(kwargs.get('mean_service_time', 15))
        self.simulation_time = int(kwargs.get('simulation_time', 480))
        self.seed = kwargs.get('seed')
        self.arrival_pattern = kwargs.get('arrival_pattern', "homogeneous")
        self.arrival_profile = kwargs.get('arrival_profile')
        self.pacientes: List[Paciente] = kwargs.get('pacientes', [])
        self.doctor_specialties = kwargs.get('doctor_specialties', {})
        self.reset()

    def reset(self):
        self.tempos_espera = []; self.tempos_consulta = []; self.tempos_clinica = []
        self.fila_sizes = []; self.ocupacao_medicos = [] 
        self.eventos = []; self.distritos_pacientes = []
        self.doentes_atendidos = 0
        self.stats_por_medico = {}; self.stats_geral = {}
        self._rng = np.random.default_rng(self.seed)
        self._heap = []
        self._counter = itertools.count()
        self._chegada = {}; self._inicio = {}; self._saida = {}; self._duracao = {}
        self._pid_to_pidx = {} 
        self._paciente_medico = {} 
        self.slots_ocupados = np.zeros(self.simulation_time + 500)
        self._medicos = []
        i = 0
        while i < self.num_doctors:
            esp = self.doctor_specialties.get(str(i), FALLBACK_ESP)
            self._medicos.append({
                "id": i, "livre": True, "fim": 0.0, "especialidade": esp, 
                "last_event_time": 0.0, "num_atendidos": 0, "tempos_consulta": []
            })
            i += 1
        self._filas = {} 
        self._pid_counter = 1
        
    def _gera_intervalo_chegada_homogeneo(self) -> float:
        val = float('inf')
        if self.pacientes: 
            val = gera_intervalo_tempo_chegada(self.lambda_rate, rng=self._rng)
        return val

    def _gera_chegadas_nonhomogeneous(self):
        if self.pacientes: 
            profile = self.arrival_profile
            if profile is None:
                profile = [(0, 120, 5.0), (120, 300, 15.0), (300, 420, 25.0), (420, self.simulation_time, 10.0)]
            pid_ctr = self._pid_counter; pidx = 0; idx_bloco = 0
            while idx_bloco < len(profile):
                bloco = profile[idx_bloco]; start_min, end_min, lam = bloco
                if (end_min > start_min) and (lam > 0):
                    t = float(start_min); taxa_min = lam / 60.0
                    while (t < end_min) and (pidx < len(self.pacientes)):
                        intervalo = float(self._rng.exponential(1.0 / taxa_min)); t += intervalo
                        if (t < end_min) and (pidx < len(self.pacientes)):
                            pid = f"p{pid_ctr}"; pid_ctr += 1
                            self._chegada[pid] = t; heapq.heappush(self._heap, (t, next(self._counter), CHEGADA, pid))
                            self._pid_to_pidx[pid] = pidx; pidx += 1
                idx_bloco += 1
            self._pid_counter = pid_ctr

    def _gera_chegadas_homogeneo(self):
        if self.pacientes: 
            t = float(self._gera_intervalo_chegada_homogeneo()); pid_ctr = self._pid_counter; pidx = 0
            while (t < self.simulation_time) and (pidx < len(self.pacientes)):
                pid = f"p{pid_ctr}"; pid_ctr += 1
                self._chegada[pid] = t; heapq.heappush(self._heap, (t, next(self._counter), CHEGADA, pid))
                self._pid_to_pidx[pid] = pidx; pidx += 1
                t += float(self._gera_intervalo_chegada_homogeneo())
            self._pid_counter = pid_ctr

    # --- CORREÇÃO ABSOLUTA PARA O LATIM ---
    def _detectar_doenca_e_prioridade(self, p: Dict[str, Any]) -> Tuple[str, str, str]:
        doenca_raw = ""
        if isinstance(p, dict):
            val = p.get("doenca")
            if not val:
                val = p.get("descrição")
            if isinstance(val, str) and val != "":
                doenca_raw = val.lower()

        # AQUI ESTÁ O FILTRO FORTE:
        # 1. Se for vazio
        # 2. OU se tiver mais de 25 caracteres (Latim é longo)
        # 3. OU se tiver palavras proibidas
        is_bad = False
        if not doenca_raw: is_bad = True
        elif len(doenca_raw) > 25: is_bad = True # Corta frases longas em Latim
        else:
            lorem = ["nostrud", "ipsum", "magna", "amet"]
            if any(x in doenca_raw for x in lorem): is_bad = True

        if is_bad or doenca_raw == "virose":
            opcoes = [
                "gripe", "virose", "febre", "checkup",    
                "perna partida", "entorse", "queda",      
                "dor no peito", "arritmia", "enfarte",    
                "falta de ar", "asma",                    
                "dor de ouvidos", "otite"                 
            ]
            doenca_raw = random.choice(opcoes)

        emergencias = ["angina", "enfarte", "fratura", "fractura", "sufocamento", "queimadura", "acidente", "peito", "arritmia"]
        urgentes = ["febre", "dor", "cólica", "infecção", "covid", "gripe", "asma", "ar", "otite"]
        
        prioridade = "normal" 
        found_emergency = False
        i = 0
        while i < len(emergencias) and not found_emergency:
            if emergencias[i] in doenca_raw.lower():
                prioridade = "urgente"; found_emergency = True
            i += 1
            
        if not found_emergency:
            found_urgent = False
            j = 0
            while j < len(urgentes) and not found_urgent:
                if urgentes[j] in doenca_raw.lower():
                    prioridade = "moderada"; found_urgent = True
                j += 1

        visualizacao_str = doenca_raw.capitalize() 
        return doenca_raw, prioridade, visualizacao_str

    def _doenca_para_especialidade(self, doenca: str) -> str:
        d = doenca.lower()
        if d in DOENCA_TO_ESP: return DOENCA_TO_ESP[d]
        for k, v in DOENCA_TO_ESP.items():
            if k in d: return v
        if "cardio" in d: return "cardiologia"
        if "ortop" in d: return "ortopedia"
        return FALLBACK_ESP
        
    def _registar_ocupacao_timeline(self, minuto_inicio, duracao):
        start = int(minuto_inicio)
        end = min(start + int(math.ceil(duracao)), self.simulation_time)
        if end > start: self.slots_ocupados[start:end] += 1
    
    def run(self):
        self.reset()
        if not self.pacientes: return
        if self.arrival_pattern == "nao homogeneo": self._gera_chegadas_nonhomogeneous()
        else: self._gera_chegadas_homogeneo()
        self._filas[FALLBACK_ESP] = [] 

        while self._heap:
            tempo, _, tipo, pid = heapq.heappop(self._heap)
            
            if tipo == CHEGADA:
                pidx = self._pid_to_pidx.get(pid)
                if pidx is not None and pidx < len(self.pacientes):
                    pdata = self.pacientes[pidx]
                    # Garante que conseguimos ler os dados (seja objeto ou dicionário)
                    p_info = pdata.__dict__ if not isinstance(pdata, dict) else pdata
                    
                    doenca, prio, motivo = self._detectar_doenca_e_prioridade(p_info)

                    # --- ALTERAÇÃO 1: Guardar a prioridade calculada no paciente ---
                    if isinstance(pdata, dict):
                        pdata['prioridade'] = prio
                    else:
                        pdata.prioridade = prio
                    # ---------------------------------------------------------------
                    
                    esp_req = self._doenca_para_especialidade(doenca)
                    
                    # Tratamento seguro da morada
                    try:
                        if isinstance(pdata, dict):
                            morada = pdata.get('morada', {}).get('distrito', "Desconhecido")
                        else:
                            morada = pdata.morada.get('distrito') if pdata.morada else "Desconhecido"
                    except:
                        morada = "Desconhecido"

                    if morada: self.distritos_pacientes.append(morada)
                    
                    if esp_req not in self._filas: self._filas[esp_req] = []

                    medico_idx = None; found = False
                    
                    # 1. TENTA ESPECIALISTA
                    j = 0
                    while j < self.num_doctors and not found:
                        m = self._medicos[j]
                        if m["livre"] and (m["especialidade"] == esp_req):
                            medico_idx = j; found = True
                        j += 1
                    
                    # 2. TENTA CLÍNICA GERAL (REDE DE SEGURANÇA)
                    if not found:
                        k = 0
                        while k < self.num_doctors and not found:
                            m = self._medicos[k]
                            if m["livre"] and (m["especialidade"] == FALLBACK_ESP):
                                medico_idx = k; found = True
                            k += 1
                    
                    if medico_idx is not None:
                        dur = gera_tempo_consulta(self.mean_service_time, self.service_distribution, self._rng)
                        self._inicio[pid] = tempo; self._duracao[pid] = dur
                        self._medicos[medico_idx]["livre"] = False
                        self._medicos[medico_idx]["num_atendidos"] += 1
                        self._medicos[medico_idx]["tempos_consulta"].append(dur)
                        self._paciente_medico[pid] = medico_idx 
                        self._registar_ocupacao_timeline(tempo, dur)
                        heapq.heappush(self._heap, (tempo + dur, next(self._counter), SAIDA, pid))
                        self.eventos.append({"minuto_inicio": int(tempo), "duracao": dur, "medico": medico_idx, "paciente": pdata.nome, "especialidade": esp_req, "motivo": motivo})
                    else:
                        # --- ALTERAÇÃO 2: COLOCAR NA FILA E ORDENAR POR PRIORIDADE ---
                        self._filas[esp_req].append(pid)

                        # Mapa: Urgente(0) > Moderada(1) > Normal(2)
                        mapa_val = {"urgente": 0, "moderada": 1, "normal": 2}

                        # Função auxiliar para ler a prioridade do paciente pelo ID
                        def get_prio_val(p_id):
                            idx = self._pid_to_pidx[p_id]
                            pat = self.pacientes[idx]
                            # Lê prioridade de forma segura (funciona para dict ou classe)
                            p_val = pat.get('prioridade', 'normal') if isinstance(pat, dict) else getattr(pat, 'prioridade', 'normal')
                            return mapa_val.get(p_val, 2)

                        # O sort do Python é 'estável': mantém a ordem de chegada para prioridades iguais
                        self._filas[esp_req].sort(key=get_prio_val)
                        # -------------------------------------------------------------

                        self.eventos.append({"minuto_inicio": int(tempo), "duracao": 0, "medico": None, "paciente": pdata.nome, "especialidade": esp_req, "motivo": motivo})

            elif tipo == SAIDA:
                found_idx = self._paciente_medico.get(pid)
                self._saida[pid] = tempo; self.doentes_atendidos += 1
                
                if found_idx is not None:
                    self._medicos[found_idx]["livre"] = True
                    esp_med = self._medicos[found_idx]["especialidade"]
                    prox_pid = None
                    
                    # 1. Médico verifica a SUA fila (Como já está ordenada, o pop(0) tira o mais urgente)
                    if esp_med in self._filas and self._filas[esp_med]: 
                        prox_pid = self._filas[esp_med].pop(0)
                    
                    # 2. Se for Clínica Geral, ajuda nas outras filas se estiver livre
                    elif esp_med == FALLBACK_ESP:
                        if FALLBACK_ESP in self._filas and self._filas[FALLBACK_ESP]:
                            prox_pid = self._filas[FALLBACK_ESP].pop(0)
                        else:
                            all_queues = list(self._filas.keys())
                            q_idx = 0
                            while q_idx < len(all_queues) and not prox_pid:
                                k = all_queues[q_idx]
                                if self._filas[k]: prox_pid = self._filas[k].pop(0)
                                q_idx += 1

                    if prox_pid:
                        pidx2 = self._pid_to_pidx.get(prox_pid); pdata2 = self.pacientes[pidx2]
                        # Re-detectar motivo para registo correto
                        p_info2 = pdata2.__dict__ if not isinstance(pdata2, dict) else pdata2
                        doenca2, _, motivo2 = self._detectar_doenca_e_prioridade(p_info2)
                        
                        esp2 = self._doenca_para_especialidade(doenca2)
                        
                        dur2 = gera_tempo_consulta(self.mean_service_time, self.service_distribution, self._rng)
                        self._inicio[prox_pid] = tempo; self._duracao[prox_pid] = dur2
                        self._medicos[found_idx]["livre"] = False
                        self._medicos[found_idx]["num_atendidos"] += 1
                        self._medicos[found_idx]["tempos_consulta"].append(dur2)
                        self._paciente_medico[prox_pid] = found_idx
                        self._registar_ocupacao_timeline(tempo, dur2)
                        heapq.heappush(self._heap, (tempo + dur2, next(self._counter), SAIDA, prox_pid))
                        self.eventos.append({"minuto_inicio": int(tempo), "duracao": dur2, "medico": found_idx, "paciente": pdata2.nome, "especialidade": esp2, "motivo": motivo2})

        minuto = 0
        while minuto < self.simulation_time:
            chegada_c = 0; inicio_c = 0
            for pk, tc in self._chegada.items():
                if tc <= minuto:
                    chegada_c += 1
                    ti = self._inicio.get(pk)
                    if ti is not None and ti <= minuto: inicio_c += 1
            f_size = max(0, chegada_c - inicio_c)
            self.fila_sizes.append(f_size)
            
            n_ocupados = min(self.slots_ocupados[minuto], self.num_doctors)
            pct = (n_ocupados / max(1, self.num_doctors)) * 100.0
            self.ocupacao_medicos.append(pct)
            minuto += 1

        for pid, tini in self._inicio.items():
            tch = self._chegada.get(pid); dur = self._duracao.get(pid)
            if tch and dur:
                self.tempos_espera.append(tini - tch)
                self.tempos_consulta.append(dur)
                tsai = self._saida.get(pid)
                if tsai: self.tempos_clinica.append(tsai - tch)
                else: self.tempos_clinica.append((tini - tch) + dur)

        calcular_estatisticas(self)   
    