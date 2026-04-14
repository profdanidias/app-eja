import os
from datetime import datetime
import io

from flask import (
    Flask, render_template, request, redirect,
    session, jsonify, send_file
)
import psycopg2
import psycopg2.extras
import requests
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib.pagesizes import letter

# ================= CONFIGURAÇÃO BÁSICA =================

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

# E-mail(s) da gestora
GESTORES = ["professoradanidias@gmail.com"]

# URL do banco (Render → Environment → DATABASE_URL)
DATABASE_URL = os.environ.get("DATABASE_URL")


# ================= CONEXÃO E TABELAS =================

def conectar():
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn


def criar_tabelas():
    conn = conectar()
    cur = conn.cursor()

    # Tabela de respostas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS respostas (
            id SERIAL PRIMARY KEY,
            usuario_id TEXT,
            municipio_id TEXT,
            municipio_nome TEXT,
            estado TEXT,
            formador_local TEXT,
            pba TEXT,
            pba_qtd INTEGER,
            eja_alfabetizacao TEXT,
            eja_alfabetizacao_qtd INTEGER,
            eja_anos_iniciais TEXT,
            eja_anos_iniciais_qtd INTEGER,
            jan INTEGER, fev INTEGER, mar INTEGER, abr INTEGER,
            mai INTEGER, jun INTEGER, jul INTEGER, ago INTEGER, setm INTEGER,
            data_envio TIMESTAMP
        )
    """)

    # Tabela de estado fixo por usuário (apenas formadores)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuario_estado (
            email TEXT PRIMARY KEY,
            estado TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


criar_tabelas()


# ================= ESTADO FIXO (APENAS FORMADORES) =================

def obter_estado_fixo(email):
    if not email:
        return None
    # Gestora NÃO tem estado fixo
    if email in GESTORES:
        return None

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM usuario_estado WHERE email = %s", (email,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def definir_estado_fixo(email, estado):
    if not email or not estado:
        return
    # Não fixa estado para gestora
    if email in GESTORES:
        return

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuario_estado (email, estado)
        VALUES (%s, %s)
        ON CONFLICT (email) DO UPDATE SET estado = EXCLUDED.estado
    """, (email, estado))
    conn.commit()
    conn.close()


# ================= LOGIN / FLUXO INICIAL =================

@app.route("/")
def auto_login():
    nome = request.args.get("nome")
    email = request.args.get("email")

    if nome and email:
        session["nome"] = nome
        session["email"] = email.lower()
        return redirect("/funcao")

    return "Acesso inválido"


@app.route("/funcao", methods=["GET", "POST"])
def funcao():
    if request.method == "POST":
        session["funcao"] = request.form.get("funcao")

        if session["funcao"] != "Formador Regional":
            return render_template("bloqueado.html")

        return redirect("/formulario")

    return render_template("funcao.html")


@app.route("/formulario")
def formulario():
    email = session.get("email")
    if not email:
        return redirect("/")

    is_gestor = email in GESTORES
    estado_fixo = obter_estado_fixo(email)

    # Para gestora, carregamos a lista de estados do IBGE
    estados = []
    if is_gestor:
        try:
            r = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados")
            if r.status_code == 200:
                estados = sorted(r.json(), key=lambda x: x["sigla"])
        except Exception:
            estados = []

    return render_template(
        "formulario.html",
        is_gestor=is_gestor,
        estado_fixo=estado_fixo,
        estados=estados
    )


# ================= IBGE =================

@app.route("/estados")
def estados():
    r = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados")
    return jsonify(r.json())


@app.route("/municipios/<uf>")
def municipios(uf):
    r = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios")
    return jsonify(r.json())


# ================= API DADOS ANTERIORES MUNICÍPIO =================

