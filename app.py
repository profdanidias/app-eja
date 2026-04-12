from flask import Flask, render_template, request, redirect, session
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = "segredo"

GESTORES = ["gestor@email.com"]

def conectar():
    return sqlite3.connect("database.db")

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        funcao = request.form.get("funcao")

        conn = conectar()
        cur = conn.cursor()

        tipo = "gestor" if email in GESTORES else "formador"

        cur.execute("""
        INSERT INTO usuarios (nome, email, tipo, funcao)
        VALUES (?, ?, ?, ?)
        """, (nome, email, tipo, funcao))

        usuario_id = cur.lastrowid

        cur.execute("INSERT INTO logs_acesso (usuario_id, acao) VALUES (?, ?)",
                    (usuario_id, "login"))

        conn.commit()
        conn.close()

        session["usuario_id"] = usuario_id
        session["tipo"] = tipo
        session["funcao"] = funcao

        if funcao != "Formador Regional":
            return render_template("bloqueado.html")

        return redirect("/formulario")

    return render_template("login.html")

# ---------------- IBGE ----------------
@app.route("/estados")
def estados():
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
    return requests.get(url).json()

@app.route("/municipios/<uf>")
def municipios(uf):
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
    return requests.get(url).json()

# ---------------- FORMULÁRIO ----------------
@app.route("/formulario")
def formulario():
    if session.get("funcao") != "Formador Regional":
        return "Acesso não autorizado"
    return render_template("formulario.html")

# ---------------- SALVAR ----------------
@app.route("/salvar", methods=["POST"])
def salvar():
    conn = conectar()
    cur = conn.cursor()

    usuario_id = session["usuario_id"]

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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario_id,
            m,
            request.form.get(f"nome_{m}"),
            request.form.get("estado"),

            request.form.get(f"formador_local_{m}"),

            request.form.get(f"pba_{m}"),
            request.form.get(f"pba_qtd_{m}") or 0,

            request.form.get(f"eja_alf_{m}"),
            request.form.get(f"eja_alf_qtd_{m}") or 0,

            request.form.get(f"eja_ai_{m}"),
            request.form.get(f"eja_ai_qtd_{m}") or 0,

            request.form.get(f"jan_{m}") or 0,
            request.form.get(f"fev_{m}") or 0,
            request.form.get(f"mar_{m}") or 0,
            request.form.get(f"abr_{m}") or 0,
            request.form.get(f"mai_{m}") or 0,
            request.form.get(f"jun_{m}") or 0,
            request.form.get(f"jul_{m}") or 0,
            request.form.get(f"ago_{m}") or 0,
            request.form.get(f"setm_{m}") or 0
        ))

    conn.commit()
    conn.close()

    return "Dados salvos com sucesso!"

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if session.get("tipo") != "gestor":
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()

    # Indicadores
    cur.execute("SELECT COUNT(*) FROM usuarios")
    total_usuarios = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM usuarios WHERE funcao='Formador Regional'")
    total_formadores = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM usuarios WHERE funcao!='Formador Regional'")
    outros = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT municipio_id) FROM respostas")
    municipios = cur.fetchone()[0]

    cur.execute("SELECT SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm) FROM respostas")
    participantes = cur.fetchone()[0] or 0

    # Participantes por estado
    cur.execute("""
    SELECT estado, SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm)
    FROM respostas
    GROUP BY estado
    """)
    dados_estado = cur.fetchall()

    # Participantes por mês
    cur.execute("""
    SELECT SUM(jan), SUM(fev), SUM(mar), SUM(abr),
           SUM(mai), SUM(jun), SUM(jul), SUM(ago), SUM(setm)
    FROM respostas
    """)
    meses = cur.fetchone()

    # Funções
    cur.execute("SELECT funcao, COUNT(*) FROM usuarios GROUP BY funcao")
    funcoes = cur.fetchall()

    conn.close()

    return render_template("dashboard.html",
        total_usuarios=total_usuarios,
        total_formadores=total_formadores,
        outros=outros,
        municipios=municipios,
        participantes=participantes,
        dados_estado=dados_estado,
        meses=meses,
        funcoes=funcoes
    )
if __name__ == "__main__":
    app.run()
