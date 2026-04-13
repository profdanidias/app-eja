from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

# ================= CONFIG =================
GESTORES = ["professoradanidias@gmail.com"]

def conectar():
    return sqlite3.connect("database.db")


# ================= CRIAR BANCO AUTOMATICAMENTE =================
def inicializar_banco():
    conn = conectar()
    cur = conn.cursor()

    # tabela usuarios
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT,
        tipo TEXT,
        funcao TEXT
    )
    """)

    # tabela logs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs_acesso (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        acao TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # tabela respostas
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


# executa ao iniciar
inicializar_banco()


# ================= LOGIN =================
@app.route("/", methods=["GET"])
def auto_login():
    nome = request.args.get("nome")
    email = request.args.get("email")

    if nome and email:
        session["nome"] = nome.strip()
        session["email"] = email.strip().lower()
        session["tipo"] = "gestor" if session["email"] in GESTORES else "formador"
        return redirect("/funcao")

    return "Acesso inválido. Utilize o acesso via Moodle."


# ================= FUNÇÃO =================
@app.route("/funcao", methods=["GET", "POST"])
def funcao():

    if "email" not in session:
        return redirect("/")

    if request.method == "POST":
        funcao = request.form.get("funcao")

        conn = conectar()
        cur = conn.cursor()

        # INSERÇÃO SEGURA
        try:
            cur.execute("""
            INSERT INTO usuarios (nome, email, tipo, funcao)
            VALUES (?, ?, ?, ?)
            """, (
                session.get("nome"),
                session.get("email"),
                session.get("tipo"),
                funcao
            ))
        except Exception as e:
            conn.close()
            return f"Erro ao salvar usuário: {str(e)}"

        user_id = cur.lastrowid

        try:
            cur.execute(
                "INSERT INTO logs_acesso (usuario_id, acao) VALUES (?, ?)",
                (user_id, "login")
            )
        except Exception as e:
            conn.close()
            return f"Erro ao registrar log: {str(e)}"

        conn.commit()
        conn.close()

        session["user_id"] = user_id
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

    if "user_id" not in session:
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    usuario = session["user_id"]
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
            request.form.get(f"nome_{m}"),
            estado,
            request.form.get(f"formador_local_{m}"),
            request.form.get(f"pba_{m}"),
            int(request.form.get(f"pba_qtd_{m}") or 0),
            request.form.get(f"eja_alf_{m}"),
            int(request.form.get(f"eja_alf_qtd_{m}") or 0),
            request.form.get(f"eja_ai_{m}"),
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

    if session.get("tipo") != "gestor":
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    SELECT estado, SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm)
    FROM respostas
    GROUP BY estado
    """)
    dados_estado = cur.fetchall()

    cur.execute("""
    SELECT funcao, COUNT(*)
    FROM usuarios
    GROUP BY funcao
    """)
    funcoes = cur.fetchall()

    cur.execute("""
    SELECT 
        SUM(jan), SUM(fev), SUM(mar), SUM(abr),
        SUM(mai), SUM(jun), SUM(jul), SUM(ago), SUM(setm)
    FROM respostas
    """)
    meses = cur.fetchone()

    conn.close()

    return render_template(
        "dashboard.html",
        dados_estado=dados_estado,
        funcoes=funcoes,
        meses=meses
    )


# ================= EMBED =================
@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)