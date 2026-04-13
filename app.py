from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

GESTORES = ["professoradanidias@gmail.com"]


def conectar():
    return sqlite3.connect("database.db")


# ================= BANCO =================
def inicializar_banco():
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
        mai INTEGER, jun INTEGER, jul INTEGER, ago INTEGER, setm INTEGER
    )
    """)

    conn.commit()
    conn.close()


inicializar_banco()


# ================= LOGIN =================
@app.route("/")
def auto_login():
    nome = request.args.get("nome")
    email = request.args.get("email")

    if nome and email:
        session["nome"] = nome
        session["email"] = email.lower()
        session["tipo"] = "gestor" if email.lower() in GESTORES else "formador"
        return redirect("/funcao")

    return "Acesso inválido"


# ================= FUNÇÃO =================
@app.route("/funcao", methods=["GET", "POST"])
def funcao():

    if "email" not in session:
        return redirect("/")

    if request.method == "POST":
        funcao = request.form.get("funcao")

        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO usuarios (nome, email, tipo, funcao)
        VALUES (?, ?, ?, ?)
        """, (
            session["nome"],
            session["email"],
            session["tipo"],
            funcao
        ))

        conn.commit()
        conn.close()

        session["funcao"] = funcao

        if funcao != "Formador Regional":
            return render_template("bloqueado.html")

        return redirect("/formulario")

    return render_template("funcao.html")


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


# ================= FORMULÁRIO =================
@app.route("/formulario")
def formulario():

    if "email" not in session:
        return redirect("/")

    if session.get("funcao") != "Formador Regional":
        return "Acesso negado"

    is_gestor = session.get("email") in GESTORES

    return render_template("formulario.html", is_gestor=is_gestor)


# ================= SALVAR =================
@app.route("/salvar", methods=["POST"])
def salvar():

    if "email" not in session:
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    usuario = session.get("email")
    estado = request.form.get("estado")
    municipios = request.form.getlist("municipios")

    for m in municipios:
        cur.execute("""
        INSERT INTO respostas (
            usuario_id, municipio_id, municipio_nome, estado,
            formador_local,
            pba, pba_qtd,
            eja_alfabetizacao, eja_alfabetizacao_qtd,
            eja_anos_iniciais, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            int(request.form.get(f"setm_{m}") or 0)
        ))

    conn.commit()
    conn.close()

    return "<h3>Dados enviados com sucesso!</h3><a href='/formulario'>Voltar</a>"


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "email" not in session:
        return redirect("/")

    if session.get("email") not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()

    # ESTADOS
    cur.execute("""
    SELECT estado, COALESCE(SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm),0)
    FROM respostas
    GROUP BY estado
    """)
    dados_estado = cur.fetchall()

    # MUNICÍPIOS
    cur.execute("""
    SELECT municipio_nome, estado,
           COALESCE(SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm),0)
    FROM respostas
    GROUP BY municipio_nome, estado
    ORDER BY 3 DESC
    """)
    dados_municipio = cur.fetchall()

    # FUNÇÕES
    cur.execute("SELECT funcao, COUNT(*) FROM usuarios GROUP BY funcao")
    funcoes = cur.fetchall()

    # MESES
    cur.execute("""
    SELECT 
        COALESCE(SUM(jan),0), COALESCE(SUM(fev),0), COALESCE(SUM(mar),0),
        COALESCE(SUM(abr),0), COALESCE(SUM(mai),0), COALESCE(SUM(jun),0),
        COALESCE(SUM(jul),0), COALESCE(SUM(ago),0), COALESCE(SUM(setm),0)
    FROM respostas
    """)
    meses = cur.fetchone() or (0,0,0,0,0,0,0,0,0)

    conn.close()

    return render_template("dashboard.html",
        dados_estado=dados_estado or [],
        dados_municipio=dados_municipio or [],
        funcoes=funcoes or [],
        meses=meses
    )


@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)