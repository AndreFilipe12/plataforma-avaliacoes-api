from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from psycopg2.errors import UniqueViolation, CheckViolation
from database import get_db_connection

app = FastAPI(
    title="Plataforma de Avaliações - Brasil",
    description="API para consultar e avaliar estabelecimentos comerciais pelo Brasil."
)

# Schemas para validação de dados de entrada
class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr

class AvaliacaoCreate(BaseModel):
    usuario_id: int
    estabelecimento_id: int
    nota: int
    comentario: Optional[str] = None

# 1. Rota para listar estabelecimentos (com filtro opcional por cidade)
@app.get("/estabelecimentos")
def listar_estabelecimentos(cidade: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT 
                e.id,
                e.nome AS estabelecimento,
                e.descricao,
                e.cidade,
                c.nome AS categoria,
                COALESCE(ROUND(AVG(a.nota), 1), 0)::FLOAT AS media_nota,
                COUNT(a.id)::INT AS total_avaliacoes
            FROM estabelecimentos e
            JOIN categorias c ON e.categoria_id = c.id
            LEFT JOIN avaliacoes a ON e.id = a.estabelecimento_id
        """
        params = []
        if cidade:
            query += " WHERE LOWER(e.cidade) = LOWER(%s)"
            params.append(cidade)

        query += " GROUP BY e.id, c.nome ORDER BY media_nota DESC;"
        
        cursor.execute(query, params)
        estabelecimentos = cursor.fetchall()
        return estabelecimentos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# 2. Rota para ver as avaliações de um estabelecimento específico
@app.get("/estabelecimentos/{estabelecimento_id}/avaliacoes")
def listar_avaliacoes(estabelecimento_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT 
                a.id,
                u.nome AS usuario,
                a.nota,
                a.comentario,
                a.criado_em
            FROM avaliacoes a
            JOIN usuarios u ON a.usuario_id = u.id
            WHERE a.estabelecimento_id = %s
            ORDER BY a.criado_em DESC;
        """
        cursor.execute(query, (estabelecimento_id,))
        avaliacoes = cursor.fetchall()
        return avaliacoes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# 3. Rota para cadastrar uma nova avaliação
@app.post("/avaliacoes", status_code=status.HTTP_201_CREATED)
def criar_avaliacao(avaliacao: AvaliacaoCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO avaliacoes (usuario_id, estabelecimento_id, nota, comentario)
               VALUES (%s, %s, %s, %s) RETURNING *;""",
            (avaliacao.usuario_id, avaliacao.estabelecimento_id, avaliacao.nota, avaliacao.comentario)
        )
        nova_avaliacao = cursor.fetchone()
        conn.commit()
        return nova_avaliacao
    except UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Este usuário já avaliou este estabelecimento!")
    except CheckViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="A nota deve ser um valor inteiro entre 1 e 5.")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()