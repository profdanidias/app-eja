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

# ================= CONFIGURAÇÕES BÁSICAS =================

# Ajuste para o seu banco
def conectar():
    return psycopg2.connect(
        host="SEU_HOST",
        dbname="SEU_DB",
        user="SEU_USER",
        password="SUA_SENHA",
        port=5432
    )

# E-mails de gestores
GESTORES = {
    "gestor1@exemplo.com",
    "gestor2@exemplo.com",
}

# ================= ESTADOS / MUNICÍPIOS (EXEMPLO) =================
# Você provavelmente já tem essas tabelas no banco; aqui é só o esqueleto.

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

def definir_estado_fixo(email, estado):
    # Se você tiver lógica específica para formadores, coloque aqui.
    # Neste esqueleto, não faz nada além de existir.
    pass

# ================= LOGIN SIMPLES (EXEMPLO) =================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")

        session["nome"] = nome
        session["email"] = email

        return redirect("/formulario")

    return render_template("login.html")

# ================= FORMULÁRIO =================

@app.route("/formulario")
def formulario():
    email = session.get("email")
    if not email:
        return redirect("/")

    is_gestor = email in GESTORES

    estados = listar_estados()
    estado_fixo = None

    if not is_gestor:
        # Se quiser amarrar o estado do formador, faça aqui
        # Exemplo simples: pega o primeiro estado
        if estados:
            estado_fixo = estados[0]["sigla"]

    return render_template(
        "formulario.html",
        is_gestor=is_gestor,
        estados=estados,
        estado_fixo=estado_fixo
    )

# ================= MUNICÍPIOS POR ESTADO =================

@app.route("/municipios/<uf>")
def municipios(uf):
    lista = listar_municipios_por_uf(uf)
    return jsonify(lista)

# ================= API DADOS ANTERIORES POR MUNICÍPIO =================

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

    meses_dict = {
        "jan": row[7] or 0,
        "fev": row[8] or 0,
        "mar": row[9] or 0,
        "abr": row[10] or 0,
        "mai": row[11] or 0,
        "jun": row[12] or 0,
        "jul": row[13] or 0,
        "ago": row[14] or 0,
        "setm": row[15] or 0,
    }

    return jsonify({
        "existe": True,
        "formador_local": row[0] or "",
        "pba": row[1] or "",
        "pba_qtd": row[2] or 0,
        "eja_alf": row[3] or "",
        "eja_alf_qtd": row[4] or 0,
        "eja_ai": row[5] or "",
        "eja_ai_qtd": row[6] or 0,
        "meses": meses_dict,
        "mes_atual": datetime.now().month
    })

# ================= SALVAR RESPOSTAS =================

