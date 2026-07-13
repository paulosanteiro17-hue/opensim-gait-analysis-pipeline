import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, detrend
from scipy.interpolate import interp1d

# Estilo visual melhorado para gráficos de publicação
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'lines.linewidth': 2.5,
    'figure.titlesize': 14
})

# ==========================================
# CONFIGURAÇÕES GERAIS E PASTAS
# ==========================================
BASE_DIR = Path(r"C:\Users\paulo\Modelos_OpenSim_Teste")
DATASET_DIR = BASE_DIR / "Gait Dataset"
PACIENTES_DIR = BASE_DIR / "Projeto_OpenSim" / "Pacientes"
RESULTADOS_GRP_DIR = BASE_DIR / "Projeto_OpenSim" / "Resultados_Grupo"
RESULTADOS_GRP_DIR.mkdir(parents=True, exist_ok=True)

# Cores para o artigo
COLOR_YOUNG = '#1f77b4' # Azul
COLOR_OLD = '#ff7f0e'   # Laranja

def load_osim_file(filepath):
    skip_lines = 0
    with open(filepath, 'r') as file:
        for i, line in enumerate(file):
            if line.startswith('time') or line.startswith('endheader'):
                if line.startswith('endheader'):
                    skip_lines = i + 1
                else:
                    skip_lines = i
                break
    return pd.read_csv(filepath, sep='\t', skiprows=skip_lines)

def get_muscle_col(df, base_name):
    aliases = {
        'gasmed_r': ['gasmed_r', 'med_gas_r'],
        'rect_fem_r': ['rect_fem_r', 'rec_fem_r'],
        'semimem_r': ['semimem_r', 'semi_mem_r'],
        'bifemlh_r': ['bifemlh_r', 'bi_fem_lh_r'],
        'soleus_r': ['soleus_r', 'sol_r'],
        'tib_ant_r': ['tib_ant_r']
    }
    for alias in aliases.get(base_name, [base_name]):
        if alias in df.columns:
            return alias
    return None

def extract_patient_cycles(df, signal_col, cycle_times, is_com=False, com_axis=None, is_muscle=False):
    if signal_col not in df.columns or 'time' not in df.columns:
        return None
        
    time_array = df['time'].values
    signal = df[signal_col].values
    
    if is_com:
        # Converter metros para centímetros
        signal = signal * 100.0
        if com_axis == 'X':
            signal = detrend(signal)
        elif com_axis in ['Y', 'Z']:
            signal = signal - np.mean(signal)
            
    if is_muscle:
        # Converter metros para centímetros e subtrair a média individual
        signal = signal * 100.0
        signal = signal - np.mean(signal)
            
    ciclos = []
    for start_t, end_t in cycle_times:
        start_idx = np.argmin(np.abs(time_array - start_t))
        end_idx = np.argmin(np.abs(time_array - end_t))
        
        if end_idx > start_idx + 5: 
            ciclo_original = signal[start_idx:end_idx]
            tempo_original = np.linspace(0, 100, len(ciclo_original))
            tempo_novo = np.linspace(0, 100, 101)
            
            f_interp = interp1d(tempo_original, ciclo_original, kind='cubic')
            ciclo_norm = f_interp(tempo_novo)
            
            if is_com and com_axis == 'X':
                ciclo_norm = ciclo_norm - ciclo_norm[0]
                
            ciclos.append(ciclo_norm)
            
    if not ciclos:
        return None
        
    return np.mean(np.array(ciclos), axis=0)

