import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io

# --- CONFIGURAÇÃO ---
CORES_FAIXAS = ["Branca", "Cinza", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"]

st.set_page_config(page_title="Therapy Jiu-Jitsu", layout="wide")

def setup_db():
    conn = sqlite3.connect('therapy_final.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # 1. Criação das Tabelas
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, tipo TEXT, nome TEXT, faixa TEXT, graus INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS historico_graduacao (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, faixa TEXT, graus INTEGER, data_promocao TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS grade_horarios (id INTEGER PRIMARY KEY AUTOINCREMENT, dia_semana TEXT, hora TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_nome TEXT, data TEXT, horario TEXT, status TEXT DEFAULT "Pendente")')
    cursor.execute('CREATE TABLE IF NOT EXISTS pagamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, mes TEXT, ano TEXT, valor REAL, data_envio TEXT, comprovante BLOB, status TEXT DEFAULT "Pendente")')

    # 2. Migração: Garante que as colunas novas existam caso o banco seja antigo
    cursor.execute("PRAGMA table_info(pagamentos)")
    colunas = [c[1] for c in cursor.fetchall()]
    if 'comprovante' not in colunas:
        cursor.execute('ALTER TABLE pagamentos ADD COLUMN comprovante BLOB')
    if 'data_envio' not in colunas:
        cursor.execute('ALTER TABLE pagamentos ADD COLUMN data_envio TEXT')

    # 3. Inserção de Perfis Padrão (Mestre e Aluno01)
    cursor.execute("SELECT * FROM usuarios WHERE username='mestre'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios VALUES ('mestre', '123', 'professor', 'Mestre Therapy', 'Preta', 3)")
    
    cursor.execute("SELECT * FROM usuarios WHERE username='aluno01'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios VALUES ('aluno01', '123', 'aluno', 'João Aluno', 'Branca', 0)")

    conn.commit()
    return conn, cursor

conn, cursor = setup_db()

# --- SISTEMA DE LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🥋 Therapy Jiu-Jitsu")
    with st.form("login"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            # CORREÇÃO: Removido o 'VALUES' que causava erro na imagem
            cursor.execute("SELECT * FROM usuarios WHERE username=? AND senha=?", (u, s))
            user = cursor.fetchone()
            if user:
                st.session_state.update({'logged_in': True, 'user_id': user[0], 'user_type': user[2], 'nome_real': user[3]})
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
else:
    with st.sidebar:
        st.write(f"OSS, **{st.session_state['nome_real']}**")
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()

    # --- INTERFACE PROFESSOR ---
    if st.session_state['user_type'] == 'professor':
        tabs = st.tabs(["📊 Mural", "🎓 Gestão de Alunos", "📅 Grade", "💰 Financeiro"])

        with tabs[1]: # Gestão de Alunos
            st.header("Alunos Cadastrados")
            cursor.execute("SELECT nome, username, faixa, graus FROM usuarios WHERE tipo='aluno'")
            for n, u_id, f, g in cursor.fetchall():
                with st.expander(f"👤 {n} (Atual: {f})"):
                    
                    # Alteração de Graduação
                    st.subheader("🛠️ Alterar Graduação Atual")
                    c1, c2 = st.columns(2)
                    nova_f = c1.selectbox("Nova Faixa", CORES_FAIXAS, index=CORES_FAIXAS.index(f), key=f"f_{u_id}")
                    novo_g = c2.slider("Graus", 0, 4, g, key=f"g_{u_id}")
                    
                    b1, b2 = st.columns(2)
                    if b1.button("✏️ Corrigir Atual", key=f"edit_{u_id}"):
                        cursor.execute("UPDATE usuarios SET faixa=?, graus=? WHERE username=?", (nova_f, novo_g, u_id))
                        conn.commit()
                        st.success("Dados atualizados!")
                        st.rerun()
                    
                    if b2.button("🏆 Registrar Promoção", key=f"prom_{u_id}"):
                        hoje = datetime.now().strftime("%d/%m/%Y")
                        cursor.execute("UPDATE usuarios SET faixa=?, graus=? WHERE username=?", (nova_f, novo_g, u_id))
                        cursor.execute("INSERT INTO historico_graduacao (username, faixa, graus, data_promocao) VALUES (?, ?, ?, ?)", (u_id, nova_f, novo_g, hoje))
                        conn.commit()
                        st.success("Promoção salva no histórico!")
                        st.rerun()

                    # Gerenciar Histórico (Excluir entradas)
                    st.write("---")
                    st.subheader("📜 Histórico de Graduações")
                    cursor.execute("SELECT id, data_promocao, faixa, graus FROM historico_graduacao WHERE username=? ORDER BY id DESC", (u_id,))
                    h_rows = cursor.fetchall()
                    for h_id, h_dt, h_fx, h_gr in h_rows:
                        hc1, hc2 = st.columns([3, 1])
                        hc1.write(f"📅 {h_dt} - {h_fx} ({h_gr} graus)")
                        if hc2.button("🗑️", key=f"del_h_{h_id}"):
                            cursor.execute("DELETE FROM historico_graduacao WHERE id=?", (h_id,))
                            conn.commit()
                            st.rerun()

        with tabs[3]: # Financeiro (Corrigido para evitar erros das imagens)
            st.header("Pagamentos Pendentes")
            cursor.execute("""SELECT p.id, u.nome, p.mes, p.valor, p.comprovante 
                              FROM pagamentos p JOIN usuarios u ON p.username = u.username 
                              WHERE p.status = 'Pendente'""")
            for pid, pnome, pmes, pvalor, pimg in cursor.fetchall():
                with st.expander(f"Pagamento: {pnome} - {pmes}"):
                    st.write(f"Valor: R$ {pvalor}")
                    if pimg: st.image(pimg, width=300)
                    if st.button("Aprovar", key=f"ap_{pid}"):
                        cursor.execute("UPDATE pagamentos SET status='Confirmado' WHERE id=?", (pid,))
                        conn.commit()
                        st.rerun()

    # --- INTERFACE ALUNO ---
    else:
        menu = st.sidebar.radio("Ir para", ["Check-in", "Evolução", "Financeiro"])
        
        if menu == "Evolução":
            st.header("🥋 Minha Trajetória")
            cursor.execute("SELECT faixa, graus, data_promocao FROM historico_graduacao WHERE username=? ORDER BY id DESC", (st.session_state['user_id'],))
            for f, g, d in cursor.fetchall():
                st.info(f"**{d}**: Faixa {f} - {g} graus")
        
        elif menu == "Financeiro":
            st.header("💰 Enviar Mensalidade")
            with st.form("pagto"):
                m = st.selectbox("Mês", ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho"])
                v = st.number_input("Valor", value=150.0)
                arq = st.file_uploader("Comprovante", type=['jpg', 'png'])
                if st.form_submit_button("Enviar"):
                    if arq:
                        cursor.execute("""INSERT INTO pagamentos (username, mes, ano, valor, data_envio, comprovante, status) 
                                          VALUES (?, ?, ?, ?, ?, ?, 'Pendente')""",
                                       (st.session_state['user_id'], m, "2024", v, datetime.now().strftime("%d/%m/%Y"), arq.read()))
                        conn.commit()
                        st.success("Enviado!")