@app.route("/salvar", methods=["POST"])
def salvar():
    conn = conectar()
    cur = conn.cursor()

    usuario = session.get("nome")
    email = session.get("email")
    estado = request.form.get("estado")

    definir_estado_fixo(email, estado)

    municipios = request.form.getlist("municipios")
    data_envio = datetime.now()

    ids_inseridos = []

    for m in municipios:
        # Normalizar respostas condicionais
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

        cur.execute("""
            INSERT INTO respostas (
                usuario_id, municipio_id, municipio_nome, estado,
                formador_local,
                pba, pba_qtd,
                eja_alfabetizacao, eja_alfabetizacao_qtd,
                eja_anos_iniciais, eja_anos_iniciais_qtd,
                jan, fev, mar, abr, mai, jun, jul, ago, setm,
                data_envio
            ) VALUES (
                %s,%s,%s,%s,
                %s,
                %s,%s,
                %s,%s,
                %s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s
            )
        """, (
            usuario,
            m,
            request.form.get(f"nome_{m}") or "",
            estado,
            request.form.get(f"formador_local_{m}") or "",

            pba, pba_qtd,
            eja_alf, eja_alf_qtd,
            eja_ai, eja_ai_qtd,

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

        cur.execute("SELECT LASTVAL()")
        last_id = cur.fetchone()[0]
        ids_inseridos.append(last_id)

    conn.commit()
    conn.close()

    session["ids_ultimo_envio"] = ids_inseridos

    return redirect("/resumo_envio")

# ================= RESUMO / FINALIZAÇÃO =================

@app.route("/resumo_envio")
def resumo_envio():
    ids = session.get("ids_ultimo_envio")
    if not ids:
        return redirect("/formulario")

    conn = conectar()
    cur = conn.cursor()
    query = """
        SELECT municipio_nome, estado, formador_local,
               pba, pba_qtd,
               eja_alfabetizacao, eja_alfabetizacao_qtd,
               eja_anos_iniciais, eja_anos_iniciais_qtd,
               jan, fev, mar, abr, mai, jun, jul, ago, setm,
               data_envio
        FROM respostas
        WHERE id = ANY(%s)
        ORDER BY data_envio DESC
    """
    cur.execute(query, (ids,))
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
            "meses": [r[9], r[10], r[11], r[12], r[13], r[14], r[15], r[16], r[17]],
            "data": r[18].strftime("%d/%m/%Y %H:%M") if r[18] else ""
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
    estados_set = set()
    formadores_set = set()

    for r in rows:
        meses = [
            r[10] or 0, r[11] or 0, r[12] or 0, r[13] or 0, r[14] or 0,
            r[15] or 0, r[16] or 0, r[17] or 0, r[18] or 0
        ]
        dados.append({
            "formador": r[0],
            "municipio": r[1],
            "estado": r[2],
            "formador_local": r[3],
            "pba": r[4] or "",
            "pba_qtd": r[5] or 0,
            "eja_alf": r[6] or "",
            "eja_alf_qtd": r[7] or 0,
            "eja_ai": r[8] or "",
            "eja_ai_qtd": r[9] or 0,
            "meses": meses,
            "total": sum(meses),
            "data": r[19].strftime("%d/%m/%Y %H:%M") if r[19] else "",
            "municipio_id": r[20]
        })
        if r[2]:
            estados_set.add(r[2])
        if r[0]:
            formadores_set.add(r[0])

    estados_lista = sorted(list(estados_set))
    formadores_lista = sorted(list(formadores_set))

    return render_template(
        "dashboard.html",
        dados=dados,
        estados_lista=estados_lista,
        formadores_lista=formadores_lista
    )

# ================= API DADOS INICIAIS (GRÁFICOS) =================

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

# ================= MAPA BRASIL POR MÊS =================

MESES_COLUNAS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "setm"]

def coluna_mes_atual():
    mes_idx = datetime.now().month
    if mes_idx < 1:
        mes_idx = 1
    if mes_idx > 9:
        mes_idx = 9
    return MESES_COLUNAS[mes_idx - 1]

@app.route("/api/mapa")
def api_mapa():
    coluna = coluna_mes_atual()
    return _dados_mapa_por_coluna(coluna)

@app.route("/api/mapa_mes/<coluna>")
def api_mapa_mes(coluna):
    if coluna not in MESES_COLUNAS:
        return jsonify([])
    return _dados_mapa_por_coluna(coluna)

def _dados_mapa_por_coluna(coluna):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT estado, SUM(COALESCE({coluna}, 0))
        FROM respostas
        GROUP BY estado
    """)
    rows = cur.fetchall()
    conn.close()

    dados = [{"uf": r[0], "total": r[1] or 0} for r in rows if r[0]]
    return jsonify(dados)

# ================= API FILTROS =================

@app.route("/api/filtrar", methods=["POST"])
def filtrar():
    filtros = request.json
    estado = filtros.get("estado")
    formador = filtros.get("formador")
    municipio_raw = filtros.get("municipio")
    data_ini = filtros.get("data_ini")
    data_fim = filtros.get("data_fim")

    municipio_id = None
    if municipio_raw:
        # Pode ser só ID ou "ID|Nome"
        partes = municipio_raw.split("|", 1)
        municipio_id = partes[0]

    query = """
        SELECT 
            usuario_id, municipio_nome, estado, formador_local,
            pba, pba_qtd,
            eja_alfabetizacao, eja_alfabetizacao_qtd,
            eja_anos_iniciais, eja_anos_iniciais_qtd,
            jan, fev, mar, abr, mai, jun, jul, ago, setm,
            data_envio, municipio_id
        FROM respostas
        WHERE 1=1
    """
    params = []

    if estado:
        query += " AND estado = %s"
        params.append(estado)

    if formador:
        query += " AND usuario_id = %s"
        params.append(formador)

    if municipio_id:
        query += " AND municipio_id = %s"
        params.append(municipio_id)

    if data_ini:
        query += " AND data_envio::date >= %s"
        params.append(data_ini)

    if data_fim:
        query += " AND data_envio::date <= %s"
        params.append(data_fim)

    query += " ORDER BY data_envio DESC"

    conn = conectar()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    tabela = []
    pba_total = 0
    eja_alf_total = 0
    eja_ai_total = 0

    for r in rows:
        meses = [
            r[10] or 0, r[11] or 0, r[12] or 0, r[13] or 0, r[14] or 0,
            r[15] or 0, r[16] or 0, r[17] or 0, r[18] or 0
        ]
        total_mes = sum(meses)

        tabela.append({
            "formador": r[0],
            "municipio": r[1],
            "estado": r[2],
            "formador_local": r[3],
            "pba": r[4] or "",
            "pba_qtd": r[5] or 0,
            "eja_alf": r[6] or "",
            "eja_alf_qtd": r[7] or 0,
            "eja_ai": r[8] or "",
            "eja_ai_qtd": r[9] or 0,
            "data": r[19].strftime("%d/%m/%Y %H:%M") if r[19] else "",
            "municipio_id": r[20]
        })

        pba_total += r[5] or 0
        eja_alf_total += r[7] or 0
        eja_ai_total += r[9] or 0

    return jsonify({
        "tabela": tabela,
        "cards": {
            "pba": pba_total,
            "eja_alf": eja_alf_total,
            "eja_ai": eja_ai_total,
            "geral": pba_total + eja_alf_total + eja_ai_total
        }
    })

# ================= EXPORTAÇÃO EXCEL (GERAL) =================

@app.route("/exportar_excel")
def exportar_excel():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("""
        SELECT *
        FROM respostas
        ORDER BY data_envio DESC
    """, conn)
    conn.close()

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="dados.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ================= EXPORTAÇÃO EXCEL POR MUNICÍPIO =================

@app.route("/exportar_municipio/<municipio_id>")
def exportar_municipio(municipio_id):
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("""
        SELECT *
        FROM respostas
        WHERE municipio_id = %s
        ORDER BY data_envio DESC
    """, conn, params=(municipio_id,))
    conn.close()

    if df.empty:
        return "Nenhum registro encontrado para este município."

    nome_municipio = df["municipio_nome"].iloc[0] or "municipio"
    hoje = datetime.now().strftime("%Y-%m-%d")
    nome_arquivo = f"historico_{nome_municipio}_{hoje}.xlsx".replace(" ", "_")

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ================= EXPORTAÇÃO PDF =================

@app.route("/exportar_pdf")
def exportar_pdf():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado"

    conn = conectar()
    df = pd.read_sql_query("""
        SELECT *
        FROM respostas
        ORDER BY data_envio DESC
    """, conn)
    conn.close()

    output = io.BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=letter)

    tabela = [df.columns.tolist()] + df.values.tolist()
    pdf.build([Table(tabela)])
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="dados.pdf",
        mimetype="application/pdf"
    )

# ================= LIMPAR TODOS OS DADOS =================

@app.route("/limpar_tudo", methods=["POST"])
def limpar_tudo():
    email = session.get("email")
    if email not in GESTORES:
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()
    cur.execute("DELETE FROM respostas")
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

# ================= CABEÇALHO DE RESPOSTA =================

@app.after_request
def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    return response

# ================= MAIN =================

if __name__ == "__main__":
    app.run(debug=True)