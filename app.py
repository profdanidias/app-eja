from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

GESTORES = ["professoradanidias@gmail.com"]


# ================= CONEXÃO =================
def conectar():
    return sqlite3.connect("database.db")


# ================= LOGIN AUTOMÁTICO =================
@app.route("/")
def auto_login():
    nome = request.args.get("nome")
    email = request.args.get("email")

    if nome and email:
        session["nome"] = nome
        session["email"] = email.lower()
        return redirect("/funcao")

    return "Acesso inválido"


# ================= FUNÇÃO =================
@app.route("/funcao", methods=["GET", "POST"])
def funcao():

    if "email" not in session:
        return redirect("/")

    if request.method == "POST":
        session["funcao"] = request.form.get("funcao")

        if session["funcao"] != "Formador Regional":
            return render_template("bloqueado.html")

        return redirect("/formulario")

    return render_template("funcao.html")


# ================= FORMULÁRIO =================
@app.route("/formulario")
def formulario():

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


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if session.get("email") not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    SELECT 
        usuario_id,
        municipio_nome,
        estado,
        formador_local,
        pba_qtd,
        eja_alfabetizacao_qtd,
        eja_anos_iniciais_qtd,
        COALESCE(jan,0)+COALESCE(fev,0)+COALESCE(mar,0)+COALESCE(abr,0)+
        COALESCE(mai,0)+COALESCE(jun,0)+COALESCE(jul,0)+COALESCE(ago,0)+COALESCE(setm,0)
        as total
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
            "total": r[7] or 0
        })

    return render_template("dashboard.html", dados=dados)


# ================= PERMITIR EMBED =================
@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)