@app.route("/api/dados_municipio/<municipio_id>")
def api_dados_municipio(municipio_id):
    usuario = session.get("nome")
    if not usuario:
        return jsonify({"existe": False})

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            formador_local,
            pba, pba_qtd,
            eja_alfabetizacao, eja_alfabetizacao_qtd,
            eja_anos_iniciais, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm
        FROM respostas
        WHERE usuario_id = %s AND municipio_id = %s
        ORDER BY data_envio DESC
        LIMIT 1
    """, (usuario, municipio_id))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"existe": False})

    dados = {
        "existe": True,
        "formador_local": row[0] or "",
        "pba": row[1] or "",
        "pba_qtd": row[2] or 0,
        "eja_alf": row[3] or "",
        "eja_alf_qtd": row[4] or 0,
        "eja_ai": row[5] or "",
        "eja_ai_qtd": row[6] or 0,
        "meses": {
            "jan": row[7] or 0,
            "fev": row[8] or 0,
            "mar": row[9] or 0,
            "abr": row[10] or 0,
            "mai": row[11] or 0,
            "jun": row[12] or 0,
            "jul": row[13] or 0,
            "ago": row[14] or 0,
            "setm": row[15] or 0
        }
    }
    return jsonify(dados)


# ================= SALVAR RESPOSTAS =================

@app.route("/salvar", methods=["POST"])
def salvar():
    conn = conectar()
    cur = conn.cursor()

    usuario = session.get("nome")
    email = session.get("email")
    estado = request.form.get("estado")

    # Fixa estado apenas para formadores
    definir_estado_fixo(email, estado)

    # Municípios selecionados (no novo formulário é um único name="municipios")
    municipios = request.form.getlist("municipios")
    data_envio = datetime.now()

    ids_inseridos = []

    for m in municipios:
        cur.execute("""
            INSERT INTO respostas (
                usuario_id, municipio_id, municipio_nome, estado,
                formador_local,
                pba, pba_qtd,
                eja_alfabetizacao, eja_alfabetizacao_qtd,
                eja_anos_iniciais, eja_anos_iniciais_qtd,
                jan, fev, mar, abr, mai, jun, jul, ago, setm,
                data_envio
            ) VALUES (
                %s,%s,%s,%s,
                %s,
                %s,%s,
                %s,%s,
                %s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s
            )
        """, (
            usuario,
            m,
            request.form.get(f"nome_{m}") or "",
            estado,
            request.form.get(f"formador_local_{m}") or "",
            request.form.get(f"pba_{m}") or "",
            int(request.form.get(f"pba_qtd_{m}") or 0),
            request.form.get(f"eja_alf_{m}") or "",
            int(request.form.get(f"eja_alf_qtd_{m}") or 0),
            request.form.get(f"eja_ai_{m}") or "",
            int(request.form.get(f"eja_ai_qtd_{m}") or 0),
            int(request.form.get(f"jan_{m}") or 0),
            int(request.form.get(f"fev_{m}") or 0),
            int(request.form.get(f"mar_{m}") or 0),
            int(request.form.get(f"abr_{m}") or 0),
            int(request.form.get(f"mai_{m}") or 0),
            int(request.form.get(f"jun_{m}") or 0),
            int(request.form.get(f"jul_{m}") or 0),
            int(request.form.get(f"ago_{m}") or 0),
            int(request.form.get(f"setm_{m}") or 0),
            data_envio
        ))

        cur.execute("SELECT LASTVAL()")
        last_id = cur.fetchone()[0]
        ids_inseridos.append(last_id)

    conn.commit()
    conn.close()

    session["ids_ultimo_envio"] = ids_inseridos

    return redirect("/resumo_envio")


# ================= RESUMO / FINALIZAÇÃO =================

@app.route("/resumo_envio")
def resumo_envio():
    ids = session.get("ids_ultimo_envio")
    if not ids:
        return redirect("/formulario")

    conn = conectar()
    cur = conn.cursor()
    query = f"""
        SELECT municipio_nome, estado, formador_local,
               pba_qtd, eja_alfabetizacao_qtd, eja_anos_iniciais_qtd,
               jan, fev, mar, abr, mai, jun, jul, ago, setm,
               data_envio
        FROM respostas
        WHERE id = ANY(%s)
        ORDER BY data_envio DESC
    """
    cur.execute(query, (ids,))
    rows = cur.fetchall()
    conn.close()

    dados = []
    for r in rows:
        dados.append({
            "municipio": r[0],
            "estado": r[1],
            "formador_local": r[2],
            "pba": r[3],
            "eja_alf": r[4],
            "eja_ai": r[5],
            "meses": [r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13], r[14]],
            "data": r[15].strftime("%d/%m/%Y %H:%M") if r[15] else ""
        })

    return render_template("resumo_envio.html", dados=dados)


@app.route("/finalizar_envio", methods=["POST"])
def finalizar_envio():
    session.pop("ids_ultimo_envio", None)
    return render_template("mensagem_final.html")


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            usuario_id, municipio_nome, estado, formador_local,
            pba_qtd, eja_alfabetizacao_qtd, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm,
            data_envio, municipio_id
        FROM respostas
        ORDER BY data_envio DESC
    """)
    rows = cur.fetchall()
    conn.close()

    dados = []
    estados_set = set()
    formadores_set = set()

    for r in rows:
        meses = [
            r[7] or 0, r[8] or 0, r[9] or 0, r[10] or 0, r[11] or 0,
            r[12] or 0, r[13] or 0, r[14] or 0, r[15] or 0
        ]
        dados.append({
            "formador": r[0],
            "municipio": r[1],
            "estado": r[2],
            "formador_local": r[3],
            "pba": r[4] or 0,
            "eja_alf": r[5] or 0,
            "eja_ai": r[6] or 0,
            "meses": meses,
            "total": sum(meses),
            "data": r[16].strftime("%d/%m/%Y %H:%M") if r[16] else "",
            "municipio_id": r[17]
        })
        if r[2]:
            estados_set.add(r[2])
        if r[0]:
            formadores_set.add(r[0])

    estados_lista = sorted(list(estados_set))
    formadores_lista = sorted(list(formadores_set))

    return render_template(
        "dashboard.html",
        dados=dados,
        estados_lista=estados_lista,
        formadores_lista=formadores_lista
    )


