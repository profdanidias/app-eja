from flask import Flask, render_template, request, redirect, session, jsonify, send_file
import sqlite3
import requests
import pandas as pd
import io
from datetime import datetime

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
        dados.append({
            "formador": r[0],
            "municipio": r[1],
            "estado": r[2],
            "formador_local": r[3],
            "pba": r[4] or 0,
            "eja_alf": r[5] or 0,
            "eja_ai": r[6] or 0,
            "meses": [
                r[7] or 0, r[8] or 0, r[9] or 0, r[10] or 0, r[11] or 0,
                r[12] or 0, r[13] or 0, r[14] or 0, r[15] or 0
            ],
            "data": r[16]
        })

    return render_template("dashboard.html", dados=dados)

# ============= ENDPOINT ALIMENTAR OS GRÁFICOS
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


@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)