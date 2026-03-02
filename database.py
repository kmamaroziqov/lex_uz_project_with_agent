import os
import psycopg2
from psycopg2 import pool
from sentence_transformers import SentenceTransformer, CrossEncoder
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.db_params = {
            "dbname": os.getenv("DB_NAME", "lexuz_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgres"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5433")
        }
        # Connection Pool
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(1, 20, **self.db_params)
        except Exception as e:
            print(f"❌ DB Pool xatosi: {e}. .env faylini tekshiring.")
            raise

        # Modellar
        print("🔄 Yuklanmoqda: Multilingual-E5 & Reranker...")
        self.embed_model = SentenceTransformer("intfloat/multilingual-e5-base")
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        self._initialized = True
        print("✅ Modellar va DB Pool tayyor.")

    def get_conn(self): return self.pool.getconn()
    def put_conn(self, conn): self.pool.putconn(conn)

    def setup_database(self):
        """Bazani va jadvallarni tozalab, yangi o'lcham bilan yaratish"""
        conn = self.get_conn()
        try:
            cur = conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # DIQQAT: Eski jadvalni o'chiramiz (o'lcham almashgani uchun shart)
            print("🗑 Eski jadval o'chirilmoqda...")
            cur.execute("DROP TABLE IF EXISTS documents;") 
            
            cur.execute("""
                CREATE TABLE documents (
                    id SERIAL PRIMARY KEY,
                    source VARCHAR(255),
                    content TEXT,
                    embedding vector(768) 
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS embedding_idx ON documents USING ivfflat (embedding vector_cosine_ops);")
            cur.execute("CREATE INDEX IF NOT EXISTS content_ts_idx ON documents USING GIN (to_tsvector('simple', content));")
            conn.commit()
            print("✅ Jadval 768 o'lcham bilan qayta yaratildi.")
        except Exception as e:
            print(f"❌ Setup xatosi: {e}")
        finally:
            self.put_conn(conn)

    def upload_data(self, folder="lex_structured"):
        """JSON fayllardan ma'lumotlarni bazaga yuklash"""
        import json
        import glob
        
        files = glob.glob(f"{folder}/*.json")
        if not files:
            print(f"⚠️ {folder} papkasida JSON fayllar topilmadi!")
            return

        conn = self.get_conn()
        try:
            cur = conn.cursor()
            # Eski ma'lumotlarni tozalash (ixtiyoriy)
            cur.execute("TRUNCATE TABLE documents RESTART IDENTITY;")
            
            for f_path in files:
                source = os.path.basename(f_path).replace(".json", "").replace("_", " ")
                print(f"📄 Yuklanmoqda: {source}...")
                with open(f_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for art_num, art_data in data.items():
                        content = art_data.get("content", "")
                        if len(content.strip()) < 50: continue
                        
                        # E5 uchun prefixlar juda muhim!
                        emb = self.embed_model.encode(f"passage: {content}").tolist()
                        cur.execute(
                            "INSERT INTO documents (source, content, embedding) VALUES (%s, %s, %s::vector)",
                            (source, content, emb)
                        )
                conn.commit()
            print("🎉 Barcha ma'lumotlar muvaffaqiyatli yuklandi!")
        except Exception as e:
            print(f"❌ Yuklashda xato: {e}")
            conn.rollback()
        finally:
            self.put_conn(conn)

    def hybrid_search(self, query: str, top_k: int = 8) -> List[Dict]:
        conn = self.get_conn()
        try:
            query_vec = self.embed_model.encode(f"query: {query}").tolist()
            cur = conn.cursor()
            search_sql = """
            WITH vector_matches AS (
                SELECT id, content, source, 1 - (embedding <=> %s::vector) as v_score
                FROM documents ORDER BY embedding <=> %s::vector LIMIT 20
            ),
            text_matches AS (
                SELECT id, content, source, ts_rank_cd(to_tsvector('simple', content), websearch_to_tsquery('simple', %s)) as t_score
                FROM documents WHERE to_tsvector('simple', content) @@ websearch_to_tsquery('simple', %s) LIMIT 20
            )
            SELECT COALESCE(v.content, t.content), COALESCE(v.source, t.source),
                   (COALESCE(v.v_score, 0) + COALESCE(t.t_score, 0)) as score
            FROM vector_matches v FULL OUTER JOIN text_matches t ON v.id = t.id
            ORDER BY score DESC LIMIT 15;
            """
            cur.execute(search_sql, (query_vec, query_vec, query, query))
            candidates = cur.fetchall()
            if not candidates: return []

            passages = [c[0] for c in candidates]
            rerank_scores = self.reranker.predict([(query, p) for p in passages])
            
            results = []
            for i, score in enumerate(rerank_scores):
                results.append({"content": candidates[i][0], "source": candidates[i][1], "score": float(score)})
            
            return sorted(results, key=lambda x: x['score'], reverse=True)[:4]
        finally:
            self.put_conn(conn)

# Global helper funksiya agentlar uchun
def search_lexuz_tool(query: str) -> str:
    db = DatabaseManager()
    results = db.hybrid_search(query)
    if not results: return "Bazada ushbu mavzu bo'yicha ma'lumot topilmadi."
    
    formatted = "📚 TASDIQLANGAN MANBALAR:\n\n"
    for res in results:
        formatted += f"📄 {res['source']}:\n{res['content']}\n{'-'*30}\n"
    return formatted

if __name__ == "__main__":
    db = DatabaseManager()
    print("1. Bazani sozlash...")
    db.setup_database()
    print("2. Ma'lumotlarni yuklash...")
    db.upload_data("lex_structured")