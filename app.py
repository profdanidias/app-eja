import io
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    session, jsonify, send_file
)
import psycopg2
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
app.secret_key = "SUA_SECRET_KEY_AQUI"



#========== LOGIN SEM MOODLE =============
@app.before_request
def controle_de_acesso():
    # Permitir acesso ao login (GET ou POST), mesmo com parâmetros
    if request.endpoint == "index":
        return

    # Permitir arquivos estáticos
    if request.path.startswith("/static"):
        return

    # Se já está logado, segue
    if "email" in session:
        return

    # Caso contrário, volta para o login
    return redirect("/")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        session["nome"] = request.form.get("nome")
        session["email"] = request.form.get("email")
        return redirect("/formulario")

    return render_template("login.html")



# ================= CONFIGURAÇÃO DO POSTGRES =================

def conectar():
    return psycopg2.connect(
        host="dpg-d7f5m8rbc2fs738hmrs0-a.oregon-postgres.render.com",
        database="postgresql_eja",
        user="postgresql_eja_user",
        password="9x8y7z123456",
        port=5432
    )

GESTORES = {
    "gestor1@exemplo.com",
    "gestor2@exemplo.com",
}

# ================= ESTADOS / MUNICÍPIOS =================

def listar_estados():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT sigla, nome FROM estados ORDER BY nome")
    rows = cur.fetchall()
    conn.close()
    return [{"sigla": r[0], "nome": r[1]} for r in rows]

def listar_municipios_por_uf(uf):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nome FROM municipios WHERE uf = %s ORDER BY nome",
        (uf,)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "nome": r[1]} for r in rows]

# ================= FORMULÁRIO =================

@app.route("/formulario")
def formulario():
    email = session.get("email")
    if not email:
        return redirect("/")

    is_gestor = email in GESTORES
    estados = listar_estados()

    estado_fixo = None
    if not is_gestor and estados:
        estado_fixo = estados[0]["sigla"]

    return render_template(
        "formulario.html",
        is_gestor=is_gestor,
        estados=estados,
        estado_fixo=estado_fixo
    )

@app.route("/municipios/<uf>")
def municipios(uf):
    return jsonify(listar_municipios_por_uf(uf))

# ================= API DADOS ANTERIORES =================

