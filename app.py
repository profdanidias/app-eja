from flask import Flask, render_template, request, redirect, session, jsonify, send_file
import sqlite3
import requests
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

GESTORES = ["professoradanidias@gmail.com"]


def conectar():
    return sqlite3.connect("database.db")


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


# ================= FUNÇÃO =================
@app.route("/funcao", methods=["GET", "POST"])
def funcao():

    if request.method == "POST":
        funcao = request.form.get("funcao")
        session["funcao"] = funcao

        if funcao != "Formador Regional":
            return render_template("bloqueado.html")

        return redirect("/formulario")

    return render_template("funcao.html")


# ================= FORM =================
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

    for m in municipios:
        cur.execute("""
        INSERT INTO respostas (
            usuario_id, municipio_nome, estado,
            jan, fev, mar, abr, mai, jun, jul, ago, setm
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            usuario,
            request.form.get(f"nome_{m}"),
            estado,
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

    return "Salvo com sucesso"


# ================= EXPORTAR EXCEL =================
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


# ================= IMPORTAR EXCEL =================
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

    cur.execute("""
    SELECT estado, SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm)
    FROM respostas GROUP BY estado
    """)
    dados_estado = cur.fetchall()

    cur.execute("""
    SELECT municipio_nome, estado, usuario_id,
           SUM(jan+fev+mar+abr+mai+jun+jul+ago+setm)
    FROM respostas
    GROUP BY municipio_nome, estado, usuario_id
    """)
    dados_municipio = cur.fetchall()

    conn.close()

    return render_template("dashboard.html",
        dados_estado=dados_estado,
        dados_municipio=dados_municipio
    )


@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response


if __name__ == "__main__":
    app.run(debug=True)