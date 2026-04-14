import requests
import psycopg2

# CONFIGURAÇÃO DO BANCO
DB_HOST = "SEU_HOST"
DB_NAME = "SEU_DB"
DB_USER = "SEU_USER"
DB_PASS = "SUA_SENHA"
DB_PORT = 5432

def conectar():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

def importar_municipios():
    print("Baixando lista de municípios do IBGE...")

    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    resposta = requests.get(url)

    if resposta.status_code != 200:
        print("Erro ao acessar API do IBGE")
        return

    municipios = resposta.json()
    print(f"{len(municipios)} municípios encontrados.")

    conn = conectar()
    cur = conn.cursor()

    for m in municipios:
        codigo = str(m["id"])
        nome = m["nome"]
        uf = m["microrregiao"]["mesorregiao"]["UF"]["sigla"]

        cur.execute("""
            INSERT INTO municipios (id, nome, uf)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (codigo, nome, uf))

    conn.commit()
    conn.close()

    print("Importação concluída com sucesso!")

if __name__ == "__main__":
    importar_municipios()