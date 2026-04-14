from flask import Flask, render_template, request, redirect, session, jsonify, send_file
import sqlite3
import requests
import pandas as pd
import io
from datetime import datetime

from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

GESTORES = ["professoradanidias@gmail.com"]


# ================= BANCO =================
def conectar():
    return sqlite3.connect("database.db")


def criar_banco():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        data_envio TEXT
    )
    """)

    conn.commit()
    conn.close()


criar_banco()


# ================= LOGIN =================
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
    is_gestor = session.get("email") in GESTORES
    return render_template("formulario.html", is_gestor=is_gestor)


# ================= IBGE =================
@app.route("/estados")
def estados():
    return jsonify(requests.get(
        "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
    ).json())


@app.route("/municipios/<uf>")
def municipios(uf):
    return jsonify(requests.get(
        f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
    ).json())


# ================= SALVAR =================
@app.route("/salvar", methods=["POST"])
def salvar():

    conn = conectar()
    cur = conn.cursor()

    usuario = session.get("nome")
    estado = request.form.get("estado")
    municipios = request.form.getlist("municipios")
    data_envio = datetime.now().strftime("%d/%m/%Y %H:%M")

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
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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

    conn.commit()
    conn.close()

    return "<h3>Dados salvos com sucesso!</h3><a href='/formulario'>Voltar</a>"


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if session.get("email") not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            usuario_id, municipio_nome, estado, formador_local,
            pba_qtd, eja_alfabetizacao_qtd, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm,
            data_envio
        FROM respostas
    """)

    rows = cur.fetchall()
    conn.close()

    dados = []
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
            "data": r[16]
        })

    return render_template("dashboard.html", dados=dados)


# ================= API FILTROS (TABELA + CARDS + GRÁFICOS + MAPA) =================
@app.route("/api/filtrar", methods=["POST"])
def filtrar():

    filtros = request.json
    estado = filtros.get("estado")
    formador = filtros.get("formador")
    data_ini = filtros.get("data_ini")
    data_fim = filtros.get("data_fim")

    query = """
        SELECT 
            usuario_id, municipio_nome, estado, formador_local,
            pba_qtd, eja_alfabetizacao_qtd, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm,
            data_envio
        FROM respostas
        WHERE 1=1
    """

    params = []

    if estado:
        query += " AND estado = ?"
        params.append(estado)

    if formador:
        query += " AND usuario_id = ?"
        params.append(formador)

    if data_ini:
        query += " AND date(substr(data_envio,7,4)||'-'||substr(data_envio,4,2)||'-'||substr(data_envio,1,2)) >= date(?)"
        params.append(data_ini)

    if data_fim:
        query += " AND date(substr(data_envio,7,4)||'-'||substr(data_envio,4,2)||'-'||substr(data_envio,1,2)) <= date(?)"
        params.append(data_fim)

    conn = conectar()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    # ======== MONTAR RESPOSTA COMPLETA ========
    tabela = []
    estados = {}
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
            "total": total_mes,
            "data": r[16]
        })

        # Totais para cards
        pba_total += r[4] or 0
        eja_alf_total += r[5] or 0
        eja_ai_total += r[6] or 0

        # Totais por estado (gráfico + mapa)
        uf = r[2]
        if uf not in estados:
            estados[uf] = 0
        estados[uf] += total_mes

    return jsonify({
        "tabela": tabela,
        "cards": {
            "pba": pba_total,
            "eja_alf": eja_alf_total,
            "eja_ai": eja_ai_total,
            "geral": pba_total + eja_alf_total + eja_ai_total
        },
        "estados": estados
    })


# ================= EXPORTAÇÃO EXCEL =================
@app.route("/exportar_excel")
def exportar_excel():

    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM respostas", conn)
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


# ================= EXPORTAÇÃO PDF =================
@app.route("/exportar_pdf")
def exportar_pdf():

    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM respostas", conn)
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


# ================= CABEÇALHO DE RESPOSTA =================
@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)