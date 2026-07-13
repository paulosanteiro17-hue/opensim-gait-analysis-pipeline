import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import argparse
import datetime
import sys
import re# ==========================================
# CONFIGURAÇÕES GERAIS E ESTRUTURA DE PASTAS
# ==========================================
BASE_DIR = Path(r"C:\Users\paulo\Modelos_OpenSim_Teste")
DATASET_DIR = BASE_DIR / "Gait Dataset"
PROJETO_DIR = BASE_DIR / "Projeto_OpenSim"
TEMPLATES_DIR = PROJETO_DIR / "Templates"
PACIENTES_DIR = PROJETO_DIR / "Pacientes"
REPORT_FILE = PROJETO_DIR / "pipeline_report.txt"

C3D_TO_TRC_SCRIPT = DATASET_DIR / "c3d_to_trc.py"
PLOT_MUSCLE_SCRIPT = BASE_DIR / "Nova pasta" / "plot_muscle.py"
PLOT_COM_SCRIPT = BASE_DIR / "Nova pasta" / "plot_com.py"
PLOT_KIN_SCRIPT = BASE_DIR / "Nova pasta" / "plotter_bonito.py"

def log_report(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    print(log_line)
    with open(REPORT_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

def get_time_range_from_trc(trc_path):
    """Extrai tempo inicial e final do arquivo .trc"""
    try:
        with open(trc_path, "r") as f:
            lines = f.readlines()

        start_idx = None
        for i, line in enumerate(lines):
            if line.startswith("Frame#"):
                start_idx = i + 2
                break

        if start_idx is None:
            return None, None

        times = []
        for line in lines[start_idx:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    times.append(float(parts[1]))
                except ValueError:
                    pass

        if not times:
            return None, None

        return times[0], times[-1]

    except Exception as e:
        log_report(f"Erro ao ler tempo do TRC {trc_path.name}: {e}")
        return None, None

def get_time_range_from_mot(mot_path):
    """Extrai tempo inicial e final do arquivo .mot"""
    try:
        times = []
        with open(mot_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                try:
                    times.append(float(parts[0]))
                except ValueError:
                    continue

        if not times:
            return None, None

        return times[0], times[-1]

    except Exception as e:
        log_report(f"Erro ao ler tempo do MOT {mot_path.name}: {e}")
        return None, None

def generate_qc_report(pac_id, logs_folder):
    qc_file = logs_folder / "QC_report.txt"
    ik_stdout = logs_folder / "IK_stdout.txt"
    scale_stdout = logs_folder / "Scale_stdout.txt"
    analyze_stdout = logs_folder / "Analyze_stdout.txt"
    
    scale_rms = 0.0
    scale_max = 0.0
    if scale_stdout.exists():
        with open(scale_stdout, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            m = re.search(r'marker error:\s+RMS\s+=\s+([\d\.]+),\s+max\s+=\s+([\d\.]+)', content)
            if m:
                scale_rms = float(m.group(1)) * 1000
                scale_max = float(m.group(2)) * 1000

    ik_rms_list = []
    ik_max_err_list = []
    if ik_stdout.exists():
        with open(ik_stdout, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = re.search(r'marker error:\s+RMS\s+=\s+([\d\.]+),\s+max\s+=\s+([\d\.]+)', line)
                if m:
                    ik_rms_list.append(float(m.group(1)) * 1000)
                    ik_max_err_list.append(float(m.group(2)) * 1000)
                    
    ik_avg_rms = sum(ik_rms_list) / len(ik_rms_list) if ik_rms_list else 0.0
    ik_max_rms = max(ik_rms_list) if ik_rms_list else 0.0
    ik_max_err = max(ik_max_err_list) if ik_max_err_list else 0.0
    
    analyze_warning = "Nenhum"
    if analyze_stdout.exists():
        with open(analyze_stdout, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "relaxing constraints" in content or "Unable to achieve required assembly error tolerance" in content:
                analyze_warning = "AVISO (Tolerancia de montagem relaxada)"
                
    if ik_avg_rms == 0.0:
        status = "FALHA IK"
    elif ik_avg_rms > 15.0:
        status = "REVISAR (IK RMS > 15mm)"
    elif scale_rms > 30.0:
        status = "APROVADO COM OBSERVACAO (Scale RMS > 30mm)"
    else:
        status = "APROVADO"
        
    qc_content = f"=== RELATÓRIO DE QUALIDADE (QC) - {pac_id} ===\n"
    qc_content += f"Status Final: {status}\n\n"
    qc_content += "1. SCALE (Estático)\n"
    qc_content += f"   RMS Geral: {scale_rms:.2f} mm\n"
    qc_content += f"   Erro Máximo: {scale_max:.2f} mm\n\n"
    qc_content += "2. INVERSE KINEMATICS (Dinâmico)\n"
    qc_content += f"   RMS Médio: {ik_avg_rms:.2f} mm\n"
    qc_content += f"   RMS Máximo: {ik_max_rms:.2f} mm\n"
    qc_content += f"   Erro Máximo Absoluto: {ik_max_err:.2f} mm\n\n"
    qc_content += "3. ANALYZE\n"
    qc_content += f"   Avisos: {analyze_warning}\n"
    
    with open(qc_file, "w", encoding="utf-8") as f:
        f.write(qc_content)
        
    return status, ik_avg_rms, scale_rms

def check_opensim_cmd(custom_path=None):
    if custom_path and Path(custom_path).exists():
        return custom_path
    
    # Tenta usar do PATH
    try:
        subprocess.run(["opensim-cmd", "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return "opensim-cmd"
    except FileNotFoundError:
        pass
        
    # Busca automática nas pastas mais comuns do Windows
    caminhos_comuns = [
        r"C:\OpenSim 4.5\bin\opensim-cmd.exe",
        r"C:\OpenSim 4.4\bin\opensim-cmd.exe",
        r"C:\OpenSim 4.3\bin\opensim-cmd.exe",
        r"C:\Program Files\OpenSim 4.5\bin\opensim-cmd.exe",
        r"C:\Program Files\OpenSim 4.4\bin\opensim-cmd.exe",
    ]
    
    for caminho in caminhos_comuns:
        if Path(caminho).exists():
            print(f"[Autodetect] opensim-cmd encontrado em: {caminho}")
            return caminho
            
    return None

def main():
    parser = argparse.ArgumentParser(description="Automação do Pipeline OpenSim")
    parser.add_argument("--opensim", type=str, default=None, help="Caminho para o opensim-cmd.exe")
    parser.add_argument("--teste-paciente", type=str, default=None, help="Executar apenas para um paciente (ex: 01_LLG)")
    parser.add_argument("--trial", type=str, default="1_00.c3d", help="Arquivo C3D dinâmico a processar (ex: 1_00.c3d)")
    parser.add_argument("--generic-model", type=str, required=False, help="Modelo OpenSim genérico usado no Scale")
    args = parser.parse_args()

    # 1. VALIDAÇÕES INICIAIS (1 a 3)
    opensim_cmd = check_opensim_cmd(args.opensim)
    if not opensim_cmd:
        print("ERRO CRÍTICO: opensim-cmd não encontrado no PATH nem passado no argumento --opensim.")
        sys.exit(1)

    template_scale = TEMPLATES_DIR / "Setup_Scale_Template.xml"
    if not template_scale.exists():
        template_scale = BASE_DIR / "Setup_Scale_Template.xml" # Fallback para a pasta raiz
        
    template_ik = TEMPLATES_DIR / "Setup_IK_Base.xml"
    if not template_ik.exists():
        template_ik = TEMPLATES_DIR / "Setup_IK.xml"
        
    template_analyze = TEMPLATES_DIR / "Setup_Analyze_Base.xml"
    if not template_analyze.exists():
        template_analyze = TEMPLATES_DIR / "Setup_Analyze.xml"

    # Criando arquivo de log
    PROJETO_DIR.mkdir(parents=True, exist_ok=True)
    PACIENTES_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== RELATÓRIO DO PIPELINE OPENSIM ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}) ===\n")

    if not template_ik.exists() or not template_analyze.exists():
        log_report("ERRO CRÍTICO: Templates IK ou Analyze não encontrados na pasta Templates.")
        sys.exit(1)

    # Validar scripts
    for script in [C3D_TO_TRC_SCRIPT, PLOT_MUSCLE_SCRIPT, PLOT_COM_SCRIPT, PLOT_KIN_SCRIPT]:
        if not script.exists():
            log_report(f"AVISO: script não encontrado: {script}")

    # Coletar pastas de pacientes
    pacientes_young = sorted(list((DATASET_DIR / "Young").glob("*")))[:15]
    pacientes_old = sorted(list((DATASET_DIR / "Old").glob("*")))[:15]
    todos_pacientes = pacientes_young + pacientes_old

    if args.teste_paciente:
        todos_pacientes = [p for p in todos_pacientes if p.name == args.teste_paciente]
        if not todos_pacientes:
            log_report(f"Paciente de teste '{args.teste_paciente}' não encontrado nas 15 primeiras pastas.")
            sys.exit(1)

    log_report(f"INICIANDO PROCESSAMENTO (Total: {len(todos_pacientes)} pacientes)")

    for pac_folder in todos_pacientes:
        pac_id = pac_folder.name
        log_report(f"--- PROCESSANDO PACIENTE: {pac_id} ---")
        
        # 4. Achar C3Ds
        static_c3d = pac_folder / "static.c3d"
        dyn_c3d = pac_folder / args.trial
        
        if not static_c3d.exists():
            log_report(f"[{pac_id}] FALHA: static.c3d não encontrado em {pac_folder}.")
            continue
        if not dyn_c3d.exists():
            log_report(f"[{pac_id}] FALHA: trial {args.trial} não encontrado em {pac_folder}.")
            continue
            
        # Estrutura de Destino
        dest_folder = PACIENTES_DIR / pac_id
        res_folder = dest_folder / "Resultados"
        analyze_folder = res_folder / "Analyze"
        graficos_folder = res_folder / "Graficos"
        logs_folder = res_folder / "Logs"
        
        for folder in [res_folder, analyze_folder, graficos_folder, logs_folder]:
            folder.mkdir(parents=True, exist_ok=True)
            
        static_trc = dest_folder / "static.trc"
        dyn_trc = dest_folder / (dyn_c3d.stem + ".trc")
        
        # 5. Converter C3D para TRC
        log_report(f"[{pac_id}] Convertendo C3Ds para TRC...")
        
        res_static = subprocess.run(
            [sys.executable, str(C3D_TO_TRC_SCRIPT), "--file", str(static_c3d), "--output-dir", str(dest_folder)],
            capture_output=True, text=True
        )
        (logs_folder / "Convert_static_stdout.txt").write_text(res_static.stdout, encoding="utf-8")
        (logs_folder / "Convert_static_stderr.txt").write_text(res_static.stderr, encoding="utf-8")

        if res_static.returncode != 0:
            log_report(f"[{pac_id}] FALHA NA CONVERSÃO DO STATIC.C3D. Verificar Convert_static_stderr.txt")
            continue

        res_dyn = subprocess.run(
            [sys.executable, str(C3D_TO_TRC_SCRIPT), "--file", str(dyn_c3d), "--output-dir", str(dest_folder)],
            capture_output=True, text=True
        )
        (logs_folder / "Convert_dyn_stdout.txt").write_text(res_dyn.stdout, encoding="utf-8")
        (logs_folder / "Convert_dyn_stderr.txt").write_text(res_dyn.stderr, encoding="utf-8")

        if res_dyn.returncode != 0:
            log_report(f"[{pac_id}] FALHA NA CONVERSÃO DO DINÂMICO. Verificar Convert_dyn_stderr.txt")
            continue
            
        if not static_trc.exists() or not dyn_trc.exists():
            log_report(f"[{pac_id}] FALHA NA CONVERSÃO: TRCs não foram gerados.")
            continue
            
        # 6. SCALE TOOL
        scaled_raw_osim = dest_folder / f"{pac_id}_scaled_raw.osim"
        scaled_osim = dest_folder / f"{pac_id}_scaled_markerplaced.osim"
        
        if template_scale.exists():
            log_report(f"[{pac_id}] Configurando e rodando Scale Tool... (Nota: a massa foi padronizada no processo de escala devido à ausência de metadados individuais)")
            scale_xml = logs_folder / f"Setup_Scale_{pac_id}.xml"
            scale_factors = logs_folder / f"{pac_id}_scaleSet.xml"
            static_mot = logs_folder / f"{pac_id}_static_output.mot"
            
            static_start, static_end = get_time_range_from_trc(static_trc)
            if static_start is None:
                log_report(f"[{pac_id}] FALHA: Tempo inválido no TRC estático {static_trc.name}.")
                continue
                
            try:
                tree = ET.parse(template_scale)
                root = tree.getroot()
                
                # Update generic model if provided
                if args.generic_model:
                    for elem in root.findall(".//GenericModelMaker/model_file"):
                        elem.text = str(Path(args.generic_model).resolve())
                
                # ModelScaler
                for tag in root.iter('ModelScaler'):
                    for sub in tag.iter('marker_file'): sub.text = str(static_trc.resolve())
                    for sub in tag.iter('time_range'): sub.text = f"{static_start} {static_end}"
                    for sub in tag.iter('output_model_file'): sub.text = str(scaled_raw_osim.resolve())
                    for sub in tag.iter('output_scale_file'): sub.text = str(scale_factors.resolve())
                
                # MarkerPlacer
                for tag in root.iter('MarkerPlacer'):
                    for sub in tag.iter('marker_file'): sub.text = str(static_trc.resolve())
                    for sub in tag.iter('time_range'): sub.text = f"{static_start} {static_end}"
                    for sub in tag.iter('output_model_file'): sub.text = str(scaled_osim.resolve())
                    for sub in tag.iter('output_motion_file'): sub.text = str(static_mot.resolve())
                
                tree.write(scale_xml, encoding="UTF-8", xml_declaration=True)
                
                # Executar Scale
                with open(logs_folder / "Scale_stdout.txt", "w") as out, open(logs_folder / "Scale_stderr.txt", "w") as err:
                    process = subprocess.run([opensim_cmd, "run-tool", str(scale_xml.resolve())], stdout=out, stderr=err)
                    
                if process.returncode != 0 or not scaled_osim.exists():
                    log_report(f"[{pac_id}] FALHA NO SCALE: arquivo {scaled_osim.name} não criado ou erro. Verificar Scale_stderr.txt")
                    continue
                    
            except Exception as e:
                log_report(f"[{pac_id}] ERRO NO SCALE: {e}")
                continue
        else:
            # Se não tem template Scale, verifica se o .osim já existe na pasta origem
            orig_osim = pac_folder / "subject_scaled.osim"
            if orig_osim.exists():
                import shutil
                shutil.copy(orig_osim, scaled_osim)
                log_report(f"[{pac_id}] Modelo escalado copiado da origem.")
            else:
                log_report(f"[{pac_id}] FALHA CRÍTICA: Não há modelo escalado (.osim) e nem Setup_Scale_Template.xml.")
                continue

        # 7. IK TOOL
        log_report(f"[{pac_id}] Configurando e rodando IK...")
        start_time, end_time = get_time_range_from_trc(dyn_trc)
        if start_time is None:
            log_report(f"[{pac_id}] FALHA: Tempo inválido no TRC {dyn_trc.name}.")
            continue
            
        ik_xml = logs_folder / f"Setup_IK_{pac_id}.xml"
        mot_file = res_folder / f"{pac_id}_ik.mot"
        
        try:
            tree = ET.parse(template_ik)
            root = tree.getroot()
            
            for tag in root.iter('model_file'): tag.text = str(scaled_osim.resolve())
            for tag in root.iter('marker_file'): tag.text = str(dyn_trc.resolve())
            for tag in root.iter('output_motion_file'): tag.text = str(mot_file.resolve())
            for tag in root.iter('time_range'): tag.text = f"{start_time} {end_time}"
                
            tree.write(ik_xml, encoding="UTF-8", xml_declaration=True)
            
            with open(logs_folder / "IK_stdout.txt", "w") as out, open(logs_folder / "IK_stderr.txt", "w") as err:
                process = subprocess.run([opensim_cmd, "run-tool", str(ik_xml.resolve())], stdout=out, stderr=err)
                
            if process.returncode != 0 or not mot_file.exists():
                log_report(f"[{pac_id}] FALHA NA IK: arquivo {mot_file.name} não foi criado ou returncode != 0. Verificar IK_stderr.txt")
                continue
                
        except Exception as e:
            log_report(f"[{pac_id}] ERRO AO LER/GERAR XML IK: {e}")
            continue

        # 8. ANALYZE TOOL
        log_report(f"[{pac_id}] Configurando e rodando Analyze...")
        mot_start, mot_end = get_time_range_from_mot(mot_file)
        if mot_start is None:
            log_report(f"[{pac_id}] FALHA: Tempo inválido no MOT {mot_file.name}.")
            continue
            
        analyze_xml = logs_folder / f"Setup_Analyze_{pac_id}.xml"
        
        try:
            tree = ET.parse(template_analyze)
            root = tree.getroot()
            
            for tag in root.iter('model_file'): tag.text = str(scaled_osim.resolve())
            for tag in root.iter('coordinates_file'): tag.text = str(mot_file.resolve())
            for tag in root.iter('results_directory'): tag.text = str(analyze_folder.resolve())
            for tag in root.iter('initial_time'): tag.text = str(mot_start)
            for tag in root.iter('final_time'): tag.text = str(mot_end)
                
            tree.write(analyze_xml, encoding="UTF-8", xml_declaration=True)
            
            with open(logs_folder / "Analyze_stdout.txt", "w") as out, open(logs_folder / "Analyze_stderr.txt", "w") as err:
                process = subprocess.run([opensim_cmd, "run-tool", str(analyze_xml.resolve())], stdout=out, stderr=err)
                
            if process.returncode != 0:
                log_report(f"[{pac_id}] FALHA NO ANALYZE: returncode != 0. Verificar Analyze_stderr.txt")
                continue
                
            # Validar arquivos .sto flexíveis
            sto_files = list(analyze_folder.glob("*.sto"))
            
            has_length = any("Length" in f.name for f in sto_files)
            has_velocity = any("Velocity" in f.name for f in sto_files)
            has_bodykin = any("BodyKinematics" in f.name for f in sto_files)
            
            log_report(f"[{pac_id}] Analyze verificação - Length: {'OK' if has_length else 'ausente'}, Velocity: {'OK' if has_velocity else 'ausente'}, BodyKinematics: {'OK' if has_bodykin else 'ausente'}")
            
            if not has_length:
                log_report(f"[{pac_id}] AVISO: *Length*.sto não encontrado no Analyze.")
                
            sto_length = next((f for f in sto_files if f.name.endswith("_Length.sto")), None)
            sto_com = next((f for f in sto_files if "BodyKinematics_pos_global" in f.name), None)
            
        except Exception as e:
            log_report(f"[{pac_id}] ERRO AO LER/GERAR XML ANALYZE: {e}")
            continue

        # 9. FASE D: GERAR GRÁFICOS (HEADLESS)
        log_report(f"[{pac_id}] Gerando gráficos em lote...")
        try:
            # Gráfico de Cinemática
            kin_png = graficos_folder / f"{pac_id}_Cinematica.png"
            res_kin = subprocess.run([sys.executable, str(PLOT_KIN_SCRIPT), "--ik_file", str(mot_file), "--output", str(kin_png)], capture_output=True, text=True)
            (logs_folder / "Plot_Kinematics_stdout.txt").write_text(res_kin.stdout, encoding="utf-8")
            (logs_folder / "Plot_Kinematics_stderr.txt").write_text(res_kin.stderr, encoding="utf-8")
            if res_kin.returncode != 0:
                log_report(f"[{pac_id}] AVISO: gráfico de cinemática falhou. Verificar logs.")
            
            # Gráfico de CoM
            if sto_com:
                com_png = graficos_folder / f"{pac_id}_CentroDeMassa.png"
                res_com = subprocess.run([sys.executable, str(PLOT_COM_SCRIPT), "--ik_file", str(mot_file), "--com_file", str(sto_com), "--output", str(com_png)], capture_output=True, text=True)
                (logs_folder / "Plot_CoM_stdout.txt").write_text(res_com.stdout, encoding="utf-8")
                (logs_folder / "Plot_CoM_stderr.txt").write_text(res_com.stderr, encoding="utf-8")
                if res_com.returncode != 0:
                    log_report(f"[{pac_id}] AVISO: gráfico de Centro de Massa falhou. Verificar logs.")
                
            # Gráfico Muscular
            if sto_length:
                muscle_png = graficos_folder / f"{pac_id}_Musculos.png"
                res_muscle = subprocess.run([sys.executable, str(PLOT_MUSCLE_SCRIPT), "--ik_file", str(mot_file), "--muscle_file", str(sto_length), "--output", str(muscle_png)], capture_output=True, text=True)
                (logs_folder / "Plot_Muscle_stdout.txt").write_text(res_muscle.stdout, encoding="utf-8")
                (logs_folder / "Plot_Muscle_stderr.txt").write_text(res_muscle.stderr, encoding="utf-8")
                if res_muscle.returncode != 0:
                    log_report(f"[{pac_id}] AVISO: gráfico de músculos falhou. Verificar logs.")
                
            log_report(f"[{pac_id}] Gráficos processados. (Cheque logs se houver AVISO acima)")
        except Exception as e:
            log_report(f"[{pac_id}] ERRO NA GERAÇÃO DOS GRÁFICOS: {e}")
        # Geração do QC Report
        try:
            status, ik_rms, sc_rms = generate_qc_report(pac_id, logs_folder)
            log_report(f"[{pac_id}] QC STATUS: {status} (IK RMS: {ik_rms:.1f}mm | Scale RMS: {sc_rms:.1f}mm)")
        except Exception as e:
            log_report(f"[{pac_id}] ERRO AO GERAR QC REPORT: {e}")
            
        log_report(f"[{pac_id}] SUCESSO COMPLETO.")

if __name__ == "__main__":
    main()
