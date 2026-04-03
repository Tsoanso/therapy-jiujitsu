import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURAÇÕES E CORES ---
CORES_MAPA = {
    "Branca": "#FFFFFF", "Cinza": "#808080", "Amarela": "#FFFF00", 
    "Laranja": "#FFA500", "Verde": "#008000", "Azul": "#0000FF", 
    "Roxa": "#800080", "Marrom": "#8B4513", "Preta": "#000000"
}
CORES_FAIXAS = list(CORES_MAPA.keys())
DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

st.set_page_config(page_title="Therapy Jiu-Jitsu", layout="wide")

# --- BANCO DE DADOS ---
def setup_db():
    conn = sqlite3.connect('therapy_final.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Criar Tabelas
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, tipo TEXT, nome TEXT, faixa TEXT, graus INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS historico_graduacao (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, faixa TEXT, graus INTEGER, data_promocao TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS grade_horarios (id INTEGER PRIMARY KEY AUTOINCREMENT, dia_semana TEXT, hora TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_nome TEXT, data TEXT, horario TEXT, status TEXT DEFAULT "Pendente")')
    cursor.execute('''CREATE TABLE IF NOT EXISTS pagamentos 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, mes TEXT, ano TEXT, valor REAL, 
                   data_envio TEXT, comprovante BLOB, status TEXT DEFAULT "Pendente")''')
    
    # Garantir usuários iniciais para teste
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
    with st.form("login_form"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            cursor.execute("SELECT * FROM usuarios WHERE username=? AND senha=?", (u, s))
            user = cursor.fetchone()
            if user:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user[0]
                st.session_state['user_type'] = user[2] # Aqui define se é 'professor' ou 'aluno'
                st.session_state['nome_real'] = user[3]
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
else:
    # --- BARRA LATERAL (COMUM PARA TODOS) ---
    with st.sidebar:
        st.header("Menu")
        st.write(f"Usuário: **{st.session_state['nome_real']}**")
        st.write(f"Perfil: {st.session_state['user_type'].capitalize()}")
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()

    # --- 1. VISÃO DO PROFESSOR ---
    if st.session_state['user_type'] == 'professor':
        tabs = st.tabs(["📊 Mural", "🎓 Alunos", "📅 Grade", "💰 Financeiro"])

        with tabs[0]: # Mural Professor
            st.subheader("Check-ins Pendentes")
            df_c = pd.read_sql_query("SELECT id, aluno_nome, horario FROM checkins WHERE status='Pendente'", conn)
            if df_c.empty: st.info("Nenhum check-in pendente.")
            for _, r in df_c.iterrows():
                if st.button(f"Confirmar {r['aluno_nome']} ({r['horario']})", key=f"c_{r['id']}"):
                    cursor.execute("UPDATE checkins SET status='Confirmado' WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
            
            st.divider()
            st.subheader("🏆 Ranking de Presença")
            df_rank = pd.read_sql_query("SELECT aluno_nome as Aluno, COUNT(*) as Aulas FROM checkins WHERE status='Confirmado' GROUP BY Aluno ORDER BY Aulas DESC", conn)
            st.table(df_rank)

        with tabs[1]: # Gestão de Alunos
            st.header("Fichas de Alunos")
            cursor.execute("SELECT nome, username, faixa, graus FROM usuarios WHERE tipo='aluno'")
            alunos = cursor.fetchall()
            for n, u_id, f, g in alunos:
                with st.expander(f"🥋 {n} (Faixa {f})"):
                    # --- PARTE 1: REGISTRAR NOVA PROMOÇÃO ---
                    st.subheader("Nova Graduação")
                    col_f, col_g = st.columns(2)
                    nova_f = col_f.selectbox("Alterar Faixa", CORES_FAIXAS, index=CORES_FAIXAS.index(f), key=f"f_{u_id}")
                    novo_g = col_g.slider("Graus", 0, 4, g, key=f"g_{u_id}")
                    
                    if st.button("Registrar Promoção", key=f"p_{u_id}"):
                        hoje = datetime.now().strftime("%d/%m/%Y")
                        cursor.execute("UPDATE usuarios SET faixa=?, graus=? WHERE username=?", (nova_f, novo_g, u_id))
                        cursor.execute("INSERT INTO historico_graduacao (username, faixa, graus, data_promocao) VALUES (?, ?, ?, ?)", (u_id, nova_f, novo_g, hoje))
                        conn.commit()
                        st.success("Promoção registrada!")
                        st.rerun()

                    st.divider()

                    # --- PARTE 2: EDITAR/REMOVER HISTÓRICO EXISTENTE ---
                    st.subheader("Histórico de Evolução")
                    cursor.execute("SELECT id, data_promocao, faixa, graus FROM historico_graduacao WHERE username=? ORDER BY id DESC", (u_id,))
                    historico_aluno = cursor.fetchall()
                    
                    if not historico_aluno:
                        st.info("Nenhum registro de evolução encontrado para este aluno.")
                    else:
                        for h_id, h_data, h_faixa, h_graus in historico_aluno:
                            col_info, col_del = st.columns([4, 1])
                            col_info.write(f"🗓️ **{h_data}** — {h_faixa} ({h_graus} graus)")
                            
                            # Botão para deletar o registro específico do histórico
                            if col_del.button("🗑️", key=f"del_h_{h_id}", help="Excluir este registro do histórico"):
                                cursor.execute("DELETE FROM historico_graduacao WHERE id=?", (h_id,))
                                conn.commit()
                                st.warning("Registro de histórico removido!")

        with tabs[2]: # Grade de Horários
            st.header("Gerenciar Horários")
            with st.form("add_grade"):
                d = st.selectbox("Dia", DIAS_SEMANA)
                h = st.text_input("Horário (ex: 19:00)")
                if st.form_submit_button("Adicionar Aula"):
                    cursor.execute("INSERT INTO grade_horarios (dia_semana, hora) VALUES (?,?)", (d, h))
                    conn.commit()
                    st.rerun()
            
            df_g = pd.read_sql_query("SELECT * FROM grade_horarios", conn)
            for _, r in df_g.iterrows():
                col_g1, col_g2 = st.columns([4,1])
                col_g1.write(f"📅 {r['dia_semana']} - {r['hora']}")
                if col_g2.button("🗑️", key=f"del_g_{r['id']}"):
                    cursor.execute("DELETE FROM grade_horarios WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()

        with tabs[3]: # Financeiro Professor
            st.header("Controle de Mensalidades")
            cursor.execute("SELECT p.id, u.nome, p.mes, p.valor, p.comprovante, p.status FROM pagamentos p JOIN usuarios u ON p.username = u.username")
            pags = cursor.fetchall()
            for pid, pnome, pmes, pval, pimg, pstat in pags:
                with st.expander(f"{pnome} - {pmes} ({pstat})"):
                    st.write(f"Valor: R$ {pval}")
                    if pimg: st.image(pimg, width=250)
                    if pstat == 'Pendente':
                        if st.button("Aprovar", key=f"ap_{pid}"):
                            cursor.execute("UPDATE pagamentos SET status='Confirmado' WHERE id=?", (pid,)); conn.commit(); st.rerun()

    # --- 2. VISÃO DO ALUNO ---
    elif st.session_state['user_type'] == 'aluno':
        t_al = st.tabs(["📊 Mural", "👤 Cadastro", "💰 Financeiro", "🥋 Evolução"])

        with t_al[0]: # Mural Aluno (Check-in e Ranking)
            st.header("Check-in na Aula")
            df_grade_al = pd.read_sql_query("SELECT * FROM grade_horarios", conn)
            if df_grade_al.empty:
                st.warning("Nenhuma aula disponível na grade.")
            else:
                aula_selecionada = st.selectbox("Escolha a aula", df_grade_al['dia_semana'] + " - " + df_grade_al['hora'])
                if st.button("Fazer Check-in"):
                    cursor.execute("INSERT INTO checkins (aluno_nome, data, horario, status) VALUES (?, ?, ?, 'Pendente')", 
                                   (st.session_state['nome_real'], datetime.now().strftime("%d/%m/%Y"), aula_selecionada))
                    conn.commit()
                    st.success("Check-in enviado para o mestre!")

            st.divider()
            st.subheader("Sua Posição no Ranking")
            df_rank_al = pd.read_sql_query("SELECT aluno_nome, COUNT(*) as Aulas FROM checkins WHERE status='Confirmado' GROUP BY aluno_nome ORDER BY Aulas DESC", conn)
            try:
                pos = df_rank_al[df_rank_al['aluno_nome'] == st.session_state['nome_real']].index[0] + 1
                st.metric("Sua Posição", f"{pos}º Lugar")
            except:
                st.info("Participe das aulas para entrar no ranking.")
            st.dataframe(df_rank_al, use_container_width=True)

        with t_al[1]: # Cadastro Aluno
            st.header("Meus Dados Pessoais")
            with st.form("edit_perfil"):
                nome_n = st.text_input("Nome Completo", st.session_state['nome_real'])
                senha_a = st.text_input("Senha Atual", type="password")
                senha_n = st.text_input("Nova Senha (deixe em branco para não mudar)", type="password")
                if st.form_submit_button("Salvar Alterações"):
                    cursor.execute("SELECT senha FROM usuarios WHERE username=?", (st.session_state['user_id'],))
                    if cursor.fetchone()[0] == senha_a:
                        sf = senha_n if senha_n else senha_a
                        cursor.execute("UPDATE usuarios SET nome=?, senha=? WHERE username=?", (nome_n, sf, st.session_state['user_id']))
                        conn.commit()
                        st.success("Dados atualizados!")
                    else: st.error("Senha atual incorreta.")

        with t_al[2]: # Financeiro Aluno
            st.header("Enviar Comprovante")
            with st.form("pag_aluno"):
                mes_ref = st.selectbox("Mês de Referência", ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"])
                valor_p = st.number_input("Valor Pago", value=150.0)
                file_comp = st.file_uploader("Foto do Comprovante", type=['jpg', 'png', 'jpeg'])
                if st.form_submit_button("Enviar para o Mestre"):
                    if file_comp:
                        cursor.execute("INSERT INTO pagamentos (username, mes, ano, valor, data_envio, comprovante, status) VALUES (?,?,?,?,?,?,?)",
                                       (st.session_state['user_id'], mes_ref, "2024", valor_p, datetime.now().strftime("%d/%m/%Y"), file_comp.read(), 'Pendente'))
                        conn.commit()
                        st.success("Enviado com sucesso!")
                    else: st.warning("Por favor, anexe o comprovante.")

        with t_al[3]: # Evolução (Faixa Visual)
            st.header("Minha Evolução")
            cursor.execute("SELECT data_promocao, faixa, graus FROM historico_graduacao WHERE username=? ORDER BY id DESC", (st.session_state['user_id'],))
            hist = cursor.fetchall()
            if not hist: st.info("Sua jornada está começando! Nenhuma promoção registrada ainda.")
            for d, fx, gr in hist:
                cor_f = CORES_MAPA.get(fx, "#333")
                txt_f = "#000" if fx in ["Branca", "Amarela", "Cinza"] else "#FFF"
                st.markdown(f"""
                    <div style="background:{cor_f}; color:{txt_f}; padding:20px; border-radius:10px; border:2px solid #333; margin-bottom:15px; display:flex; justify-content:space-between; align-items:center; font-weight:bold; box-shadow: 4px 4px 10px rgba(0,0,0,0.1);">
                        <span style="font-size:1.2em;">🗓️ {d} — FAIXA {fx.upper()}</span>
                        <div style="background:#000; color:#FFF; padding:8px 15px; border-left:8px solid red; letter-spacing: 5px;">
                            {'I ' * gr if gr > 0 else 'SEM GRAUS'}
                        </div>
                    </div>
                """, unsafe_allow_html=True)

    else:
        st.warning("Tipo de usuário não reconhecido. Contate o administrador.")
