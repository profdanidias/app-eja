from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import requests
import os

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

GESTORES = ["professoradanidias@gmail.com"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def conectar():
    return sqlite3.connect(DB_PATH)

def criar_banco():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT,
        tipo TEXT,
        funcao TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        municipio_id INTEGER,
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
        mai INTEGER, jun INTEGER, jul INTEGER, ago INTEGER, setm INTEGER
    )
    """)

    conn.commit()
    conn.close()

criar_banco()

# LOGIN
@app.route("/")
def auto_login():
    nome = request.args.get("nome")
    email = request.args.get("email")

    if nome and email:
        session["nome"] = nome
        session["email"] = email

        if email.lower() in [g.lower() for g in GESTORES]:
            session["tipo"] = "gestor"
        else:
            session["tipo"] = "formador"

        return redirect("/funcao")

    return "Acesso via Moodle necessário"

# FUNÇÃO
@app.route("/funcao", methods=["GET","POST"])
def funcao():
    if request.method == "POST":
        funcao = request.form.get("funcao")

        session["funcao"] = funcao

        if funcao != "Formador Regional":
            return "Obrigada por sua contribuição."

        return redirect("/formulario")

    return render_template("funcao.html")

# IBGE
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

# FORMULÁRIO
@app.route("/formulario")
def formulario():
    if session.get("funcao") != "Formador Regional":
        return "Acesso negado"
    return render_template("formulario.html")

# SALVAR
@app.route("/salvar", methods=["POST"])
def salvar():

    conn = conectar()
    cur = conn.cursor()

    estado = request.form.get("estado")
    municipios = request.form.getlist("municipios")

    for m in municipios:
        cur.execute("""
        INSERT INTO respostas (
            municipio_id, municipio_nome, estado,
            formador_local,
            pba, pba_qtd,
            eja_alfabetizacao, eja_alfabetizacao_qtd,
            eja_anos_iniciais, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            m,
            request.form.get(f"nome_{m}"),
            estado,
            request.form.get(f"formador_local_{m}"),
            request.form.get(f"pba_{m}"),
            request.form.get(f"pba_qtd_{m}") or 0,
            request.form.get(f"eja_alf_{m}"),
            request.form.get(f"eja_alf_qtd_{m}") or 0,
            request.form.get(f"eja_ai_{m}"),
            request.form.get(f"eja_ai_qtd_{m}") or 0,
            max(0, int(request.form.get(f"jan_{m}") or 0)),
            max(0, int(request.form.get(f"fev_{m}") or 0)),
            max(0, int(request.form.get(f"mar_{m}") or 0)),
            max(0, int(request.form.get(f"abr_{m}") or 0)),
            max(0, int(request.form.get(f"mai_{m}") or 0)),
            max(0, int(request.form.get(f"jun_{m}") or 0)),
            max(0, int(request.form.get(f"jul_{m}") or 0)),
            max(0, int(request.form.get(f"ago_{m}") or 0)),
            max(0, int(request.form.get(f"setm_{m}") or 0))
        ))

    conn.commit()
    conn.close()

    return "Dados enviados com sucesso!"

# DASHBOARD
@app.route("/dashboard")
def dashboard():

    email = session.get("email")

    if not email or email.lower() not in [g.lower() for g in GESTORES]:
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    SELECT estado, SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm)
    FROM respostas GROUP BY estado
    """)

    dados_estado = cur.fetchall()

    cur.execute("""
    SELECT SUM(jan),SUM(fev),SUM(mar),SUM(abr),
           SUM(mai),SUM(jun),SUM(jul),SUM(ago),SUM(setm)
    FROM respostas
    """)

    meses = cur.fetchone()

    conn.close()

    return render_template("dashboard.html",
        dados_estado=dados_estado,
        meses=meses
    )

# EMBED
@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response

if __name__ == "__main__":
    app.run()