from flask import Flask, render_template, request, redirect, session, jsonify, send_file
import sqlite3
import requests
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

GESTORES = ["professoradanidias@gmail.com"]


# ================= CONEXÃO =================
def conectar():
    return sqlite3.connect("database.db")


# ================= CRIAR BANCO AUTOMÁTICO =================
def inicializar_banco():
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
        mai INTEGER, jun INTEGER, jul INTEGER, ago INTEGER, setm INTEGER
    )
    """)

    conn.commit()
    conn.close()


# 🔥 GARANTE QUE O BANCO SEMPRE EXISTE
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
        session["funcao"] = funcao

        if funcao != "Formador Regional":
            return render_template("bloqueado.html")

        return redirect("/formulario")

    return render_template("funcao.html")


# ================= FORMULÁRIO =================
@app.route("/formulario")
def formulario():

    if "email" not in session:
        return redirect("/")

    if session.get("funcao") != "Formador Regional":
        return "Acesso negado"

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

    if "email" not in session:
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    usuario = session.get("nome")
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


# ================= EXPORTAR =================
@app.route("/exportar")
def exportar():

    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM respostas", conn)
    conn.close()

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output,
        download_name="dados_eja.xlsx",
        as_attachment=True
    )


# ================= IMPORTAR =================
@app.route("/importar", methods=["POST"])
def importar():

    arquivo = request.files["file"]
    df = pd.read_excel(arquivo)

    conn = conectar()
    df.to_sql("respostas", conn, if_exists="append", index=False)
    conn.close()

    return redirect("/dashboard")


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

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
    dados_estado = cur.fetchall() or []

    # MUNICÍPIOS
    cur.execute("""
    SELECT municipio_nome, estado,
           COALESCE(SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm),0)
    FROM respostas
    GROUP BY municipio_nome, estado
    ORDER BY 3 DESC
    """)
    dados_municipio_raw = cur.fetchall() or []

    # adiciona nome do formador
    dados_municipio = []
    for m in dados_municipio_raw:
        dados_municipio.append((m[0], m[1], "Formador", m[2]))

    conn.close()

    return render_template("dashboard.html",
        dados_estado=dados_estado,
        dados_municipio=dados_municipio
    )


# ================= PERMITIR MOODLE =================
@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)