def plot_group_var(ax_plot, data_young, data_old, ylabel, title):
    x_axis = np.linspace(0, 100, 101)
    
    if data_young:
        y_mat = np.array(data_young)
        y_mean = np.mean(y_mat, axis=0)
        y_std = np.std(y_mat, axis=0, ddof=1) if len(y_mat) > 1 else np.zeros(101)
        ax_plot.plot(x_axis, y_mean, color=COLOR_YOUNG, label='Jovens')
        ax_plot.fill_between(x_axis, y_mean - y_std, y_mean + y_std, color=COLOR_YOUNG, alpha=0.3)
        
    if data_old:
        o_mat = np.array(data_old)
        o_mean = np.mean(o_mat, axis=0)
        o_std = np.std(o_mat, axis=0, ddof=1) if len(o_mat) > 1 else np.zeros(101)
        ax_plot.plot(x_axis, o_mean, color=COLOR_OLD, label='Idosos')
        ax_plot.fill_between(x_axis, o_mean - o_std, o_mean + o_std, color=COLOR_OLD, alpha=0.3)
        
    ax_plot.set_title(title)
    ax_plot.set_ylabel(ylabel)
    ax_plot.grid(True, linestyle='--', alpha=0.6)
    if ax_plot.get_subplotspec().is_last_row():
        ax_plot.set_xlabel('Ciclo da Marcha (%)')

