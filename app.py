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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuario_estado (
        email TEXT PRIMARY KEY,
        estado TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


criar_banco()


# ================= ESTADO FIXO =================
def obter_estado_fixo(email):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM usuario_estado WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def definir_estado_fixo(email, estado):
    if not email or not estado:
        return
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuario_estado (email, estado)
        VALUES (?, ?)
        ON CONFLICT(email) DO UPDATE SET estado = excluded.estado
    """, (email, estado))
    conn.commit()
    conn.close()


# ================= LOGIN / PERFIL =================
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

    estado_fixo = obter_estado_fixo(email)
    is_gestor = email in GESTORES

    return render_template(
        "formulario.html",
        is_gestor=is_gestor,
        estado_fixo=estado_fixo
    )


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


# ================= SALVAR FORMULÁRIO =================
@app.route("/salvar", methods=["POST"])
def salvar():

    conn = conectar()
    cur = conn.cursor()

    usuario = session.get("nome")
    email = session.get("email")
    estado = request.form.get("estado")

    definir_estado_fixo(email, estado)

    municipios = request.form.getlist("municipios")
    data_envio = datetime.now().strftime("%d/%m/%Y %H:%M")

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

        ids_inseridos.append(cur.lastrowid)

    conn.commit()
    conn.close()

    session["ids_ultimo_envio"] = ids_inseridos

    return redirect("/resumo_envio")


# ================= RESUMO DO ENVIO =================
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
        WHERE id IN ({",".join(["?"]*len(ids))})
    """
    cur.execute(query, ids)
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
            "data": r[15]
        })

    return render_template("resumo_envio.html", dados=dados)


@app.route("/finalizar_envio", methods=["POST"])
def finalizar_envio():
    session.pop("ids_ultimo_envio", None)
    return render_template("mensagem_final.html")


# ================= DASHBOARD (APENAS GESTOR) =================
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
        ORDER BY 
            date(substr(data_envio,7,4)||'-'||substr(data_envio,4,2)||'-'||substr(data_envio,1,2)) DESC,
            time(substr(data_envio,12)) DESC
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
            "data": r[16]
        })
        estados_set.add(r[2])
        formadores_set.add(r[0])

    estados_lista = sorted([e for e in estados_set if e])
    formadores_lista = sorted([f for f in formadores_set if f])

    return render_template(
        "dashboard.html",
        dados=dados,
        estados_lista=estados_lista,
        formadores_lista=formadores_lista
    )


# ================= EXPORTAÇÕES (GESTOR) =================
@app.route("/exportar_excel")
def exportar_excel():

    if session.get("email") not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("""
        SELECT *
        FROM respostas
        ORDER BY 
            date(substr(data_envio,7,4)||'-'||substr(data_envio,4,2)||'-'||substr(data_envio,1,2)) DESC,
            time(substr(data_envio,12)) DESC
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


@app.route("/exportar_pdf")
def exportar_pdf():

    if session.get("email") not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("""
        SELECT *
        FROM respostas
        ORDER BY 
            date(substr(data_envio,7,4)||'-'||substr(data_envio,4,2)||'-'||substr(data_envio,1,2)) DESC,
            time(substr(data_envio,12)) DESC
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


# ================= CABEÇALHO DE RESPOSTA =================
@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)