# ================= API DADOS INICIAIS (GRÁFICOS) =================

@app.route("/api/dashboard_data")
def dashboard_data():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT estado,
               SUM(pba_qtd),
               SUM(eja_alfabetizacao_qtd),
               SUM(eja_anos_iniciais_qtd),
               SUM(jan), SUM(fev), SUM(mar), SUM(abr), SUM(mai),
               SUM(jun), SUM(jul), SUM(ago), SUM(setm)
        FROM respostas
        GROUP BY estado
    """)
    rows = cur.fetchall()
    conn.close()

    estados = []
    pba = []
    eja_alf = []
    eja_ai = []
    meses = []

    for r in rows:
        estados.append(r[0])
        pba.append(r[1] or 0)
        eja_alf.append(r[2] or 0)
        eja_ai.append(r[3] or 0)
        meses.append([x or 0 for x in r[4:]])

    return jsonify({
        "estados": estados,
        "pba": pba,
        "eja_alf": eja_alf,
        "eja_ai": eja_ai,
        "meses": meses
    })


# ================= MAPA BRASIL POR MÊS =================

MESES_COLUNAS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "setm"]


def coluna_mes_atual():
    mes_idx = datetime.now().month
    if mes_idx < 1:
        mes_idx = 1
    if mes_idx > 9:
        mes_idx = 9
    return MESES_COLUNAS[mes_idx - 1]


@app.route("/api/mapa")
def api_mapa():
    coluna = coluna_mes_atual()
    return _dados_mapa_por_coluna(coluna)


@app.route("/api/mapa_mes/<coluna>")
def api_mapa_mes(coluna):
    if coluna not in MESES_COLUNAS:
        return jsonify([])

    return _dados_mapa_por_coluna(coluna)


def _dados_mapa_por_coluna(coluna):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT estado, SUM(COALESCE({coluna}, 0))
        FROM respostas
        GROUP BY estado
    """)
    rows = cur.fetchall()
    conn.close()

    dados = [{"uf": r[0], "total": r[1] or 0} for r in rows if r[0]]
    return jsonify(dados)


# ================= API FILTROS =================

