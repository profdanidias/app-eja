CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    email TEXT,
    tipo TEXT,
    funcao TEXT
);

CREATE TABLE respostas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    municipio_id INTEGER,
    municipio_nome TEXT,
    estado TEXT,
    formador_local TEXT,
    pba TEXT,
    pba_qtd INTEGER,
    eja_alfabetizacao TEXT,
    eja_alfabetizacao_qtd INTEGER,
    eja_anos_iniciais TEXT,
    eja_anos_iniciais_qtd INTEGER,
    jan INTEGER,
    fev INTEGER,
    mar INTEGER,
    abr INTEGER,
    mai INTEGER,
    jun INTEGER,
    jul INTEGER,
    ago INTEGER,
    setm INTEGER
);

CREATE TABLE logs_acesso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    acao TEXT,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
);
