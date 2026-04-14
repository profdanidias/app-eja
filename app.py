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
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuario_estado (email, estado)
        VALUES (?, ?)
        ON CONFLICT(email) DO UPDATE SET estado = excluded.estado
    """, (email, estado))
    conn.commit()
    conn.close()


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


# ================= SALVAR =================
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


# ================= RESUMO =================
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
            "meses": [r[6],r[7],r[8],r[9],r[10],r[11],r[12],r[13],r[14]],
            "data": r[15]
        })