@app.route("/api/dados_municipio/<municipio_id>")
def api_dados_municipio(municipio_id):
    email = session.get("email")
    if not email:
        return jsonify({"existe": False})

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            formador_local,
            pba, pba_qtd,
            eja_alfabetizacao, eja_alfabetizacao_qtd,
            eja_anos_iniciais, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm
        FROM respostas
        WHERE usuario_id = %s
          AND municipio_id = %s
        ORDER BY data_envio DESC
        LIMIT 1
    """, (email, municipio_id))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"existe": False})

    meses = ["jan","fev","mar","abr","mai","jun","jul","ago","setm"]

    return jsonify({
        "existe": True,
        "formador_local": row[0],
        "pba": row[1],
        "pba_qtd": row[2],
        "eja_alf": row[3],
        "eja_alf_qtd": row[4],
        "eja_ai": row[5],
        "eja_ai_qtd": row[6],
        "meses": {meses[i]: row[7+i] for i in range(9)},
        "mes_atual": datetime.now().month
    })

# ================= SALVAR FORMULÁRIO =================

@app.route("/salvar", methods=["POST"])
def salvar():
    conn = conectar()
    cur = conn.cursor()

    usuario = session.get("email")
    estado = request.form.get("estado")
    municipios = request.form.getlist("municipios")
    data_envio = datetime.now()

    ids = []

    for m in municipios:
        pba = request.form.get(f"pba_{m}") or ""
        pba_qtd = int(request.form.get(f"pba_qtd_{m}") or 0)
        if pba != "Sim":
            pba_qtd = 0

        eja_alf = request.form.get(f"eja_alf_{m}") or ""
        eja_alf_qtd = int(request.form.get(f"eja_alf_qtd_{m}") or 0)
        if eja_alf != "Sim":
            eja_alf_qtd = 0

        eja_ai = request.form.get(f"eja_ai_{m}") or ""
        eja_ai_qtd = int(request.form.get(f"eja_ai_qtd_{m}") or 0)
        if eja_ai != "Sim":
            eja_ai_qtd = 0

        meses = ["jan","fev","mar","abr","mai","jun","jul","ago","setm"]
        valores_meses = [int(request.form.get(f"{mes}_{m}") or 0) for mes in meses]

        cur.execute(f"""
            INSERT INTO respostas (
                usuario_id, municipio_id, municipio_nome, estado,
                formador_local,
                pba, pba_qtd,
                eja_alfabetizacao, eja_alfabetizacao_qtd,
                eja_anos_iniciais, eja_anos_iniciais_qtd,
                {",".join(meses)},
                data_envio
            ) VALUES (
                %s,%s,%s,%s,
                %s,
                %s,%s,
                %s,%s,
                %s,%s,
                {",".join(["%s"]*9)},
                %s
            )
        """, (
            usuario,
            m,
            request.form.get(f"nome_{m}"),
            estado,
            request.form.get(f"formador_local_{m}"),
            pba, pba_qtd,
            eja_alf, eja_alf_qtd,
            eja_ai, eja_ai_qtd,
            *valores_meses,
            data_envio
        ))

        cur.execute("SELECT LASTVAL()")
        ids.append(cur.fetchone()[0])

    conn.commit()
    conn.close()

    session["ids_ultimo_envio"] = ids
    return redirect("/resumo_envio")

# ================= RESUMO =================

@app.route("/resumo_envio")
def resumo_envio():
    ids = session.get("ids_ultimo_envio")
    if not ids:
        return redirect("/formulario")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT municipio_nome, estado, formador_local,
               pba, pba_qtd,
               eja_alfabetizacao, eja_alfabetizacao_qtd,
               eja_anos_iniciais, eja_anos_iniciais_qtd,
               jan, fev, mar, abr, mai, jun, jul, ago, setm,
               data_envio
        FROM respostas
        WHERE id = ANY(%s)
    """, (ids,))
    rows = cur.fetchall()
    conn.close()

    dados = []
    for r in rows:
        dados.append({
            "municipio": r[0],
            "estado": r[1],
            "formador_local": r[2],
            "pba": r[3],
            "pba_qtd": r[4],
            "eja_alf": r[5],
            "eja_alf_qtd": r[6],
            "eja_ai": r[7],
            "eja_ai_qtd": r[8],
            "meses": r[9:18],
            "data": r[18].strftime("%d/%m/%Y %H:%M")
        })

    return render_template("resumo_envio.html", dados=dados)

@app.route("/finalizar_envio", methods=["POST"])
def finalizar_envio():
    session.pop("ids_ultimo_envio", None)
    return render_template("mensagem_final.html")

# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            usuario_id, municipio_nome, estado, formador_local,
            pba, pba_qtd,
            eja_alfabetizacao, eja_alfabetizacao_qtd,
            eja_anos_iniciais, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm,
            data_envio, municipio_id
        FROM respostas
        ORDER BY data_envio DESC
    """)
    rows = cur.fetchall()
    conn.close()

    dados = []
    estados = set()
    formadores = set()

    for r in rows:
        dados.append({
            "formador": r[0],
            "municipio": r[1],
            "estado": r[2],
            "formador_local": r[3],
            "pba": r[4],
            "pba_qtd": r[5],
            "eja_alf": r[6],
            "eja_alf_qtd": r[7],
            "eja_ai": r[8],
            "eja_ai_qtd": r[9],
            "data": r[19].strftime("%d/%m/%Y %H:%M"),
            "municipio_id": r[20]
        })

        estados.add(r[2])
        formadores.add(r[0])

    return render_template(
        "dashboard.html",
        dados=dados,
        estados_lista=sorted(estados),
        formadores_lista=sorted(formadores)
    )

# ================= EXPORTAÇÕES =================

@app.route("/exportar_excel")
def exportar_excel():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM respostas ORDER BY data_envio DESC", conn)
    conn.close()

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name="dados.xlsx")

@app.route("/exportar_municipio/<municipio_id>")
def exportar_municipio(municipio_id):
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query(
        "SELECT * FROM respostas WHERE municipio_id = %s ORDER BY data_envio DESC",
        conn,
        params=(municipio_id,)
    )
    conn.close()

    if df.empty:
        return "Nenhum registro encontrado."

    nome = df["municipio_nome"].iloc[0]
    hoje = datetime.now().strftime("%Y-%m-%d")

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name=f"{nome}_{hoje}.xlsx")

# ================= MAIN =================

if __name__ == "__main__":
    app.run(debug=True)