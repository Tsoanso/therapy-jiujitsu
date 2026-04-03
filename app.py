import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io

# --- CONFIGURAÇÃO VISUAL ---
PALETA = {'fundo': '#F0F2F6', 'roxo': '#5A2D82', 'card': '#FFFFFF'}
CORES_FAIXAS = {
    "Branca": "#FFFFFF", "Cinza": "#808080", "Amarela": "#FFFF00", 
    "Laranja": "#FFA500", "Verde": "#008000", "Azul": "#0000FF", 
    "Roxa": "#800080", "Marrom": "#8B4513", "Preta": "#000000"
}

st.set_page_config(page_title="Therapy Jiu-Jitsu", layout="wide")

# --- BANCO DE DADOS COM REPARO DE COLUNAS ---
def setup_db():
    conn = sqlite3.connect('therapy_final.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Criar tabelas se não existirem
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, tipo TEXT, nome TEXT, faixa TEXT, graus INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS historico_graduacao (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, faixa TEXT, graus INTEGER, data_promocao TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS grade_horarios (id INTEGER PRIMARY KEY AUTOINCREMENT, dia_semana TEXT, hora TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_nome TEXT, data TEXT, horario TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS pagamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, mes TEXT, ano TEXT, valor REAL)')

    # --- LÓGICA DE MIGRAÇÃO (ADICIONAR COLUNAS FALTANTES) ---
    # Verificar checkins
    cursor.execute("PRAGMA table_info(checkins)")
    colunas_checkin = [col[1] for col in cursor.fetchall()]
    if 'status' not in colunas_checkin:
        cursor.execute('ALTER TABLE checkins ADD COLUMN status TEXT DEFAULT "Pendente"')

    # Verificar pagamentos
    cursor.execute("PRAGMA table_info(pagamentos)")
    colunas_pagto = [col[1] for col in cursor.fetchall()]
    novas_colunas_pagto = {
        'data_envio': 'TEXT',
        'comprovante': 'BLOB',
        'status': 'TEXT DEFAULT "Pendente"'
    }
    for col_name, col_type in novas_colunas_pagto.items():
        if col_name not in colunas_pagto:
            cursor.execute(f'ALTER TABLE pagamentos ADD COLUMN {col_name} {col_type}')
    
    conn.commit()
    return conn, cursor

conn, cursor = setup_db()

# --- USUÁRIOS PADRÃO ---
def init_users():
    users = [('admin', '123', 'professor', 'Professor ADM', 'Preta', 0),
             ('aluno1', '123', 'aluno', 'Aluno 1', 'Branca', 0),
             ('aluno2', '123', 'aluno', 'Aluno 2', 'Branca', 0)]
    for u, s, t, n, f, g in users:
        cursor.execute("SELECT 1 FROM usuarios WHERE username=?", (u,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?, ?)", (u, s, t, n, f, g))
    conn.commit()

init_users()

# --- AUXILIARES ---
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
DIAS_LISTA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
DIAS_MAP = {i: dia for i, dia in enumerate(DIAS_LISTA)}

def format_date_to_sort(date_str):
    try: return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except: return "0000-00-00"

# --- LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🥋 Therapy Jiu-Jitsu")
    with st.form("login_form"):
        u, s = st.text_input("Usuário"), st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            cursor.execute("SELECT * FROM usuarios WHERE username=? AND senha=?", (u, s))
            user = cursor.fetchone()
            if user:
                st.session_state.update({'logged_in': True, 'user_id': user[0], 'user_type': user[2], 'nome_real': user[3]})
                st.rerun()
            else: st.error("Acesso Negado.")
else:
    with st.sidebar:
        st.write(f"**OSS, {st.session_state['nome_real']}**")
        if st.button("Sair"):
            st.session_state.clear(); st.rerun()

    # --- PERFIL PROFESSOR ---
    if st.session_state['user_type'] == 'professor':
        tabs = st.tabs(["📊 Mural & Ranking", "🎓 Alunos", "📅 Grade", "💰 Financeiro"])
        
        with tabs[0]:
            c1, c2 = st.columns(2)
            with c1:
                st.header("🔔 Check-ins")
                df_p = pd.read_sql_query("SELECT id, aluno_nome, horario FROM checkins WHERE status='Pendente'", conn)
                for _, row in df_p.iterrows():
                    with st.expander(f"Validar: {row['aluno_nome']}"):
                        if st.button("Confirmar Presença", key=f"cp_{row['id']}"):
                            cursor.execute("UPDATE checkins SET status='Confirmado' WHERE id=?", (row['id'],)); conn.commit(); st.rerun()
            with c2:
                st.header("🏆 Ranking")
                df_r = pd.read_sql_query("SELECT aluno_nome as Aluno, COUNT(*) as Presenças FROM checkins WHERE status='Confirmado' GROUP BY aluno_nome ORDER BY Presenças DESC", conn)
                st.dataframe(df_r, use_container_width=True, hide_index=True)

        with tabs[1]:
            st.header("Gestão de Alunos")
            cursor.execute("SELECT nome, username, faixa, graus FROM usuarios WHERE tipo='aluno'")
            for n, u, f, g in cursor.fetchall():
                with st.expander(f"👤 {n}"):
                    new_n = st.text_input("Nome", n, key=f"en_{u}")
                    if st.button("Salvar Nome", key=f"sn_{u}"):
                        cursor.execute("UPDATE usuarios SET nome=? WHERE username=?", (new_n, u)); conn.commit(); st.rerun()
                    st.write("---")
                    with st.form(f"grad_{u}"):
                        nf = st.selectbox("Nova Faixa", list(CORES_FAIXAS.keys()), index=list(CORES_FAIXAS.keys()).index(f))
                        ng = st.slider("Graus", 0, 4, g)
                        if st.form_submit_button("Graduar"):
                            dt = datetime.now().strftime("%d/%m/%Y")
                            cursor.execute("UPDATE usuarios SET faixa=?, graus=? WHERE username=?", (nf, ng, u))
                            cursor.execute("INSERT INTO historico_graduacao (username, faixa, graus, data_promocao) VALUES (?, ?, ?, ?)", (u, nf, ng, dt))
                            conn.commit(); st.rerun()

        with tabs[3]:
            st.header("💰 Validação de Pagamentos")
            cursor.execute("""SELECT p.id, u.nome, p.mes, p.valor, p.comprovante 
                              FROM pagamentos p JOIN usuarios u ON p.username = u.username 
                              WHERE p.status = 'Pendente'""")
            p_fin = cursor.fetchall()
            if not p_fin: st.info("Nenhum comprovante pendente.")
            for pid, pnome, pmes, pvalor, pimg in p_fin:
                with st.expander(f"Pagamento: {pnome} ({pmes})"):
                    st.write(f"Valor: R$ {pvalor}")
                    if pimg: st.image(pimg, width=400)
                    cf1, cf2 = st.columns(2)
                    if cf1.button("✅ Confirmar", key=f"fy_{pid}"):
                        cursor.execute("UPDATE pagamentos SET status='Confirmado' WHERE id=?", (pid,)); conn.commit(); st.rerun()
                    if cf2.button("❌ Recusar", key=f"fn_{pid}"):
                        cursor.execute("DELETE FROM pagamentos WHERE id=?", (pid,)); conn.commit(); st.rerun()

    # --- PERFIL ALUNO ---
    else:
        menu = st.sidebar.radio("Menu", ["Check-in", "Minha Evolução", "Financeiro", "Configurações"])
        
        if menu == "Financeiro":
            st.header("💰 Enviar Pagamento")
            with st.form("envio_compr", clear_on_submit=True):
                m_sel = st.selectbox("Mês Referente", MESES)
                v_sel = st.number_input("Valor Pago R$", value=150.0)
                file = st.file_uploader("Foto do Comprovante", type=['jpg', 'jpeg', 'png'])
                if st.form_submit_button("Enviar"):
                    if file:
                        img_data = file.read()
                        cursor.execute("INSERT INTO pagamentos (username, mes, ano, valor, data_envio, comprovante, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                       (st.session_state['user_id'], m_sel, str(datetime.now().year), v_sel, datetime.now().strftime("%d/%m/%Y"), img_data, "Pendente"))
                        conn.commit(); st.success("Comprovante enviado!")
                    else: st.error("Selecione a imagem.")
            
            st.subheader("Histórico Financeiro")
            df_hist_f = pd.read_sql_query(f"SELECT mes, valor, status FROM pagamentos WHERE username='{st.session_state['user_id']}'", conn)
            st.dataframe(df_hist_f, use_container_width=True, hide_index=True)

        elif menu == "Check-in":
            st.header("Check-in")
            agora = datetime.now()
            dia = DIAS_MAP[agora.weekday()]
            cursor.execute("SELECT hora FROM grade_horarios WHERE dia_semana=?", (dia,))
            aulas = [h[0] for h in cursor.fetchall() if h[0] >= agora.strftime("%H:%M")]
            if aulas:
                aula = st.selectbox("Próximas aulas", aulas)
                if st.button("Confirmar Presença"):
                    cursor.execute("INSERT INTO checkins (aluno_nome, data, horario, status) VALUES (?, ?, ?, ?)", 
                                   (st.session_state['nome_real'], agora.strftime("%d/%m/%Y"), f"{dia} - {aula}", "Pendente"))
                    conn.commit(); st.success("Check-in enviado!")
            else: st.warning("Sem aulas disponíveis agora.")

        elif menu == "Minha Evolução":
            st.header("🥋 Minha Evolução")
            cursor.execute("SELECT faixa, graus, data_promocao FROM historico_graduacao WHERE username=?", (st.session_state['user_id'],))
            hist = sorted(cursor.fetchall(), key=lambda x: format_date_to_sort(x[2]), reverse=True)
            for f, g, d in hist:
                st.write(f"🔹 **{d}**: {f} - {g} graus")

        elif menu == "Configurações":
            st.header("⚙️ Configurações")
            with st.expander("Alterar Senha"):
                ns = st.text_input("Nova Senha", type="password")
                if st.button("Atualizar"):
                    cursor.execute("UPDATE usuarios SET senha=? WHERE username=?", (ns, st.session_state['user_id']))
                    conn.commit(); st.success("Senha alterada!")
