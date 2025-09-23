# bench_read.py
import os
from typing import Optional
from sqlalchemy import create_engine, text  # type: ignore
from sqlalchemy.engine import Engine  # type: ignore

def _sqlalchemy_url() -> str:
    url = os.getenv("SQLALCHEMY_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        # Docker ağı için mantıklı varsayılan
        url = "postgresql+psycopg2://postgres:"
    # psycopg3 yoksa +psycopg -> +psycopg2'ye çevir (emniyet)
    if "+psycopg://" in url and not os.getenv("ALLOW_PSYCOPG3"):
        url = url.replace("+psycopg://", "+psycopg2://")
    return url

DATABASE_URL = _sqlalchemy_url()

class BenchRead:
    """
    cpu_benchmarks(cpu_name, score)
    gpu_benchmarks(gpu_name, score)
    cpu_aliases(alias -> name)
    gpu_aliases(alias -> name)
    """
    def __init__(self, url: Optional[str] = None) -> None:
        self.engine: Engine = create_engine(url or DATABASE_URL, pool_pre_ping=True, future=True)

    def _resolve_cpu(self, model: Optional[str]) -> Optional[str]:
        if not model:
            return None
        q = text("""
            WITH want(model) AS (SELECT :m)
            SELECT
              COALESCE(
                (SELECT cpu_name FROM cpu_benchmarks WHERE cpu_name = (SELECT model FROM want) LIMIT 1),
                (SELECT name     FROM cpu_aliases     WHERE alias    = (SELECT model FROM want) LIMIT 1)
              ) AS canon
        """)
        with self.engine.begin() as conn:
            row = conn.execute(q, {"m": model}).first()
        return row[0] if row and row[0] else None

    def _resolve_gpu(self, model: Optional[str]) -> Optional[str]:
        if not model:
            return None
        q = text("""
            WITH want(model) AS (SELECT :m)
            SELECT
              COALESCE(
                (SELECT gpu_name FROM gpu_benchmarks WHERE gpu_name = (SELECT model FROM want) LIMIT 1),
                (SELECT name     FROM gpu_aliases     WHERE alias    = (SELECT model FROM want) LIMIT 1)
              ) AS canon
        """)
        with self.engine.begin() as conn:
            row = conn.execute(q, {"m": model}).first()
        return row[0] if row and row[0] else None

    def cpu_score(self, model: str) -> Optional[int]:
        canon = self._resolve_cpu(model) or model
        q = text("SELECT score FROM cpu_benchmarks WHERE cpu_name = :m LIMIT 1;")
        with self.engine.begin() as conn:
            row = conn.execute(q, {"m": canon}).first()
        return int(row[0]) if row else None

    def gpu_score(self, model: str) -> Optional[int]:
        canon = self._resolve_gpu(model) or model
        q = text("SELECT score FROM gpu_benchmarks WHERE gpu_name = :m LIMIT 1;")
        with self.engine.begin() as conn:
            row = conn.execute(q, {"m": canon}).first()
        return int(row[0]) if row else None

if __name__ == "__main__":
    br = BenchRead()
    with br.engine.connect() as c:
        v = c.execute(text("select version(), current_database();")).first()
        print("[db]", v[0].split()[0], "db=", v[1])

    # Demo:
    print("cpu( Intel Core i5-12400F ) =>", br.cpu_score("Intel Core i5-12400F"))
    print("gpu( GeForce RTX 4060 )     =>", br.gpu_score("GeForce RTX 4060"))
    # alias örneği:
    print("gpu( NVIDIA GeForce RTX 4060 Laptop GPU ) =>", br.gpu_score("NVIDIA GeForce RTX 4060 Laptop GPU"))