def main():
    print("Iniciando processamento de grupo...")
    
    young_ids = [p.name for p in (DATASET_DIR / "Young").glob("*") if p.is_dir()]
    old_ids = [p.name for p in (DATASET_DIR / "Old").glob("*") if p.is_dir()]
    
    group_data = {
        'Young': {'kinematics': {}, 'com': {}, 'muscles': {}},
        'Old': {'kinematics': {}, 'com': {}, 'muscles': {}}
    }
    
    counts = {
        'Young': {'kinematics': {}, 'com': {}, 'muscles': {}},
        'Old': {'kinematics': {}, 'com': {}, 'muscles': {}}
    }
    
    vars_kinematics = ['knee_angle_r', 'ankle_angle_r', 'hip_flexion_r']
    vars_com = {'X': 'center_of_mass_X', 'Y': 'center_of_mass_Y', 'Z': 'center_of_mass_Z'}
    vars_muscles = ['rect_fem_r', 'semimem_r', 'bifemlh_r', 'gasmed_r', 'soleus_r', 'tib_ant_r']
    
    for grp in ['Young', 'Old']:
        for var in vars_kinematics: 
            group_data[grp]['kinematics'][var] = []
            counts[grp]['kinematics'][var] = 0
        for ax in vars_com.keys(): 
            group_data[grp]['com'][ax] = []
            counts[grp]['com'][ax] = 0
        for var in vars_muscles: 
            group_data[grp]['muscles'][var] = []
            counts[grp]['muscles'][var] = 0

    pacientes = [p for p in PACIENTES_DIR.glob("*") if p.is_dir()]
    
    for pac_folder in pacientes:
        pac_id = pac_folder.name
        grp = 'Young' if pac_id in young_ids else ('Old' if pac_id in old_ids else None)
        if not grp: 
            continue 
        
        res_dir = pac_folder / "Resultados"
        ik_file = res_dir / f"{pac_id}_ik.mot"
        analyze_dir = res_dir / "Analyze"
        
        if not ik_file.exists() or not analyze_dir.exists():
            continue
            
        sto_files = list(analyze_dir.glob("*.sto"))
        sto_length = next((f for f in sto_files if f.name.endswith("_Length.sto")), None)
        sto_com = next((f for f in sto_files if "BodyKinematics_pos_global" in f.name), None)
        
        df_ik = load_osim_file(ik_file)
        
        if 'knee_angle_r' in df_ik.columns:
            df_ik['knee_angle_r'] = -df_ik['knee_angle_r']
            
        if 'hip_flexion_r' not in df_ik.columns or 'time' not in df_ik.columns: 
            continue
            
        peaks_idx, _ = find_peaks(df_ik['hip_flexion_r'], distance=50, prominence=5)
        if len(peaks_idx) < 2: 
            continue
            
        peak_times = df_ik['time'].iloc[peaks_idx].values
        durations = np.diff(peak_times)
        if len(durations) == 0:
            continue
            
        median_dur = np.median(durations)
        cycle_times = []
        for i in range(len(durations)):
            if 0.8 * median_dur <= durations[i] <= 1.2 * median_dur:
                cycle_times.append((peak_times[i], peak_times[i+1]))
                
        if not cycle_times:
            continue
        
        for var in vars_kinematics:
            paciente_mean_curve = extract_patient_cycles(df_ik, var, cycle_times)
            if paciente_mean_curve is not None:
                group_data[grp]['kinematics'][var].append(paciente_mean_curve)
                counts[grp]['kinematics'][var] += 1
                
        if sto_com and sto_com.exists():
            df_com = load_osim_file(sto_com)
            for ax, col in vars_com.items():
                paciente_mean_curve = extract_patient_cycles(df_com, col, cycle_times, is_com=True, com_axis=ax)
                if paciente_mean_curve is not None:
                    group_data[grp]['com'][ax].append(paciente_mean_curve)
                    counts[grp]['com'][ax] += 1
                    
        if sto_length and sto_length.exists():
            df_musc = load_osim_file(sto_length)
            for var in vars_muscles:
                col = get_muscle_col(df_musc, var)
                if col:
                    paciente_mean_curve = extract_patient_cycles(df_musc, col, cycle_times, is_muscle=True)
                    if paciente_mean_curve is not None:
                        group_data[grp]['muscles'][var].append(paciente_mean_curve)
                        counts[grp]['muscles'][var] += 1
                    
    print("\nExtração concluída. Gerando gráficos finais...")
    
    fig, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)
    plot_group_var(axes[0], group_data['Young']['kinematics']['hip_flexion_r'], group_data['Old']['kinematics']['hip_flexion_r'], 'Ângulo (graus)', 'Quadril Direito (Flexão/Extensão)')
    plot_group_var(axes[1], group_data['Young']['kinematics']['knee_angle_r'], group_data['Old']['kinematics']['knee_angle_r'], 'Ângulo (graus)', 'Joelho Direito (Flexão/Extensão)')
    plot_group_var(axes[2], group_data['Young']['kinematics']['ankle_angle_r'], group_data['Old']['kinematics']['ankle_angle_r'], 'Ângulo (graus)', 'Tornozelo Direito (Dorsi/Plantarflexão)')
    axes[0].legend(loc='upper right')
    fig.text(0.5, 0.01, 'Área sombreada = ±1 DP entre participantes', ha='center', fontsize=10, style='italic', color='dimgrey')
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(RESULTADOS_GRP_DIR / 'Figura_A_Cinematica.png', dpi=300)
    plt.close()
    
    fig, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)
    plot_group_var(axes[0], group_data['Young']['com']['X'], group_data['Old']['com']['X'], 'Deslocamento (cm)', 'Centro de Massa - Anteroposterior (Detrendido)')
    plot_group_var(axes[1], group_data['Young']['com']['Y'], group_data['Old']['com']['Y'], 'Deslocamento (cm)', 'Centro de Massa - Vertical (Centrado)*')
    plot_group_var(axes[2], group_data['Young']['com']['Z'], group_data['Old']['com']['Z'], 'Deslocamento (cm)', 'Centro de Massa - Mediolateral (Centrado)')
    axes[0].legend(loc='upper right')
    fig.text(0.5, 0.01, 'Área sombreada = ±1 DP entre participantes', ha='center', fontsize=10, style='italic', color='dimgrey')
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(RESULTADOS_GRP_DIR / 'Figura_B_CoM.png', dpi=300)
    plt.close()
    
    fig, axes = plt.subplots(3, 2, figsize=(12, 12), sharex=True)
    axes = axes.flatten()
    muscle_titles = ['Reto Femoral', 'Semimembranoso', 'Bíceps Femoral (CL)', 'Gastrocnêmio Medial', 'Sóleo', 'Tibial Anterior']
    for i, var in enumerate(vars_muscles):
        plot_group_var(axes[i], group_data['Young']['muscles'][var], group_data['Old']['muscles'][var], 'Variação de comprimento (cm)', muscle_titles[i])
    axes[0].legend(loc='upper right')
    fig.suptitle('Comprimentos musculotendíneos estimados', fontsize=16, fontweight='bold')
    fig.text(0.5, 0.01, 'Área sombreada = ±1 DP entre participantes', ha='center', fontsize=10, style='italic', color='dimgrey')
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(RESULTADOS_GRP_DIR / 'Figura_C_Musculos.png', dpi=300)
    plt.close()
    
    print("\nCalculando métricas para a Tabela 1...")
    
    def calc_mean_std(data):
        if len(data) == 0: return "N/A"
        if len(data) == 1: return f"{data[0]:.2f} ± 0.00"
        return f"{np.mean(data):.2f} ± {np.std(data, ddof=1):.2f}"
        
    def get_metrics(grp_data):
        res = {}
        if grp_data['kinematics']['knee_angle_r']:
            arr = np.array(grp_data['kinematics']['knee_angle_r'])
            peaks = np.max(arr, axis=1)
            amps = np.max(arr, axis=1) - np.min(arr, axis=1)
            res['Pico de flexão do joelho (graus)'] = calc_mean_std(peaks)
            res['Amplitude do joelho (graus)'] = calc_mean_std(amps)
        else:
            res['Pico de flexão do joelho (graus)'] = "N/A"
            res['Amplitude do joelho (graus)'] = "N/A"
            
        if grp_data['kinematics']['ankle_angle_r']:
            arr = np.array(grp_data['kinematics']['ankle_angle_r'])
            dorsi = np.max(arr, axis=1)
            plantar = np.min(arr, axis=1)
            res['Pico de dorsiflexão do tornozelo (graus)'] = calc_mean_std(dorsi)
            res['Pico de plantarflexão do tornozelo* (graus)'] = calc_mean_std(plantar)
        else:
            res['Pico de dorsiflexão do tornozelo (graus)'] = "N/A"
            res['Pico de plantarflexão do tornozelo* (graus)'] = "N/A"
            
        if grp_data['com']['Y']:
            arrY = np.array(grp_data['com']['Y'])
            excY = np.max(arrY, axis=1) - np.min(arrY, axis=1)
            res['Excursão vertical do CoM (cm)'] = calc_mean_std(excY)
        else:
            res['Excursão vertical do CoM (cm)'] = "N/A"
            
        if grp_data['com']['Z']:
            arrZ = np.array(grp_data['com']['Z'])
            excZ = np.max(arrZ, axis=1) - np.min(arrZ, axis=1)
            res['Excursão mediolateral do CoM (cm)'] = calc_mean_std(excZ)
        else:
            res['Excursão mediolateral do CoM (cm)'] = "N/A"
            
        if grp_data['muscles']['rect_fem_r']:
            arrRF = np.array(grp_data['muscles']['rect_fem_r'])
            excRF = np.max(arrRF, axis=1) - np.min(arrRF, axis=1)
            res['Excursão do reto femoral (cm)'] = calc_mean_std(excRF)
        else:
            res['Excursão do reto femoral (cm)'] = "N/A"
            
        if grp_data['muscles']['gasmed_r']:
            arrGM = np.array(grp_data['muscles']['gasmed_r'])
            excGM = np.max(arrGM, axis=1) - np.min(arrGM, axis=1)
            res['Excursão do gastrocnêmio medial (cm)'] = calc_mean_std(excGM)
        else:
            res['Excursão do gastrocnêmio medial (cm)'] = "N/A"
            
        return res

    res_young = get_metrics(group_data['Young'])
    res_old = get_metrics(group_data['Old'])
    
    # Gerando DataFrame pandas e exportando
    df_table = pd.DataFrame({
        'Variável': list(res_young.keys()),
        'Jovens': list(res_young.values()),
        'Idosos': list(res_old.values())
    })
    
    df_table.to_csv(RESULTADOS_GRP_DIR / 'Tabela1_Resumo.csv', index=False, encoding='utf-8')
    df_table.to_markdown(RESULTADOS_GRP_DIR / 'Tabela1_Resumo.md', index=False)
    
    # Adicionando notas metodológicas no rodapé do Markdown
    with open(RESULTADOS_GRP_DIR / 'Tabela1_Resumo.md', 'a', encoding='utf-8') as f:
        f.write('\n\n**Notas:**\n')
        f.write('- Jovens: n = 14; Idosos: n = 13.\n')
        f.write('- * Valores interpretados conforme a convenção angular do modelo musculoesquelético.\n')
        f.write('- Valores apresentados como média ± desvio-padrão entre participantes.\n')
        f.write('- As excursões musculotendíneas correspondem à variação pico-a-pico das curvas centralizadas individualmente.\n')
        f.write('- Os ciclos da marcha foram normalizados de 0 a 100%.\n')
    try:
        df_table.to_excel(RESULTADOS_GRP_DIR / 'Tabela1_Resumo.xlsx', index=False)
    except Exception:
        pass
            
    # 5. RELATÓRIO DE AUDITORIA E AVISOS
    report_lines = []
    report_lines.append("==================================================")
    report_lines.append("RELATÓRIO DE AUDITORIA (CONTROLE DE QUALIDADE)")
    report_lines.append("==================================================")
    report_lines.append("\n1. CINEMÁTICA")
    for var in vars_kinematics:
        y_count = counts['Young']['kinematics'][var]
        o_count = counts['Old']['kinematics'][var]
        report_lines.append(f"  {var:<15} — Jovens: {y_count:<2} | Idosos: {o_count:<2}")
        if y_count <= 1: report_lines.append(f"    -> AVISO: Grupo Young possui apenas {y_count} paciente(s) para {var}.")
        if o_count <= 1: report_lines.append(f"    -> AVISO: Grupo Old possui apenas {o_count} paciente(s) para {var}.")
    
    report_lines.append("\n2. CENTRO DE MASSA (CoM)")
    for ax in vars_com.keys():
        y_count = counts['Young']['com'][ax]
        o_count = counts['Old']['com'][ax]
        report_lines.append(f"  {ax:<15} — Jovens: {y_count:<2} | Idosos: {o_count:<2}")
        if y_count <= 1: report_lines.append(f"    -> AVISO: Grupo Young possui apenas {y_count} paciente(s) para o eixo {ax}.")
        if o_count <= 1: report_lines.append(f"    -> AVISO: Grupo Old possui apenas {o_count} paciente(s) para o eixo {ax}.")
        
    report_lines.append("\n3. MÚSCULOS")
    for var in vars_muscles:
        y_count = counts['Young']['muscles'][var]
        o_count = counts['Old']['muscles'][var]
        report_lines.append(f"  {var:<15} — Jovens: {y_count:<2} | Idosos: {o_count:<2}")
        if y_count <= 1: report_lines.append(f"    -> AVISO: Grupo Young possui apenas {y_count} paciente(s) para {var}.")
        if o_count <= 1: report_lines.append(f"    -> AVISO: Grupo Old possui apenas {o_count} paciente(s) para {var}.")
        
    report_lines.append("\n* Nota 1: O componente vertical do CoM foi centralizado em relação à média individual para comparar a excursão vertical independentemente da altura corporal.")
    report_lines.append("* Nota 2: Para reduzir a influência da escala corporal nos músculos, cada curva individual foi centralizada pela subtração da média temporal (variação relativa).")
    report_lines.append("* Nota 3: Os ciclos da marcha foram estimados cinematicamente a partir dos picos de flexão do quadril direito.")
    report_lines.append("==================================================\n")
    
    # Imprimir no console
    report_text = "\n".join(report_lines)
    print(report_text)
    
    # Salvar em arquivo texto
    with open(RESULTADOS_GRP_DIR / 'Relatorio_Auditoria_Grupo.txt', 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"Processamento completo! Verifique a pasta: {RESULTADOS_GRP_DIR}")

if __name__ == "__main__":
    main()
