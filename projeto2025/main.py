import argparse
import json
import os
from interface import App

CONFIG_FILE = "config.json"

def load_initial_config():
    config = {
        "lambda_rate": 10.0, 
        "num_doctors": 3, 
        "service_distribution": "exponential",
        "mean_service_time": 15.0, 
        "simulation_time": 120, 
        "arrival_pattern": "homogeneous",
        "dataset_file": "pessoas.json",
        "doctor_specialties": {} 
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                json_config = json.load(f)
                config.update({k: (float(v) if isinstance(config.get(k), float) else v) for k, v in json_config.items()})
            print(f"Configuracoes carregadas de {CONFIG_FILE}.")
        except Exception as e:
            print(f"Erro ao carregar {CONFIG_FILE}: {e}. Usando valores padrao.")
    else:
        print(f"Ficheiro {CONFIG_FILE} nao encontrado. Usando valores padrao.")
        
    return config

def parse_cli_arguments(config):
    parser = argparse.ArgumentParser(description="Simulacao de Clinica Medica.")
    parser.add_argument('--lambda_rate', type=float, help='Taxa de chegada de pacientes por hora (lambda).')
    parser.add_argument('--num_doctors', type=int, help='Numero de medicos disponiveis.')
    parser.add_argument('--service_distribution', type=str, help='Distribuicao do tempo de consulta.')
    parser.add_argument('--mean_service_time', type=float, help='Tempo medio de servico (minutos).')
    parser.add_argument('--simulation_time', type=int, help='Duracao total da simulacao (minutos).')
    parser.add_argument('--arrival_pattern', type=str, help='Padrao de chegada (homogeneous ou nonhomogeneous).')
    parser.add_argument('--dataset_file', type=str, help='Caminho para o ficheiro JSON de pacientes.')

    args, unknown = parser.parse_known_args() 

    final_config = config.copy()
    if args.lambda_rate is not None: final_config['lambda_rate'] = args.lambda_rate
    if args.num_doctors is not None: final_config['num_doctors'] = args.num_doctors
    if args.service_distribution is not None: final_config['service_distribution'] = args.service_distribution
    if args.mean_service_time is not None: final_config['mean_service_time'] = args.mean_service_time
    if args.simulation_time is not None: final_config['simulation_time'] = args.simulation_time
    if args.arrival_pattern is not None: final_config['arrival_pattern'] = args.arrival_pattern
    if args.dataset_file is not None: final_config['dataset_file'] = args.dataset_file 
    
    return final_config

if __name__ == "__main__":
    initial_config = load_initial_config()
    final_config = parse_cli_arguments(initial_config)
    app = App(initial_params=final_config)
    app.mainloop()