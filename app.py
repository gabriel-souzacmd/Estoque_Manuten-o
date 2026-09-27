import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression


# 1. CONF E BD


st.set_page_config(page_title="Controle de Frota", layout="wide")

@st.cache_resource
def conectar_banco():
    # Cria um arquivo real (frota_estoque.db) para não perder dados ao atualizar a tela
    conn = sqlite3.connect('frota_estoque.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS pecas (id_peca INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, quantidade_estoque INTEGER, estoque_minimo INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS caminhoes (id_caminhao INTEGER PRIMARY KEY AUTOINCREMENT, placa TEXT, km_atual REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_manutencao (id_manutencao INTEGER PRIMARY KEY AUTOINCREMENT, id_caminhao INTEGER, id_peca INTEGER, km_na_troca REAL, vida_util_peca REAL)''')
    conn.commit()
    return conn

conn = conectar_banco()

# 2. FUNÇÃO DA IA PREDITIVA

def prever_proxima_troca(id_caminhao, id_peca):
    df = pd.read_sql_query("SELECT km_na_troca, vida_util_peca FROM historico_manutencao WHERE id_caminhao = ? AND id_peca = ? ORDER BY km_na_troca ASC", conn, params=(id_caminhao, id_peca))
    if len(df) < 3:
        return None # Precisa de histórico mínimo para a regressão matemática funcionar
        
    X = df[['km_na_troca']]
    y = df['vida_util_peca']
    modelo = LinearRegression()
    modelo.fit(X, y)
    
    cursor = conn.cursor()
    cursor.execute("SELECT km_atual FROM caminhoes WHERE id_caminhao = ?", (id_caminhao,))
    km_atual = cursor.fetchone()[0]
    
    vida_util_prevista = modelo.predict(np.array([[km_atual]]))[0] 
    return round(km_atual + vida_util_prevista, 2)


# 3. INTERFACE GRÁFICA (UI Bem basicona) NO STREAMLIT


