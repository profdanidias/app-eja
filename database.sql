-- ============================================
-- BANCO DE DADOS DO SISTEMA EJA (PostgreSQL)
-- ============================================

-- TABELA DE ESTADOS
CREATE TABLE IF NOT EXISTS estados (
    sigla VARCHAR(2) PRIMARY KEY,
    nome VARCHAR(100) NOT NULL
);

-- TABELA DE MUNICÍPIOS
CREATE TABLE IF NOT EXISTS municipios (
    id VARCHAR(20) PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    uf VARCHAR(2) NOT NULL REFERENCES estados(sigla)
);

-- TABELA DE RESPOSTAS
CREATE TABLE IF NOT EXISTS respostas (
    id SERIAL PRIMARY KEY,

    usuario_id VARCHAR(255),
    municipio_id VARCHAR(50),
    municipio_nome VARCHAR(255),
    estado VARCHAR(5),

    formador_local VARCHAR(50),

    pba VARCHAR(20),
    pba_qtd INTEGER DEFAULT 0,

    eja_alfabetizacao VARCHAR(20),
    eja_alfabetizacao_qtd INTEGER DEFAULT 0,

    eja_anos_iniciais VARCHAR(20),
    eja_anos_iniciais_qtd INTEGER DEFAULT 0,

    jan INTEGER DEFAULT 0,
    fev INTEGER DEFAULT 0,
    mar INTEGER DEFAULT 0,
    abr INTEGER DEFAULT 0,
    mai INTEGER DEFAULT 0,
    jun INTEGER DEFAULT 0,
    jul INTEGER DEFAULT 0,
    ago INTEGER DEFAULT 0,
    setm INTEGER DEFAULT 0,

    data_envio TIMESTAMP
);

-- LOGS (se quiser manter)
CREATE TABLE IF NOT EXISTS logs_acesso (
    id SERIAL PRIMARY KEY,
    usuario_id VARCHAR(255),
    acao TEXT,
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ÍNDICES PARA PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_respostas_estado ON respostas(estado);
CREATE INDEX IF NOT EXISTS idx_respostas_usuario ON respostas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_respostas_municipio ON respostas(municipio_id);
CREATE INDEX IF NOT EXISTS idx_respostas_data ON respostas(data_envio);

CREATE INDEX IF NOT EXISTS idx_respostas_meses ON respostas(
    jan, fev, mar, abr, mai, jun, jul, ago, setm
);

CREATE INDEX IF NOT EXISTS idx_respostas_estado_municipio
ON respostas(estado, municipio_id);

-- POPULAR ESTADOS DO BRASIL
INSERT INTO estados (sigla, nome) VALUES
('AC', 'Acre'),
('AL', 'Alagoas'),
('AP', 'Amapá'),
('AM', 'Amazonas'),
('BA', 'Bahia'),
('CE', 'Ceará'),
('DF', 'Distrito Federal'),
('ES', 'Espírito Santo'),
('GO', 'Goiás'),
('MA', 'Maranhão'),
('MT', 'Mato Grosso'),
('MS', 'Mato Grosso do Sul'),
('MG', 'Minas Gerais'),
('PA', 'Pará'),
('PB', 'Paraíba'),
('PR', 'Paraná'),
('PE', 'Pernambuco'),
('PI', 'Piauí'),
('RJ', 'Rio de Janeiro'),
('RN', 'Rio Grande do Norte'),
('RS', 'Rio Grande do Sul'),
('RO', 'Rondônia'),
('RR', 'Roraima'),
('SC', 'Santa Catarina'),
('SP', 'São Paulo'),
('SE', 'Sergipe'),
('TO', 'Tocantins')
ON CONFLICT (sigla) DO NOTHING;