@app.route("/api/filtrar", methods=["POST"])
def filtrar():
    filtros = request.json
    estado = filtros.get("estado")
    formador = filtros.get("formador")
    municipio_raw = filtros.get("municipio")
    data_ini = filtros.get("data_ini")
    data_fim = filtros.get("data_fim")

    municipio_id = None
    if municipio_raw:
        partes = municipio_raw.split("|", 1)
        municipio_id = partes[0]

    query = """
        SELECT 
            usuario_id, municipio_nome, estado, formador_local,
            pba_qtd, eja_alfabetizacao_qtd, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm,
            data_envio, municipio_id
        FROM respostas
        WHERE 1=1
    """
    params = []

    if estado:
        query += " AND estado = %s"
        params.append(estado)

    if formador:
        query += " AND usuario_id = %s"
        params.append(formador)

    if municipio_id:
        query += " AND municipio_id = %s"
        params.append(municipio_id)

    if data_ini:
        query += " AND data_envio::date >= %s"
        params.append(data_ini)

    if data_fim:
        query += " AND data_envio::date <= %s"
        params.append(data_fim)

    query += " ORDER BY data_envio DESC"

    conn = conectar()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    tabela = []
    estados_totais = {}
    meses_por_estado = {}
    pba_total = 0
    eja_alf_total = 0
    eja_ai_total = 0

    for r in rows:
        meses = [
            r[7] or 0, r[8] or 0, r[9] or 0, r[10] or 0, r[11] or 0,
            r[12] or 0, r[13] or 0, r[14] or 0, r[15] or 0
        ]
        total_mes = sum(meses)

        tabela.append({
            "formador": r[0],
            "municipio": r[1],
            "estado": r[2],
            "pba": r[4] or 0,
            "eja_alf": r[5] or 0,
            "eja_ai": r[6] or 0,
            "data": r[16].strftime("%d/%m/%Y %H:%M") if r[16] else "",
            "municipio_id": r[17]
        })

        pba_total += r[4] or 0
        eja_alf_total += r[5] or 0
        eja_ai_total += r[6] or 0

        uf = r[2]
        if uf not in estados_totais:
            estados_totais[uf] = 0
        estados_totais[uf] += total_mes

        if uf not in meses_por_estado:
            meses_por_estado[uf] = [0] * 9
        for i in range(9):
            meses_por_estado[uf][i] += meses[i]

    return jsonify({
        "tabela": tabela,
        "cards": {
            "pba": pba_total,
            "eja_alf": eja_alf_total,
            "eja_ai": eja_ai_total,
            "geral": pba_total + eja_alf_total + eja_ai_total
        },
        "estados": estados_totais,
        "meses": meses_por_estado
    })


# ================= EXPORTAÇÃO EXCEL (GERAL) =================

@app.route("/exportar_excel")
def exportar_excel():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("""
        SELECT *
        FROM respostas
        ORDER BY data_envio DESC
    """, conn)
    conn.close()

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="dados.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ================= EXPORTAÇÃO EXCEL POR MUNICÍPIO =================

@app.route("/exportar_municipio/<municipio_id>")
def exportar_municipio(municipio_id):
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("""
        SELECT *
        FROM respostas
        WHERE municipio_id = %s
        ORDER BY data_envio DESC
    """, conn, params=(municipio_id,))
    conn.close()

    if df.empty:
        return "Nenhum registro encontrado para este município."

    nome_municipio = df["municipio_nome"].iloc[0] or "municipio"
    hoje = datetime.now().strftime("%Y-%m-%d")
    nome_arquivo = f"historico_{nome_municipio}_{hoje}.xlsx".replace(" ", "_")

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ================= EXPORTAÇÃO PDF =================

@app.route("/exportar_pdf")
def exportar_pdf():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("""
        SELECT *
        FROM respostas
        ORDER BY data_envio DESC
    """, conn)
    conn.close()

    output = io.BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=letter)

    tabela = [df.columns.tolist()] + df.values.tolist()
    pdf.build([Table(tabela)])
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="dados.pdf",
        mimetype="application/pdf"
    )


# ================= LIMPAR TODOS OS DADOS (APENAS TABELA RESPOSTAS) =================

@app.route("/limpar_tudo", methods=["POST"])
def limpar_tudo():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()
    cur.execute("DELETE FROM respostas")
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


# ================= CABEÇALHO DE RESPOSTA =================

@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)