# CSS (A imagem que usei da empresa onde trabalho, apenas para exemplo)
st.markdown(
    """
    <style>
    /* Imagem de fundo com filtro azul escuro para manter o texto legível */
    .stApp {
        background-image: linear-gradient(rgba(4, 25, 50, 0.85), rgba(4, 25, 50, 0.85)), 
                          url("https://i0.wp.com/blogdocaminhoneiro.com/wp-content/uploads/2024/03/cordenonsi.jpg?ssl=1");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }

    /* Cores de textos gerais para azul bem claro/branco */
    .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp span, .stApp label {
        color: #E0F2FE !important;
    }

    /* Estilização das Abas de Navegação */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #0F172A;
        border-radius: 4px 4px 0px 0px;
        color: #93C5FD !important;
        border: 1px solid #1E3A8A;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1D4ED8 !important;
        color: #FFFFFF !important;
    }

    /* Estilização dos Botões */
    .stButton>button {
        background-color: #2563EB !important;
        color: white !important;
        border: 1px solid #3B82F6 !important;
        border-radius: 6px;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #1D4ED8 !important;
        border-color: #60A5FA !important;
        box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
    }
    
    /* Caixas de métricas e alertas */
    [data-testid="stMetricValue"] {
        color: #60A5FA !important;
    }
    .stAlert {
        background-color: rgba(30, 58, 138, 0.6) !important;
        border: 1px solid #3B82F6 !important;
        color: #EFF6FF !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Painel Logístico: Frota e Almoxarifado")

# Organiza o sistema em abas de navegação
aba_estoque, aba_os, aba_ia = st.tabs(["Visão de Estoque", "Lançar Ordem de Serviço", "Análise Preditiva"])

# ABA 1: ESTOQUE
with aba_estoque:
    st.header("Gestão de Peças e Recebimento")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Entrada de Material")
        nome_peca = st.text_input("Nome da Peça")
        qtd_inicial = st.number_input("Quantidade de Entrada", min_value=0, step=1)
        est_minimo = st.number_input("Estoque Mínimo (Alerta)", min_value=0, step=1)
        
        if st.button("Salvar Peça no Inventário"):
            if nome_peca:
                conn.execute("INSERT INTO pecas (nome, quantidade_estoque, estoque_minimo) VALUES (?, ?, ?)", (nome_peca, qtd_inicial, est_minimo))
                conn.commit()
                st.success("Recebimento registrado com sucesso!")
                st.rerun() # Atualiza a tela para exibir os dados novos
            
    with col2:
        st.subheader("Posição do Inventário Atual")
        df_estoque = pd.read_sql_query("SELECT id_peca as ID, nome as Peça, quantidade_estoque as Qtd, estoque_minimo as Minimo FROM pecas", conn)
        st.dataframe(df_estoque, use_container_width=True, hide_index=True)
        
        baixo_estoque = df_estoque[df_estoque['Qtd'] <= df_estoque['Minimo']]
        for _, row in baixo_estoque.iterrows():
            st.warning(f"Ação de Suprimentos Recomendada: Solicitar compra de {row['Peça']} (Restam {row['Qtd']} no armazém).")

# ABA 2: ORDEM DE SERVIÇO
with aba_os:
    st.header("Movimentação e Manutenção")
    df_caminhoes = pd.read_sql_query("SELECT * FROM caminhoes", conn)
    df_pecas_disp = pd.read_sql_query("SELECT * FROM pecas", conn)
    
    col_cad, col_baixa = st.columns(2)
    
    with col_cad:
        st.subheader("Cadastrar Novo Veículo")
        nova_placa = st.text_input("Placa do Caminhão (Ex: ABC-1234)")
        km_inic = st.number_input("Odômetro Atual", min_value=0.0)
        if st.button("Salvar Veículo"):
            if nova_placa:
                conn.execute("INSERT INTO caminhoes (placa, km_atual) VALUES (?, ?)", (nova_placa, km_inic))
                conn.commit()
                st.success("Veículo integrado à frota!")
                st.rerun()
            
    with col_baixa:
        st.subheader("Baixa de Peça / Fechar O.S.")
        if not df_caminhoes.empty and not df_pecas_disp.empty:
            cam_selecionado = st.selectbox("Veículo Destino", df_caminhoes['placa'])
            peca_selecionada = st.selectbox("Material Aplicado", df_pecas_disp['nome'])
            
            km_manutencao = st.number_input("KM Atual do Veículo no momento da troca", min_value=0.0, step=100.0)
            vida_util_ant = st.number_input("Vida Útil da Peça Retirada (KMs rodados)", min_value=0.0, step=100.0)
            
            if st.button("Finalizar Ordem de Serviço"):
                id_cam = df_caminhoes[df_caminhoes['placa'] == cam_selecionado]['id_caminhao'].values[0]
                id_peca = df_pecas_disp[df_pecas_disp['nome'] == peca_selecionada]['id_peca'].values[0]
                
                cursor = conn.cursor()
                cursor.execute("UPDATE pecas SET quantidade_estoque = quantidade_estoque - 1 WHERE id_peca = ?", (id_peca,))
                cursor.execute("UPDATE caminhoes SET km_atual = ? WHERE id_caminhao = ?", (km_manutencao, id_cam))
                cursor.execute("INSERT INTO historico_manutencao (id_caminhao, id_peca, km_na_troca, vida_util_peca) VALUES (?, ?, ?, ?)", (id_cam, id_peca, km_manutencao, vida_util_ant))
                conn.commit()
                
                st.success("Estoque atualizado e histórico salvo com sucesso!")
                st.rerun()

# ABA 3: INTELIGÊNCIA ARTIFICIAL
with aba_ia:
    st.header("Agendamento Preditivo")
    if not df_caminhoes.empty and not df_pecas_disp.empty:
        cam_pred = st.selectbox("Analisar Veículo", df_caminhoes['placa'])
        peca_pred = st.selectbox("Analisar Desgaste da Peça", df_pecas_disp['nome'])
        
        if st.button("Calcular Próxima Quebra"):
            id_cam_pred = df_caminhoes[df_caminhoes['placa'] == cam_pred]['id_caminhao'].values[0]
            id_peca_pred = df_pecas_disp[df_pecas_disp['nome'] == peca_pred]['id_peca'].values[0]
            
            previsao = prever_proxima_troca(id_cam_pred, id_peca_pred)
            if previsao:
                st.metric(label=f"Ocorrência de Falha Estimada no Odômetro:", value=f"{previsao:,.0f} km")
                st.info("Ação Operacional: Programar parada na oficina e fazer o picking (separação) do material no almoxarifado antes de atingir essa quilometragem.")
            else:
                st.error("Sem histórico suficiente. O sistema precisa de pelo menos 3 trocas desta mesma peça neste veículo para identificar o padrão de desgaste da frota.")
